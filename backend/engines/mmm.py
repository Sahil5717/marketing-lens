"""
Bayesian Marketing Mix Model — Production Grade
================================================
Model: Revenue_t = baseline + Σ_c β_c · Hill(Adstock(Spend_c,t; λ_c); K_c) + season + ε_t

Libraries:
    pymc (NUTS sampler), arviz (diagnostics), scipy (MLE fallback), scikit-learn (metrics)
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional
from sklearn.metrics import r2_score, mean_absolute_percentage_error
import warnings, logging
warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

def geometric_adstock(x, decay):
    """Geometric adstock: y[t] = x[t] + decay * y[t-1].

    Implemented via scipy.signal.lfilter for C-speed recursion. A pure-Python
    loop here gets called thousands of times inside MMM fits and was the
    single biggest bottleneck (~70% of MLE fit time).
    """
    from scipy.signal import lfilter
    x = np.asarray(x, dtype=np.float64)
    # y[t] - decay * y[t-1] = x[t]  =>  b=[1], a=[1, -decay]
    return lfilter([1.0], [1.0, -float(decay)], x)

def hill_saturation(x, half_sat, slope=1.0):
    x_s = np.maximum(x, 1e-10)
    return np.power(x_s, slope) / (np.power(half_sat, slope) + np.power(x_s, slope))

def weibull_adstock(x, shape, scale, max_lag=13):
    """Weibull adstock: flexible peak+decay. shape>1=delayed peak (TV/events), shape≤1=immediate."""
    lags = np.arange(max_lag)
    w = (shape/scale)*np.power(lags/scale, shape-1)*np.exp(-np.power(lags/scale, shape))
    w = w/(w.sum()+1e-10)
    return np.convolve(x, w, mode="full")[:len(x)]

def select_best_adstock(spend, revenue):
    """Auto-select geometric vs Weibull adstock per channel."""
    if spend.sum()==0 or len(spend)<6: return "geometric", {"decay":0.5}, 0.0
    best_corr,best_type,best_params = -1,"geometric",{"decay":0.5}
    for d in np.arange(0.05,0.95,0.05):
        ad=geometric_adstock(spend,d)
        if ad.std()>0:
            corr=abs(np.corrcoef(ad,revenue)[0,1])
            if corr>best_corr: best_corr=corr; best_type="geometric"; best_params={"decay":round(d,2)}
    for shape in [0.5,1.0,1.5,2.0,3.0]:
        for scale in [1.0,2.0,3.0,5.0]:
            try:
                ad=weibull_adstock(spend,shape,scale)
                if ad.std()>0:
                    corr=abs(np.corrcoef(ad,revenue)[0,1])
                    if corr>best_corr: best_corr=corr; best_type="weibull"; best_params={"shape":shape,"scale":scale}
            except: pass
    return best_type, best_params, round(best_corr,4)

def prepare_mmm_data(df):
    time_col = "month" if "month" in df.columns else "date"
    monthly = df.groupby(time_col).agg(revenue=("revenue","sum"), total_spend=("spend","sum")).reset_index().sort_values(time_col)
    channels = sorted(df["channel"].unique())
    spend_matrix = {}
    for ch in channels:
        ch_agg = df[df["channel"]==ch].groupby(time_col)["spend"].sum()
        spend_matrix[ch] = monthly[time_col].map(ch_agg).fillna(0).values.astype(np.float64)
    if "month" in df.columns:
        month_nums = monthly["month"].apply(lambda x: int(str(x).split("-")[1]) if "-" in str(x) else 1).values
    else:
        month_nums = (np.arange(len(monthly)) % 12) + 1
    return {"revenue": monthly["revenue"].values.astype(np.float64), "spend_matrix": spend_matrix,
            "channels": channels, "n_periods": len(monthly), "month_nums": month_nums, "periods": monthly[time_col].values,
            "trend": np.arange(len(monthly), dtype=np.float64)}

def fit_bayesian_mmm(data, n_draws=1000, n_tune=500, n_chains=4, target_accept=0.95):
    """Full Bayesian MMM via PyMC NUTS.

    Operates in scaled revenue space (revenue / rev_scale) for numerical
    stability. Without this scaling, NUTS has to navigate a posterior where
    baseline ~ Normal(rev_mean, rev_std) and betas are each O(rev_std), so
    the effective mass of the posterior is at ~10^7-10^8 in raw units. This
    produces huge step-size tuning pathologies and divergences. In scaled
    space the entire posterior lives in O(1) region and NUTS performs well.

    Priors are deliberately informative but not biased:
    - baseline ~ Normal(mean of scaled revenue, 0.5 * scaled revenue sd)
    - betas   ~ HalfNormal(sigma=0.5) -- positive, typical values ~ O(0.4)
    - decays  ~ Beta(alpha=2, beta=4) -- mean ~0.33, wider at low decay (realistic)
    - half_sats ~ LogNormal(mu=-0.7, sigma=0.5) -- centered at ~0.5, bounded above 0
    - sigma   ~ HalfNormal(sigma=0.3) -- residual sd, scaled

    Convergence diagnostics checked: r-hat < 1.05 for all params, ESS bulk > 100.
    If these fail, caller's fallback chain should discard.
    """
    import pymc as pm
    import arviz as az

    revenue = data["revenue"]
    channels = data["channels"]
    n_ch = len(channels)
    T = data["n_periods"]
    spend_raw = np.column_stack([data["spend_matrix"][ch] for ch in channels])
    spend_scales = spend_raw.max(axis=0) + 1e-10
    spend_normed = spend_raw / spend_scales
    sin_s = np.sin(2 * np.pi * data["month_nums"] / 12)
    cos_s = np.cos(2 * np.pi * data["month_nums"] / 12)

    # Scale revenue to O(1) for NUTS stability. All parameters live in scaled space.
    rev_scale = float(np.abs(revenue).mean()) + 1e-10
    rev_scaled = revenue / rev_scale

    rev_s_mean = float(rev_scaled.mean())
    rev_s_std = float(rev_scaled.std()) + 1e-10

    with pm.Model():
        # Baseline: centered near the scaled revenue mean, moderately tight.
        baseline = pm.Normal("baseline", mu=rev_s_mean, sigma=rev_s_std * 0.5)
        # Media betas: non-negative. Sigma=0.5 in scaled space allows per-channel
        # contributions up to ~0.5 of average revenue, which is generous.
        betas = pm.HalfNormal("betas", sigma=0.5, shape=n_ch)
        # Decays: Beta(2,4) favors low decay (immediate-effect channels dominant)
        # but allows high decay where the data supports it.
        decays = pm.Beta("decays", alpha=2, beta=4, shape=n_ch)
        # Half-saturation: positive, centered around the middle of normalized spend.
        half_sats = pm.LogNormal("half_sats", mu=-0.7, sigma=0.5, shape=n_ch)
        # Seasonal amplitudes (small relative to scaled revenue).
        gamma = pm.Normal("gamma", mu=0.0, sigma=rev_s_std * 0.2, shape=2)
        # Residual noise.
        sigma = pm.HalfNormal("sigma", sigma=rev_s_std * 0.5)

        mu = baseline + gamma[0] * sin_s + gamma[1] * cos_s
        for c in range(n_ch):
            # Geometric adstock via recursion (scan would be faster, but this
            # is clearer and T is small).
            ad_list = [spend_normed[0, c]]
            for t in range(1, T):
                ad_list.append(spend_normed[t, c] + decays[c] * ad_list[-1])
            ad_tensor = pm.math.stack(ad_list)
            sat = ad_tensor / (half_sats[c] + ad_tensor)
            mu = mu + betas[c] * sat

        pm.Normal("obs", mu=mu, sigma=sigma, observed=rev_scaled)

        trace = pm.sample(
            draws=n_draws,
            tune=n_tune,
            chains=n_chains,
            cores=1,
            target_accept=target_accept,
            return_inferencedata=True,
            progressbar=False,
            random_seed=42,
        )

    # Convergence diagnostics. These decide whether the caller trusts the result.
    summary = az.summary(trace, var_names=["betas", "decays", "baseline"])
    rhat_max = float(summary["r_hat"].max())
    ess_min = float(summary["ess_bulk"].min())
    try:
        loo_score = float(az.loo(trace).loo)
    except Exception:
        loo_score = None

    # Posterior summaries in scaled space.
    beta_samples = trace.posterior["betas"].values  # (chain, draw, n_ch)
    beta_means_scaled = beta_samples.mean(axis=(0, 1))
    beta_stds_scaled = beta_samples.std(axis=(0, 1))
    beta_hdi_scaled = az.hdi(trace, var_names=["betas"], hdi_prob=0.9)["betas"].values
    decay_samples = trace.posterior["decays"].values
    decay_means = decay_samples.mean(axis=(0, 1))
    decay_stds = decay_samples.std(axis=(0, 1))
    hs_samples = trace.posterior["half_sats"].values
    hs_means = hs_samples.mean(axis=(0, 1))
    baseline_scaled_mean = float(trace.posterior["baseline"].values.mean())
    gamma_means = trace.posterior["gamma"].values.mean(axis=(0, 1))

    # Rebuild posterior mean prediction in scaled space, then unscale to dollars.
    y_pred_scaled = np.full(T, baseline_scaled_mean)
    y_pred_scaled = y_pred_scaled + gamma_means[0] * sin_s + gamma_means[1] * cos_s
    for c, ch in enumerate(channels):
        ad = geometric_adstock(spend_normed[:, c], float(decay_means[c]))
        sat = hill_saturation(ad, max(float(hs_means[c]), 1e-6))
        # Note: hill_saturation returns ad^1 / (hs^1 + ad^1), matching the model.
        y_pred_scaled = y_pred_scaled + float(beta_means_scaled[c]) * sat
    y_pred = y_pred_scaled * rev_scale

    # Channel contributions in dollars.
    contributions = {}
    total_media = 0.0
    # Keep raw posterior samples of betas/decays/hs in memory so we can
    # compute per-channel ROAS HDIs below. These arrays are (n_chain, n_draw, n_ch).
    beta_samples_flat = beta_samples.reshape(-1, len(channels))
    decay_samples_flat = decay_samples.reshape(-1, len(channels))
    hs_samples_flat = hs_samples.reshape(-1, len(channels))
    n_draws_total = beta_samples_flat.shape[0]

    for c, ch in enumerate(channels):
        spend = data["spend_matrix"][ch]
        spend_total = float(spend.sum())
        ad = geometric_adstock(spend_normed[:, c], float(decay_means[c]))
        sat = hill_saturation(ad, max(float(hs_means[c]), 1e-6))
        contrib_dollars = max(
            0.0,
            float(beta_means_scaled[c]) * float(sat.sum()) * rev_scale,
        )
        total_media += contrib_dollars
        # Report beta in dollar-per-unit-scaled-spend for comparability.
        beta_dollar = float(beta_means_scaled[c]) * rev_scale
        hdi_dollar = [
            float(beta_hdi_scaled[c, 0]) * rev_scale,
            float(beta_hdi_scaled[c, 1]) * rev_scale,
        ]

        # --- Per-draw ROAS and contribution computation ---
        # For each posterior draw, recompute the full saturation path using
        # THAT draw's decay and half-saturation, then contribution = beta * sum(sat).
        # ROAS = contribution / spend_total. Take 5th/95th percentiles for 90% HDI.
        #
        # Without this, the UI has no honest uncertainty around ROAS — only
        # a parameter-level HDI on beta, which isn't what a CMO asks to see.
        # This loop is cheap: ~600 draws × 6 channels × 48 periods = 170k ops.
        contrib_draws = np.empty(n_draws_total)
        roas_draws = np.empty(n_draws_total)
        for d in range(n_draws_total):
            ad_d = geometric_adstock(spend_normed[:, c], float(decay_samples_flat[d, c]))
            sat_d = hill_saturation(ad_d, max(float(hs_samples_flat[d, c]), 1e-6))
            contrib_d = max(
                0.0,
                float(beta_samples_flat[d, c]) * float(sat_d.sum()) * rev_scale,
            )
            contrib_draws[d] = contrib_d
            roas_draws[d] = contrib_d / max(spend_total, 1.0)
        roas_hdi_low = float(np.percentile(roas_draws, 5))
        roas_hdi_high = float(np.percentile(roas_draws, 95))
        roas_mean_draws = float(roas_draws.mean())
        contrib_hdi_low = float(np.percentile(contrib_draws, 5))
        contrib_hdi_high = float(np.percentile(contrib_draws, 95))

        contributions[ch] = {
            "contribution": round(contrib_dollars, 0),
            "contribution_hdi_90": [round(contrib_hdi_low, 0), round(contrib_hdi_high, 0)],
            "beta_mean": round(beta_dollar, 4),
            "beta_std": round(float(beta_stds_scaled[c]) * rev_scale, 4),
            "beta_hdi_90": [round(hdi_dollar[0], 4), round(hdi_dollar[1], 4)],
            "decay_mean": round(float(decay_means[c]), 3),
            "decay_std": round(float(decay_stds[c]), 3),
            "half_saturation": round(float(hs_means[c]), 4),
            "spend": round(spend_total, 0),
            # ROAS HDI from the full joint posterior — not beta / spend,
            # but the proper marginal distribution of contribution/spend
            # accounting for uncertainty in beta, decay, and saturation
            # jointly. This is what the UI surfaces as "ROAS: X± Y".
            "mmm_roas": round(contrib_dollars / max(spend_total, 1.0), 2),
            "mmm_roas_mean_posterior": round(roas_mean_draws, 2),
            "mmm_roas_hdi_90": [round(roas_hdi_low, 2), round(roas_hdi_high, 2)],
            "_spend_scale": float(spend_scales[c]),
        }

    total_rev = float(revenue.sum())
    bl_contrib = max(0.0, total_rev - total_media)
    r2 = float(r2_score(revenue, y_pred))
    mape = float(mean_absolute_percentage_error(revenue, y_pred) * 100)

    # --- Bayesian response curves with 80% HDI band ---
    # For each channel, build a spend → revenue curve evaluating the full
    # joint posterior at each spend point. The curve's MIDDLE is the
    # posterior median; the SHADED BAND is the 10th/90th percentiles.
    #
    # These are "marginal" response curves — they show the per-channel
    # effect assuming a single month of spend at that level (vs the
    # multi-period adstock-aware sum used for total contribution).
    # Honest framing for the UI: "expected revenue at this monthly spend,
    # given all we know about decay and saturation."
    #
    # Grid: 30 spend points from 0 to 1.5× observed max. Cheap since the
    # per-draw computation is just one adstock+saturation evaluation.
    CURVE_POINTS = 30
    for c, ch in enumerate(channels):
        cc = contributions[ch]
        spend = data["spend_matrix"][ch]
        spend_max = float(spend.max())
        spend_scale_c = spend_scales[c]
        # Build a spend grid in RAW dollars (for UI display) and in normalized
        # space (for computation, matching the model)
        x_grid_raw = np.linspace(0, spend_max * 1.5, CURVE_POINTS)
        x_grid_normed = x_grid_raw / spend_scale_c

        # For each draw, compute revenue = beta * hill_sat(adstock_one_period(x, decay), hs)
        # Simplification: "one period" adstock on a single-month spend reduces to just
        # sat(x/scale, hs) since adstock of a single-period signal is itself.
        # So curve_draws[d, i] = beta[d] * sat(x_grid_normed[i], hs[d]) * rev_scale
        curve_matrix = np.empty((n_draws_total, CURVE_POINTS))
        for d in range(n_draws_total):
            hs_d = max(float(hs_samples_flat[d, c]), 1e-6)
            beta_d = float(beta_samples_flat[d, c])
            # Hill saturation: x / (hs + x)
            sat_vals = x_grid_normed / (hs_d + x_grid_normed)
            curve_matrix[d, :] = beta_d * sat_vals * rev_scale

        # Point estimate curve at the posterior mean params
        curve_mid = np.percentile(curve_matrix, 50, axis=0)
        curve_low = np.percentile(curve_matrix, 10, axis=0)
        curve_high = np.percentile(curve_matrix, 90, axis=0)

        cc["response_curve"] = [
            {
                "spend": round(float(x_grid_raw[i]), 0),
                "revenue": round(float(curve_mid[i]), 0),
                "revenue_hdi_low": round(float(curve_low[i]), 0),
                "revenue_hdi_high": round(float(curve_high[i]), 0),
            }
            for i in range(CURVE_POINTS)
        ]
        cc["current_monthly_spend"] = round(float(spend.mean()), 0)

    for ch in channels:
        cc = contributions[ch]
        cc["contribution_pct"] = round(cc["contribution"] / max(total_rev, 1) * 100, 1)
        # mmm_roas already set above — keep it for backward-compat consumers.
        # Confidence tier: now driven by ROAS HDI width (more honest than beta
        # CI width). HDI narrow relative to mean = High, wider = Medium, very
        # wide or straddles zero = Low.
        roas_lo, roas_hi = cc.get("mmm_roas_hdi_90", [0, 0])
        roas_mid = cc.get("mmm_roas", 1e-6)
        hdi_rel_width = (roas_hi - roas_lo) / max(abs(roas_mid), 1e-6)
        if hdi_rel_width < 0.4:
            cc["confidence"] = "High"
        elif hdi_rel_width < 0.9:
            cc["confidence"] = "Medium"
        else:
            cc["confidence"] = "Low"

    converged = rhat_max < 1.05 and ess_min > 100
    return {
        "method": "bayesian_pymc",
        "contributions": contributions,
        "baseline_contribution": round(bl_contrib, 0),
        "baseline_pct": round(bl_contrib / max(total_rev, 1) * 100, 1),
        "total_revenue": round(total_rev, 0),
        "model_diagnostics": {
            "r_squared": round(r2, 4),
            "mape": round(mape, 2),
            "r_hat_max": round(rhat_max, 4),
            "converged": converged,
            "ess_min": round(ess_min, 0),
            "loo_cv": loo_score,
            "n_draws": n_draws,
            "n_tune": n_tune,
            "n_chains": n_chains,
            "target_accept": target_accept,
            "n_periods": T,
        },
        "fitted_values": y_pred.tolist(),
        "actual_values": revenue.tolist(),
        "channels": channels,
        "periods": [str(p) for p in data["periods"]],
    }

def fit_ols_mmm(data):
    """OLS fallback with non-negative least squares + bootstrap uncertainty.

    Uses NNLS (non-negative least squares) on the media predictors because
    channel spend columns are often collinear (all follow same seasonal pattern),
    and unconstrained OLS produces large positive/negative beta pairs that
    cancel in-sample but are meaningless for attribution. NNLS pins media
    coefficients >= 0 which is also the correct prior: media can't have
    negative contribution.

    Baseline and seasonal terms remain unconstrained (they can be negative).
    """
    from scipy.optimize import nnls
    from numpy.linalg import lstsq

    revenue = data["revenue"]
    channels = data["channels"]
    T = data["n_periods"]
    n_ch = len(channels)

    # --- Auto-select geometric decay per channel via correlation with revenue ---
    best_decays = {}
    for ch in channels:
        spend = data["spend_matrix"][ch]
        if spend.sum() == 0:
            best_decays[ch] = 0.0
            continue
        best_c, best_d = -1.0, 0.5
        for d in np.arange(0.05, 0.95, 0.05):
            ad = geometric_adstock(spend, d)
            if ad.std() > 0:
                corr = np.corrcoef(ad, revenue)[0, 1]
                if corr > best_c:
                    best_c = corr
                    best_d = d
        best_decays[ch] = round(best_d, 2)

    # --- Build media predictor matrix: Hill(Adstock(spend)) per channel ---
    # Scale spend per channel first so half-sat can live in [0, 1].
    spend_scales = np.array([
        max(data["spend_matrix"][ch].max(), 1e-10) for ch in channels
    ])
    X_media = np.zeros((T, n_ch))
    half_sats = {}
    for c, ch in enumerate(channels):
        spend_norm = data["spend_matrix"][ch] / spend_scales[c]
        ad = geometric_adstock(spend_norm, best_decays[ch])
        pos = ad[ad > 0]
        hs = float(np.median(pos)) if len(pos) > 0 else 0.5
        hs = max(hs, 1e-3)
        half_sats[ch] = hs
        X_media[:, c] = hill_saturation(ad, hs)

    sin_s = np.sin(2 * np.pi * data["month_nums"] / 12)
    cos_s = np.cos(2 * np.pi * data["month_nums"] / 12)

    # --- Two-stage fit ---
    # Stage 1: Fit baseline + seasonality alone via OLS, subtract from revenue.
    # Stage 2: Fit residual against NNLS(X_media) so betas are forced >= 0.
    X_base = np.column_stack([np.ones(T), sin_s, cos_s])
    base_coeffs, *_ = lstsq(X_base, revenue, rcond=None)
    baseline_const, gamma_sin, gamma_cos = base_coeffs
    revenue_residual = revenue - X_base @ base_coeffs

    # NNLS on residual. Residual may be negative, but NNLS needs predictors
    # mapped to a non-negative target sensibly. We shift the target so its
    # minimum is 0, fit, then shift the baseline constant by that amount.
    # (Equivalent to augmenting baseline_const post-hoc.)
    shift = float(-revenue_residual.min()) + 1.0 if revenue_residual.min() < 0 else 0.0
    y_nnls = revenue_residual + shift
    try:
        beta_means, nnls_resid = nnls(X_media, y_nnls, maxiter=5000)
    except Exception as e:
        logger.warning(f"NNLS failed ({e}); falling back to clipped lstsq")
        raw, *_ = lstsq(X_media, y_nnls, rcond=None)
        beta_means = np.maximum(raw, 0.0)

    # Shift gets absorbed into baseline_const.
    effective_baseline_const = float(baseline_const) - shift

    # Bootstrap uncertainty on betas
    n_boot = 100
    beta_boot = np.zeros((n_boot, n_ch))
    rng = np.random.default_rng(42)
    for b in range(n_boot):
        idx = rng.choice(T, T, replace=True)
        try:
            y_b = revenue_residual[idx] + shift
            bb, _ = nnls(X_media[idx], y_b, maxiter=5000)
            beta_boot[b] = bb
        except Exception:
            beta_boot[b] = beta_means
    beta_stds = beta_boot.std(axis=0)

    # Reconstruct fitted values
    y_pred = effective_baseline_const + gamma_sin * sin_s + gamma_cos * cos_s + X_media @ beta_means

    # Contributions: each channel's full sum of (beta * hill(adstock)) over T.
    contributions = {}
    total_media = 0.0
    for c, ch in enumerate(channels):
        contrib = float(beta_means[c] * X_media[:, c].sum())
        contrib = max(0.0, contrib)
        total_media += contrib
        contributions[ch] = {
            "contribution": round(contrib, 0),
            "beta_mean": round(float(beta_means[c]), 4),
            "beta_std": round(float(beta_stds[c]), 4),
            "decay_mean": best_decays[ch],
            "half_saturation": half_sats[ch],
            "spend": round(float(data["spend_matrix"][ch].sum()), 0),
            "_spend_scale": float(spend_scales[c]),
        }

    total_rev = float(revenue.sum())
    bl = max(0.0, total_rev - total_media)

    for ch in channels:
        cc = contributions[ch]
        cc["contribution_pct"] = round(cc["contribution"] / max(total_rev, 1) * 100, 1)
        cc["mmm_roas"] = round(cc["contribution"] / max(cc["spend"], 1), 2)
        # Bootstrap CI half-width over mean, as a rough confidence proxy
        ci_w = cc["beta_std"] / max(cc["beta_mean"], 1e-6)
        cc["confidence"] = "High" if ci_w < 0.3 else ("Medium" if ci_w < 0.6 else "Low")

    return {
        "method": "ols_nnls_bootstrap",
        "contributions": contributions,
        "baseline_contribution": round(bl, 0),
        "baseline_pct": round(bl / max(total_rev, 1) * 100, 1),
        "total_revenue": round(total_rev, 0),
        "model_diagnostics": {
            "r_squared": round(float(r2_score(revenue, y_pred)), 4),
            "mape": round(float(mean_absolute_percentage_error(revenue, y_pred) * 100), 2),
            "n_bootstrap": n_boot,
            "n_periods": T,
            "method_note": "Non-negative least squares on Hill(Adstock(spend)) with "
                           "two-stage baseline+seasonal decomposition. Betas >= 0 by construction.",
        },
        "fitted_values": y_pred.tolist(),
        "actual_values": revenue.tolist(),
        "channels": channels,
        "periods": [str(p) for p in data["periods"]],
    }

def fit_mle_mmm(data):
    """MLE fallback using scipy.optimize.

    All optimization happens in a scaled revenue space (revenue / rev_scale)
    so parameter magnitudes are O(1) and L-BFGS-B gradients are well-conditioned.
    Spend is already normalized to [0, ~1] per channel via spend_scales.
    After optimization, scaled betas are multiplied back by rev_scale to
    recover dollar contributions.

    Why scaling matters: without it, warm-starting betas from OLS on raw
    revenue produces initial values ~1e7, which combined with spend_scales
    ~1e6 gives contributions ~1e13 — dwarfing actual revenue ~1e8 and
    putting the optimizer in a basin it can't escape.
    """
    from scipy.optimize import minimize as sp_minimize
    from numpy.linalg import lstsq

    revenue = data["revenue"]
    channels = data["channels"]
    n_ch = len(channels)
    T = data["n_periods"]
    trend = data["trend"] / (T + 1)
    sin_s = np.sin(2 * np.pi * data["month_nums"] / 12)
    cos_s = np.cos(2 * np.pi * data["month_nums"] / 12)

    spend_raw = np.column_stack([data["spend_matrix"][ch] for ch in channels])
    spend_scales = spend_raw.max(axis=0) + 1e-10
    spend_normed = spend_raw / spend_scales  # now in [0, 1]

    # Scale revenue to O(1) for numerical stability.
    rev_scale = float(np.abs(revenue).mean()) + 1e-10
    rev_scaled = revenue / rev_scale

    # --- Warm start via OLS on scaled revenue and a pre-saturated spend proxy ---
    # Use a mild Hill saturation with half-sat at each channel's median adstock
    # level, so the OLS coefficients are in the right ballpark for the MLE basis.
    proxy_X = np.zeros((T, n_ch))
    proxy_hs = np.zeros(n_ch)
    proxy_decay = np.full(n_ch, 0.5)
    for c in range(n_ch):
        ad = geometric_adstock(spend_normed[:, c], proxy_decay[c])
        # Pick half-sat near the median of positive adstock so the proxy isn't
        # flat-lined at 0 or 1 (either would make the coefficient meaningless).
        pos = ad[ad > 0]
        proxy_hs[c] = float(np.median(pos)) if len(pos) > 0 else 0.5
        proxy_X[:, c] = hill_saturation(ad, max(proxy_hs[c], 1e-6))

    X_ols = np.column_stack([np.ones(T), trend, proxy_X, sin_s, cos_s])
    c_ols, *_ = lstsq(X_ols, rev_scaled, rcond=None)
    # c_ols layout: [baseline, trend, beta_1..beta_n, gamma_sin, gamma_cos]

    baseline_init = float(c_ols[0])
    trend_init = float(c_ols[1])
    beta_init = np.maximum(c_ols[2 : 2 + n_ch], 0.01)  # ensure positive for warm start
    gamma_sin_init = float(c_ols[-2])
    gamma_cos_init = float(c_ols[-1])
    residuals = rev_scaled - X_ols @ c_ols
    sigma_init = float(np.std(residuals) + 1e-6)

    # --- MLE on scaled revenue ---
    # Parameterization:
    #   p[0]  = baseline (unconstrained, scaled)
    #   p[1]  = trend coefficient (unconstrained, scaled)
    #   p[2]  = gamma_sin (scaled)
    #   p[3]  = gamma_cos (scaled)
    #   p[4]  = log_sigma (log of scaled residual sd)
    #   p[5..5+n_ch]           = log(beta_c)  -> beta_c = exp(...) positive by construction
    #   p[5+n_ch..5+2*n_ch]    = logit(decay) -> decay in (0,1)
    #   p[5+2*n_ch..5+3*n_ch]  = log(half_sat) -> half_sat positive
    def unpack(p):
        bl = p[0]; tc = p[1]; gs = p[2]; gc = p[3]; ls = p[4]
        betas = np.exp(np.clip(p[5 : 5 + n_ch], -10, 10))
        decays = 1.0 / (1.0 + np.exp(-np.clip(p[5 + n_ch : 5 + 2 * n_ch], -10, 10)))
        hs = np.exp(np.clip(p[5 + 2 * n_ch : 5 + 3 * n_ch], -8, 4))
        return bl, tc, gs, gc, ls, betas, decays, hs

    def predict_scaled(p):
        bl, tc, gs, gc, _, betas, decays, hs = unpack(p)
        mu = bl + tc * trend + gs * sin_s + gc * cos_s
        for c in range(n_ch):
            ad = geometric_adstock(spend_normed[:, c], decays[c])
            mu = mu + betas[c] * hill_saturation(ad, hs[c])
        return mu

    def neg_ll(p):
        _, _, _, _, ls, betas, _, _ = unpack(p)
        mu = predict_scaled(p)
        sig = np.exp(np.clip(ls, -10, 10))
        res = rev_scaled - mu
        nll = 0.5 * T * np.log(2 * np.pi) + T * np.log(sig) + 0.5 * np.sum(res ** 2) / (sig ** 2)
        # L2 on betas is now at scaled magnitude (~O(1)), so reg strength is meaningful.
        nll += 0.1 * np.sum(betas ** 2)
        return nll

    # Build warm-start vector
    x0 = np.zeros(5 + 3 * n_ch)
    x0[0] = baseline_init
    x0[1] = trend_init
    x0[2] = gamma_sin_init
    x0[3] = gamma_cos_init
    x0[4] = np.log(max(sigma_init, 1e-4))
    x0[5 : 5 + n_ch] = np.log(beta_init)
    x0[5 + n_ch : 5 + 2 * n_ch] = 0.0  # logit(0.5) = 0
    x0[5 + 2 * n_ch : 5 + 3 * n_ch] = np.log(np.maximum(proxy_hs, 1e-3))

    # Bounds for L-BFGS-B keep the optimizer inside sensible regions.
    bounds = (
        [(None, None)] * 4  # baseline, trend, gammas
        + [(-5.0, 2.0)]  # log_sigma in [~0.007, ~7.4] -- revenue is scaled O(1)
        + [(-8.0, 4.0)] * n_ch  # log(beta) -- betas in [~3e-4, ~55]
        + [(-6.0, 6.0)] * n_ch  # logit(decay) -- decay stays inside (0,1)
        + [(-6.0, 3.0)] * n_ch  # log(half_sat) -- half_sat in [~0.0025, ~20]
    )

    best_res = None
    best_nll = np.inf
    rng = np.random.default_rng(42)
    # MLE convergence on 48-period mock data typically happens in <100 iterations
    # from a good warm start. L-BFGS-B with finite-difference gradients needs
    # ~30 function evals per step (one per parameter dimension), so maxiter=200
    # = ~6000 evals is plenty. We do 2 restarts: the warm start, and one
    # jittered restart to check we're not in a local minimum.
    #
    # ftol=1e-5 is looser than default (2e-9); on scaled revenue (O(1)), this
    # corresponds to resolving the log-likelihood to ~5 decimal places, which
    # changes R² in the 5th decimal. Not worth the extra iterations.
    for r in range(2):
        xr = x0.copy()
        if r > 0:
            xr = xr + rng.normal(0, 0.2, size=len(xr))
        try:
            res = sp_minimize(
                neg_ll, xr, method="L-BFGS-B", bounds=bounds,
                options={"maxiter": 200, "ftol": 1e-5, "maxfun": 6000},
            )
            if np.isfinite(res.fun) and res.fun < best_nll:
                best_nll = res.fun
                best_res = res
        except Exception as e:
            logger.debug(f"MLE restart {r} failed: {e}")

    if best_res is None:
        raise ValueError("MLE failed to converge from all restarts")

    p = best_res.x
    _, _, _, _, _, betas_scaled, decays, hs_vals = unpack(p)

    # Predict in scaled space, then unscale back to revenue units.
    y_pred_scaled = predict_scaled(p)
    y_pred = y_pred_scaled * rev_scale

    # Contributions: beta_scaled * sat_c(t) is contribution per period in scaled revenue.
    # Multiply by rev_scale to get dollars.
    contributions = {}
    total_media = 0.0
    for c, ch in enumerate(channels):
        spend = data["spend_matrix"][ch]
        ad = geometric_adstock(spend_normed[:, c], decays[c])
        sat = hill_saturation(ad, hs_vals[c])
        contrib_per_period_scaled = betas_scaled[c] * sat
        contrib_dollars = float(contrib_per_period_scaled.sum()) * rev_scale
        contrib_dollars = max(0.0, contrib_dollars)
        total_media += contrib_dollars
        # beta_dollar: per-unit-scaled-spend contribution in dollars, comparable to Bayesian output
        beta_dollar = float(betas_scaled[c]) * rev_scale
        contributions[ch] = {
            "contribution": round(contrib_dollars, 0),
            "beta_mean": round(beta_dollar, 4),
            "decay_mean": round(float(decays[c]), 3),
            "half_saturation": round(float(hs_vals[c]), 4),
            "spend": round(float(spend.sum()), 0),
            "adstock_type": "geometric",
            # _spend_scale stored so _finalize can evaluate saturation
            # in the same normalized space the model was fit in.
            "_spend_scale": float(spend_scales[c]),
        }

    total_rev = float(revenue.sum())
    bl_dollars = max(0.0, total_rev - total_media)

    # Guard against pathological fits. If R² is implausibly bad, the caller's
    # auto-chain will discard and fall back to OLS -- but we fail LOUDLY here
    # so nothing silently shows a broken model.
    r2 = float(r2_score(revenue, y_pred))
    mape = float(mean_absolute_percentage_error(revenue, y_pred) * 100)
    if r2 < -1.0 or not np.isfinite(r2):
        raise ValueError(
            f"MLE produced nonsensical fit (R²={r2:.3f}, MAPE={mape:.1f}%). "
            "Discarding and falling back."
        )

    for ch in channels:
        cc = contributions[ch]
        cc["contribution_pct"] = round(cc["contribution"] / max(total_rev, 1) * 100, 1)
        cc["mmm_roas"] = round(cc["contribution"] / max(cc["spend"], 1), 2)
        cc["confidence"] = "Medium"

    return {
        "method": "mle_scipy",
        "contributions": contributions,
        "baseline_contribution": round(bl_dollars, 0),
        "baseline_pct": round(bl_dollars / max(total_rev, 1) * 100, 1),
        "total_revenue": round(total_rev, 0),
        "model_diagnostics": {
            "r_squared": round(r2, 4),
            "mape": round(mape, 2),
            "converged": bool(best_res.success),
            "n_restarts": 2,
            "n_periods": T,
            "final_nll": round(float(best_res.fun), 4),
            "note": "MLE (L-BFGS-B) on scaled revenue with L2 regularization. "
                    "Positivity on betas via log-reparameterization.",
        },
        "fitted_values": y_pred.tolist(),
        "actual_values": revenue.tolist(),
        "channels": channels,
        "periods": [str(p) for p in data["periods"]],
    }

def run_mmm(df, method="auto", n_draws=500, n_chains=4, n_tune=None):
    """Public API: Bayesian → MLE → OLS fallback chain.

    n_draws defaults to 500 (with 500 tune and 4 chains = 2000 post-tune
    samples). That's enough for stable posterior summaries on the channel
    counts we typically see (~8 channels, ~48 periods) while keeping a
    single fit under ~90 seconds on a dev laptop. Pass a larger n_draws
    if you need tighter HDI intervals for a final report.

    n_chains / n_tune: passthrough knobs for the Bayesian fit. Useful
    when the caller knows they only need a quick directional answer
    (e.g., background demo fits use n_chains=2, n_tune=300).
    """
    data = prepare_mmm_data(df)
    if data["n_periods"]<6: logger.warning(f"Only {data['n_periods']} periods — MMM needs 12+ for reliability")
    warnings_list = []
    T = data["n_periods"]
    if T<12: warnings_list.append(f"Only {T} periods. MMM needs 12+ for reliability.")
    elif T<24: warnings_list.append(f"{T} periods. Curves may overfit. 24+ recommended.")
    elif T<36: warnings_list.append(f"{T} periods. OLS/MLE solid. Bayesian needs 36+.")
    result = None
    if method == "auto":
        if T >= 24:
            try:
                bayes_kwargs = {"n_draws": n_draws, "n_chains": n_chains}
                if n_tune is not None:
                    bayes_kwargs["n_tune"] = n_tune
                candidate = fit_bayesian_mmm(data, **bayes_kwargs)
                diag = candidate["model_diagnostics"]
                # Only accept Bayesian if the chains actually converged. A
                # Bayesian result with r-hat > 1.05 or ESS < 100 is worse than
                # a clean MLE because the reported HDIs and point estimates are
                # untrustworthy.
                if diag.get("converged"):
                    result = candidate
                    logger.info(
                        f"Bayesian MMM: R²={diag['r_squared']:.3f} "
                        f"r-hat={diag['r_hat_max']:.3f} ESS={diag['ess_min']}"
                    )
                else:
                    logger.warning(
                        f"Bayesian sampled but did not converge "
                        f"(r-hat={diag.get('r_hat_max')}, ESS={diag.get('ess_min')}). "
                        "Discarding and trying MLE."
                    )
            except Exception as e:
                logger.warning(f"Bayesian failed ({e}), trying MLE")
        if result is None:
            try:
                candidate = fit_mle_mmm(data)
                r2 = candidate["model_diagnostics"]["r_squared"]
                if r2 < 0:
                    logger.warning(
                        f"MLE R²={r2:.3f} — negative, discarding. Falling back to OLS."
                    )
                else:
                    result = candidate
                    logger.info(f"MLE MMM: R²={r2:.3f}")
            except Exception as e:
                logger.warning(f"MLE failed ({e}), OLS fallback")
        if result is None:
            result = fit_ols_mmm(data)
            logger.info(
                f"OLS MMM: R²={result['model_diagnostics']['r_squared']:.3f}"
            )
    elif method == "bayesian":
        bayes_kwargs = {"n_draws": n_draws, "n_chains": n_chains}
        if n_tune is not None:
            bayes_kwargs["n_tune"] = n_tune
        result = _finalize(fit_bayesian_mmm(data, **bayes_kwargs))
    elif method == "mle":
        result = _finalize(fit_mle_mmm(data))
    elif method == "ols":
        result = _finalize(fit_ols_mmm(data))
    else:
        raise ValueError(f"Unknown method: {method}")
    result["data_warnings"] = warnings_list
    # Adstock selection per channel
    adstock_sel = {}
    for ch in data["channels"]:
        at,ap,ac = select_best_adstock(data["spend_matrix"][ch], data["revenue"])
        adstock_sel[ch] = {"best_type":at,"params":ap,"correlation":ac}
    result["adstock_selection"] = adstock_sel
    return _finalize(result)

def _finalize(r):
    if "contributions" not in r: return r
    total_rev = r.get("total_revenue", 1)
    total_media = sum(c["contribution"] for c in r["contributions"].values())
    # Guard only against truly pathological fits. A well-fitting MMM on
    # real data routinely shows media at 60-85% of revenue -- that's the
    # defensible range. Forcing everything to 70% masks real signal and
    # is the kind of number-fudging Partners (rightly) criticize.
    #
    # We ONLY cap when media > 100% of revenue, which is mathematically
    # impossible and indicates a broken fit (the old OLS-lstsq bug
    # regularly produced 300%). The cap target when fired: 80%, which
    # leaves headroom for a nonzero baseline and is still a common
    # real-world upper bound.
    if total_media > total_rev * 1.0 and total_rev > 0:
        target_media = total_rev * 0.80
        scale = target_media / max(total_media, 1)
        for ch, cc in r["contributions"].items():
            cc["contribution"] = round(cc["contribution"] * scale, 0)
            cc["contribution_pct"] = round(cc["contribution"] / max(total_rev, 1) * 100, 1)
            cc["mmm_roas"] = round(cc["contribution"] / max(cc["spend"], 1), 2)
            cc["_normalized"] = True
        r["baseline_contribution"] = round(
            total_rev - sum(c["contribution"] for c in r["contributions"].values()), 0
        )
        r["baseline_pct"] = round(r["baseline_contribution"] / max(total_rev, 1) * 100, 1)
        if "model_diagnostics" in r:
            r["model_diagnostics"]["contribution_normalized"] = True
            r["model_diagnostics"]["raw_media_pct"] = round(
                total_media / max(total_rev, 1) * 100, 1
            )
    # Incremental ROAS (marginal return at current spend).
    # We evaluate saturation in the SAME space the model was fit in. OLS and MLE
    # both fit hill_saturation() on normalized spend (spend / spend_scale), so
    # their half_saturation values live in normalized-spend units. Bayesian
    # likewise; _spend_scale is stored on the contribution dict by all paths.
    # Falling back to dollar-space if the field is missing keeps old callers alive.
    inc_roas = {}
    for ch, cc in r["contributions"].items():
        beta = cc.get("beta_mean", 0)
        hs = cc.get("half_saturation", 0.5)
        spend = cc.get("spend", 0)
        decay = cc.get("decay_mean", 0.5)
        spend_scale = cc.get("_spend_scale")
        if spend > 0 and beta > 0:
            avg_monthly = spend / 12
            # Steady-state adstock from a constant monthly input.
            ad_cur_dollars = avg_monthly / (1 - decay + 1e-10)
            ad_plus_dollars = (avg_monthly * 1.1) / (1 - decay + 1e-10)
            # Convert to the space the Hill function was fit in.
            if spend_scale and spend_scale > 0:
                ad_cur = ad_cur_dollars / spend_scale
                ad_plus = ad_plus_dollars / spend_scale
            else:
                ad_cur = ad_cur_dollars
                ad_plus = ad_plus_dollars
            sat_cur = float(hill_saturation(np.array([ad_cur]), max(hs, 1e-6))[0])
            sat_plus = float(hill_saturation(np.array([ad_plus]), max(hs, 1e-6))[0])
            # Incremental contribution for +10% spend, extrapolated from
            # this channel's current proportional contribution.
            contrib_per_period = cc["contribution"] / 12
            if sat_cur > 1e-9:
                inc_rev = contrib_per_period * (sat_plus - sat_cur) / sat_cur * 12
            else:
                inc_rev = 0.0
            inc_spend = avg_monthly * 0.1 * 12
            inc_roas[ch] = {
                "incremental_roas": round(inc_rev / max(inc_spend, 1), 2),
                "saturation_pct": round(sat_cur * 100, 1),
                "current_spend": round(spend, 0),
                "headroom": "High" if sat_cur < 0.4 else ("Medium" if sat_cur < 0.7 else "Low"),
            }
        else:
            inc_roas[ch] = {"incremental_roas": 0, "saturation_pct": 0, "headroom": "N/A"}
    r["incremental_roas"] = inc_roas
    # Ranked
    sc = sorted(r["contributions"].items(), key=lambda x: x[1]["contribution"], reverse=True)
    r["ranked_contributions"] = [{"rank":i+1,"channel":ch,**info} for i,(ch,info) in enumerate(sc)]
    return r
