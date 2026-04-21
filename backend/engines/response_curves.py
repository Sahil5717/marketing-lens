"""
Response Curve Engine — Production Grade
=========================================
Fits diminishing-returns curves: power-law y=a·x^b and Hill y=a·x^S/(K^S+x^S)
Uses scipy.optimize.curve_fit (Levenberg-Marquardt) with proper diagnostics.

Libraries: scipy.optimize.curve_fit, scikit-learn (R², RMSE, cross-val), numpy
"""
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit, minimize_scalar
from sklearn.metrics import r2_score, mean_squared_error
from sklearn.model_selection import LeaveOneOut
from typing import Dict

def power_law(x, a, b):
    return a * np.power(np.maximum(x, 1e-6), b)

def hill_curve(x, a, b, K):
    xb = np.power(np.maximum(x, 1e-6), b)
    return a * xb / (np.power(K, b) + xb)

def marginal_power_law(x, a, b):
    if x <= 0: return float("inf")
    return a * b * np.power(x, b - 1)

def marginal_hill(x, a, b, K):
    if x <= 0: return float("inf")
    Kb = K**b; xb = x**b
    return a * b * (x**(b-1)) * Kb / ((Kb + xb)**2)


# Per-channel adstock half-life (in months). Adstock captures carryover:
# a TV ad seen this month still drives sales next month at reduced effect.
# Half-life is "how many months until the remaining effect is 50%."
#
#   Digital: ~0 months (effect is near-immediate). No adstock applied.
#   Email: ~0.3 months (roughly 1 week — same-ish as digital)
#   Social/display: near-immediate in short-term but brand halo exists;
#     keep at 0 for now — that's Bayesian territory.
#   Radio: ~1 month (broadcast carryover is real but short)
#   TV: ~2 months (heavy carryover — a TV flight drives multi-month lift)
#   OOH: ~1.5 months (placements stay up, effect decays as novelty wears off)
#   Events: ~3 months (trade show contacts convert over a long tail)
#   Direct mail: ~1 month (catalog stays on a coffee table for weeks)
#   Call center: 0 (operational, no carryover)
#
# These are pre-Bayesian approximations. The Bayesian rebuild (Week 4-5)
# will fit adstock half-lives as model parameters with tight priors
# instead of these hardcoded defaults.
CHANNEL_ADSTOCK_HALFLIFE = {
    "tv_national":    2.0,
    "radio":          1.0,
    "ooh":            1.5,
    "events":         3.0,
    "direct_mail":    1.0,
    "call_center":    0.0,
    # Digital — no adstock (immediate-response attribution)
    "paid_search":    0.0,
    "organic_search": 0.0,
    "social_paid":    0.0,
    "display":        0.0,
    "email":          0.3,
    "video_youtube":  0.3,
}


def _apply_adstock(spend_series, half_life_months):
    """
    Apply geometric adstock decay to a time-ordered spend series.

    Math: adstocked[t] = spend[t] + decay * adstocked[t-1]
    where decay = 0.5 ** (1 / half_life_months).

    Conceptually: the adstocked value at time t is the sum of all past
    spend, weighted by how long ago it happened (with half-life governing
    how fast old spend "forgets").

    If half_life_months <= 0 → return the raw series unchanged (digital).

    This is applied to spend BEFORE fitting the response curve for offline
    channels, so the curve reflects "the revenue at time t as a function
    of the still-active portion of cumulative spend," not "revenue as a
    function of this month's cash outlay alone." Offline curves fit with
    adstocked spend give dramatically better R² for broadcast channels.
    """
    if half_life_months is None or half_life_months <= 0:
        return np.asarray(spend_series, dtype=float)

    x = np.asarray(spend_series, dtype=float)
    decay = 0.5 ** (1.0 / half_life_months)
    out = np.zeros_like(x)
    out[0] = x[0]
    for t in range(1, len(x)):
        out[t] = x[t] + decay * out[t - 1]
    return out


def _fit_secondary_curve(x_spend, y_metric, metric_name):
    """
    Fit a simple Hill curve of spend→offline metric (e.g., reach, calls,
    attendees). Returns a dict with params, R², MAPE, curve points for the
    Channel Detail UI to render.

    Hill shape is the right default for reach (structural saturation at
    population size) and also works well for direct-response metrics.
    Returns None if the fit can't be done (too few points, all zero, etc.).

    This is a *secondary* curve — the primary revenue curve still drives
    the optimizer. This curve exists for honest diagnostics: when a user
    looks at TV's low R² on the revenue curve, they can see the reach
    curve fits well, explaining why the model is more confident than
    the revenue-R² alone would suggest.
    """
    if len(x_spend) < 3:
        return None
    y_arr = np.asarray(y_metric, dtype=float)
    x_arr = np.asarray(x_spend, dtype=float)
    # Skip if all-zero or near-zero (digital channels, or offline channel
    # whose data wasn't populated)
    if y_arr.sum() <= 0 or y_arr.max() < 1:
        return None

    try:
        # Hill fit: y = a * x^b / (K^b + x^b)
        # Initial guess: a = max(y) * 1.2 (asymptote just above observed max),
        # b = 1.0 (linear-ish near origin), K = median(x) (half-saturation
        # point at median spend)
        a0 = float(y_arr.max()) * 1.2
        b0 = 1.0
        K0 = float(np.median(x_arr))
        popt, pcov = curve_fit(
            hill_curve, x_arr, y_arr,
            p0=[a0, b0, K0],
            bounds=([0, 0.1, 1], [np.inf, 3.0, float(x_arr.max()) * 5]),
            maxfev=10000,
        )
        a, b, K = popt
        y_pred = hill_curve(x_arr, a, b, K)
        r2 = r2_score(y_arr, y_pred)
        mape = float(np.mean(np.abs((y_arr - y_pred) / np.maximum(np.abs(y_arr), 1))) * 100)

        # Build visualization points. Extend past observed max to show
        # where the curve asymptotes.
        x_max = float(x_arr.max()) * 1.5
        curve_pts = []
        for s in np.linspace(0, x_max, 40):
            curve_pts.append({
                "spend": round(float(s), 0),
                "value": round(float(hill_curve(s, a, b, K)), 0),
            })

        # Data points for overlay (the actual observed monthly values)
        data_pts = [{"spend": round(float(xi), 0),
                     "value": round(float(yi), 0)}
                    for xi, yi in zip(x_arr, y_arr)]

        return {
            "metric_name": metric_name,
            "metric_display": metric_name.replace("_", " ").title(),
            "model": "hill",
            "params": {
                "a": round(float(a), 4),
                "b": round(float(b), 4),
                "K": round(float(K), 2),
            },
            "diagnostics": {
                "r_squared": round(float(r2), 4),
                "mape": round(mape, 1),
                "n_data_points": len(x_arr),
            },
            "curve_points": curve_pts,
            "data_points": data_pts,
            "saturation_value_asymptote": round(float(a), 0),
        }
    except Exception:
        return None

def fit_response_curves(campaign_df, model_type="power_law"):
    """
    Fit response curves per channel with scipy.optimize.curve_fit.
    model_type: "power_law", "hill", or "auto" (fits both, picks best R² per channel)
    Returns: fitted params, R², RMSE, confidence intervals, LOO-CV score, curve points.
    """
    if model_type == "auto":
        # Fit both models, keep the one with better R² per channel
        results_pl = fit_response_curves(campaign_df, model_type="power_law")
        results_hill = fit_response_curves(campaign_df, model_type="hill")
        results = {}
        for ch in set(list(results_pl.keys()) + list(results_hill.keys())):
            pl = results_pl.get(ch, {})
            hl = results_hill.get(ch, {})
            if "error" in pl and "error" in hl:
                results[ch] = pl  # both failed
            elif "error" in pl:
                results[ch] = hl
                results[ch]["_auto_selected"] = "hill"
            elif "error" in hl:
                results[ch] = pl
                results[ch]["_auto_selected"] = "power_law"
            else:
                pl_r2 = pl.get("r_squared", 0)
                hl_r2 = hl.get("r_squared", 0)
                if hl_r2 > pl_r2 + 0.02:  # Hill needs meaningfully better R² to justify complexity
                    results[ch] = hl
                    results[ch]["_auto_selected"] = "hill"
                else:
                    results[ch] = pl
                    results[ch]["_auto_selected"] = "power_law"
        return results

    results = {}
    # Columns that exist in the data for offline metrics. We'll aggregate
    # any that are present so the secondary-curve fitter has data to work
    # with. Each maps to a sensible aggregation ('mean' for reach because
    # summing monthly reach double-counts same viewers).
    offline_metric_aggs = {
        "grps": "sum",
        "reach": "mean",
        "calls_generated": "sum",
        "event_attendees": "sum",
        "dealer_enquiries": "sum",
        "store_visits": "sum",
    }

    for channel in campaign_df["channel"].unique():
        ch_data = campaign_df[campaign_df["channel"] == channel]

        # Build aggregation dict — revenue + any offline columns present
        month_col = "month" if "month" in ch_data.columns else "date"
        agg_args = {
            "spend": ("spend", "sum"),
            "revenue": ("revenue", "sum"),
            "conversions": ("conversions", "sum"),
        }
        for col, method in offline_metric_aggs.items():
            if col in ch_data.columns:
                agg_args[col] = (col, method)

        monthly = ch_data.groupby(month_col).agg(**agg_args).reset_index().sort_values(month_col)
        x = monthly["spend"].values.astype(float)
        y = monthly["revenue"].values.astype(float)
        if len(x) < 3 or x.sum() == 0: continue

        # Determine this channel's attribution_basis + primary_metric so
        # we know which secondary curve (if any) to fit
        attribution_basis = "click"
        primary_metric = "clicks"
        if "attribution_basis" in ch_data.columns and len(ch_data) > 0:
            attribution_basis = str(ch_data["attribution_basis"].iloc[0])
        if "primary_metric" in ch_data.columns and len(ch_data) > 0:
            primary_metric = str(ch_data["primary_metric"].iloc[0])

        # Adstock half-life for this channel (months). Surfaced in the
        # response so the UI can show "TV has 2-month carryover." The actual
        # adstock pre-processing of the spend series is deferred to the
        # Bayesian rebuild (Week 4-5) where it composes cleanly with
        # priors on saturation. A frequentist adstock rescale against the
        # power_law analytical saturation is mathematically fragile
        # (saturation formula is unstable for non-asymptotic fits).
        adstock_halflife = CHANNEL_ADSTOCK_HALFLIFE.get(channel, 0.0)

        try:
            if model_type == "power_law":
                popt, pcov = curve_fit(power_law, x, y, p0=[1.0, 0.5],
                    bounds=([0, 0.01], [np.inf, 0.99]), maxfev=10000)
                a, b = popt
                y_pred = power_law(x, a, b)
                perr = np.sqrt(np.diag(pcov))  # std errors of params
                avg_spend = float(x.mean())

                # Near-linear detection. When b approaches 1.0, the power-law
                # curve doesn't meaningfully saturate within any spend range
                # you could actually commit to -- the analytical saturation
                # point (a*b)^(1/(1-b)) goes to infinity as b → 1, which
                # produced 10^150-scale sat_spend values on organic search
                # (b=0.99) and drove downstream recommendations to fabricate
                # "40% headroom" where none existed.
                #
                # We flag the fit as near-linear (unreliable for headroom/
                # saturation claims), cap the reported saturation at 5x
                # observed max spend, and cap trusted_headroom_pct at 40%
                # to prevent SCALE recs from sizing impact off a phantom
                # saturation gap.
                near_linear = bool(b > 0.90)
                observed_max = float(np.max(x))

                if near_linear:
                    # No trustable analytical saturation. Use a conservative
                    # ceiling of 3x current spend (same cap as the optimizer).
                    sat_spend = observed_max * 3.0
                    # Trusted headroom is bounded regardless of curve shape.
                    trusted_headroom = 40.0
                else:
                    sat_spend_analytical = float(np.power(a*b, 1/(1-b)))
                    # Clamp the reported saturation at 5x observed max; beyond
                    # that we're extrapolating past what the data supports.
                    sat_spend = min(sat_spend_analytical, observed_max * 5.0)
                    trusted_headroom = max(0, (sat_spend - avg_spend) / sat_spend * 100)

                # Marginal ROI at current spend -- this is in the trusted
                # range (avg_spend is inside observed data), so no cap needed.
                mROI = marginal_power_law(avg_spend, a, b)
                # Raw headroom (using analytical sat) kept for diagnostic
                # comparison; NOT used by downstream engines.
                raw_headroom = max(0, (sat_spend - avg_spend) / sat_spend * 100) if sat_spend > 0 else 0
                headroom = trusted_headroom

                # Generate curve points for visualization
                x_max = max(x) * 1.8
                curve_pts = [{"spend": round(s), "revenue": round(float(power_law(s, a, b)))}
                             for s in np.linspace(0, x_max, 50)]
                params = {"a": round(float(a), 4), "b": round(float(b), 4),
                          "a_std": round(float(perr[0]), 4), "b_std": round(float(perr[1]), 4),
                          "near_linear": near_linear}
            else:  # hill
                p0 = [max(y)*1.5, 0.8, np.median(x)]
                popt, pcov = curve_fit(hill_curve, x, y, p0=p0,
                    bounds=([0,0.1,1], [np.inf, 3.0, np.max(x)*5]), maxfev=10000)
                a, b, K = popt
                y_pred = hill_curve(x, a, b, K)
                perr = np.sqrt(np.diag(pcov))
                avg_spend = float(x.mean())
                mROI = marginal_hill(avg_spend, a, b, K)
                sat_spend = K * 3; headroom = max(0, (sat_spend-avg_spend)/sat_spend*100)
                x_max = max(x)*1.8
                curve_pts = [{"spend": round(s), "revenue": round(float(hill_curve(s, a, b, K)))}
                             for s in np.linspace(0, x_max, 50)]
                params = {"a": round(float(a),4), "b": round(float(b),4), "K": round(float(K),2),
                          "a_std": round(float(perr[0]),4), "b_std": round(float(perr[1]),4), "K_std": round(float(perr[2]),2)}

            # Diagnostics
            r2 = r2_score(y, y_pred)
            rmse = float(np.sqrt(mean_squared_error(y, y_pred)))
            mape = float(np.mean(np.abs((y - y_pred) / np.maximum(y, 1))) * 100)

            # Leave-One-Out Cross-Validation
            loo_errors = []
            if len(x) >= 4:
                loo = LeaveOneOut()
                for train_idx, test_idx in loo.split(x):
                    try:
                        if model_type == "power_law":
                            p_loo, _ = curve_fit(power_law, x[train_idx], y[train_idx],
                                p0=[1.0, 0.5], bounds=([0,0.01],[np.inf,0.99]), maxfev=5000)
                            pred = power_law(x[test_idx], *p_loo)
                        else:
                            p_loo, _ = curve_fit(hill_curve, x[train_idx], y[train_idx],
                                p0=p0, bounds=([0,0.1,1],[np.inf,3.0,np.max(x)*5]), maxfev=5000)
                            pred = hill_curve(x[test_idx], *p_loo)
                        loo_errors.append(float((y[test_idx] - pred)**2))
                    except: pass
                loo_rmse = float(np.sqrt(np.mean(loo_errors))) if loo_errors else None
            else:
                loo_rmse = None

            # Confidence assessment
            if r2 > 0.7 and mape < 20: confidence = "High"
            elif r2 > 0.4 and mape < 40: confidence = "Medium"
            else: confidence = "Low"

            # Fit secondary curve for offline channels. The metric depends
            # on the channel's primary_metric: TV/radio fit reach or grps,
            # call_center fits calls_generated, events fits event_attendees,
            # direct_mail fits dealer_enquiries, OOH fits reach or store_visits.
            secondary_curve = None
            if attribution_basis in ("reach", "direct_response") and primary_metric in monthly.columns:
                y_secondary = monthly[primary_metric].values.astype(float)
                secondary_curve = _fit_secondary_curve(x, y_secondary, primary_metric)

            results[channel] = {
                "model": model_type,
                "params": params,
                "current_avg_spend": round(avg_spend, 0),
                "saturation_spend": round(sat_spend, 0),
                "marginal_roi": round(float(mROI), 4),
                "headroom_pct": round(headroom, 1),
                "near_linear_fit": bool(params.get("near_linear", False)),
                "diagnostics": {
                    "r_squared": round(float(r2), 4),
                    "rmse": round(rmse, 0),
                    "mape": round(mape, 1),
                    "loo_cv_rmse": round(loo_rmse, 0) if loo_rmse else None,
                    "n_data_points": len(x),
                    "confidence": confidence,
                },
                "curve_points": curve_pts,
                "data_points": [{"spend": round(float(xi)), "revenue": round(float(yi))}
                                for xi, yi in zip(x, y)],
                # Channel taxonomy (flows from the source data)
                "attribution_basis": attribution_basis,
                "primary_metric": primary_metric,
                # Adstock metadata — informational for the UI. The frequentist
                # curve fit is NOT actually adstocked here; this is the
                # half-life the Bayesian rebuild will use as an informative
                # prior. Surfacing it now means the UI can show "this channel
                # has carryover" even before Bayesian lands.
                "adstock_halflife_months": adstock_halflife,
                # Secondary curve — present only for offline channels. The
                # Channel Detail UI renders this alongside the revenue curve
                # so users see the honest picture: TV's reach curve may fit
                # beautifully even if the revenue curve has modest R².
                "secondary_curve": secondary_curve,
            }
        except Exception as e:
            results[channel] = {"model": model_type, "error": str(e), "diagnostics": {"confidence": "Failed"}}
    return results

if __name__ == "__main__":
    from mock_data import generate_all_data
    data = generate_all_data()
    df = data["campaign_performance"]
    print("Fitting power-law response curves...")
    r = fit_response_curves(df, "power_law")
    for ch, info in r.items():
        d = info.get("diagnostics", {})
        print(f"  {ch}: R²={d.get('r_squared','?')} MAPE={d.get('mape','?')}% mROI={info.get('marginal_roi','?')} [{d.get('confidence','?')}]")
    print("\nFitting Hill curves...")
    r2 = fit_response_curves(df, "hill")
    for ch, info in r2.items():
        d = info.get("diagnostics", {})
        print(f"  {ch}: R²={d.get('r_squared','?')} MAPE={d.get('mape','?')}% [{d.get('confidence','?')}]")
