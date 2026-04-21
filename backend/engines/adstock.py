"""
Adstock & Carryover Models — Production Grade
===============================================
Geometric decay: adstock[t] = x[t] + λ·adstock[t-1]
Weibull decay: flexible shape for delayed peak effects (TV, events)
Hill saturation: y = x^S / (K^S + x^S)
Fitting: scipy.optimize.minimize for decay + half-saturation parameters.

Libraries: scipy.optimize.minimize, numpy, pandas
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize, differential_evolution
from typing import Dict, Optional

def geometric_adstock(x, decay=0.5, max_lag=8):
    out = np.zeros_like(x, dtype=float); out[0] = x[0]
    for t in range(1, len(x)): out[t] = x[t] + decay * out[t-1]
    return out

def weibull_adstock(x, shape=2.0, scale=1.0, max_lag=12):
    lags = np.arange(max_lag) + 1e-10
    kernel = (shape/scale) * (lags/scale)**(shape-1) * np.exp(-(lags/scale)**shape)
    kernel = np.nan_to_num(kernel); ks = kernel.sum()
    kernel = kernel/ks if ks > 0 else np.ones(max_lag)/max_lag
    return np.convolve(x, kernel, mode='full')[:len(x)]

def hill_saturation(x, half_saturation, slope=1.0):
    x_safe = np.maximum(x, 1e-10)
    return x_safe**slope / (half_saturation**slope + x_safe**slope)

def fit_adstock_params(spend, revenue, adstock_type="geometric"):
    """
    Fit adstock decay (and optionally Hill saturation K) by maximizing
    correlation between adstocked-saturated spend and revenue.
    Uses scipy differential_evolution for global optimization.
    """
    if spend.sum() == 0 or len(spend) < 3:
        return {"decay": 0.0, "half_saturation": 1.0, "correlation": 0.0, "carryover_pct": 0.0}

    def neg_corr(params):
        if adstock_type == "geometric":
            decay = params[0]; half_sat = params[1]
            ad = geometric_adstock(spend, decay)
        else:
            shape, scale, half_sat = params[0], params[1], params[2]
            ad = weibull_adstock(spend, shape, scale)
        sat = hill_saturation(ad, half_sat)
        if sat.std() == 0: return 0
        return -np.corrcoef(sat, revenue)[0, 1]

    if adstock_type == "geometric":
        bounds = [(0.01, 0.95), (1, float(np.median(spend[spend > 0])*5 + 1))]
    else:
        bounds = [(0.5, 5.0), (0.5, 5.0), (1, float(np.median(spend[spend > 0])*5 + 1))]

    try:
        result = differential_evolution(neg_corr, bounds, seed=42, maxiter=200, tol=1e-6)
        best_corr = -result.fun
        if adstock_type == "geometric":
            decay, half_sat = result.x
            ad = geometric_adstock(spend, decay)
            carryover = (ad.sum() - spend.sum()) / max(spend.sum(), 1) * 100
            return {"decay": round(decay, 3), "half_saturation": round(half_sat, 2),
                    "correlation": round(best_corr, 4), "carryover_pct": round(carryover, 1),
                    "effective_lag": round(1/(1-decay), 1) if decay < 1 else 99}
        else:
            shape, scale, half_sat = result.x
            return {"shape": round(shape, 3), "scale": round(scale, 3),
                    "half_saturation": round(half_sat, 2), "correlation": round(best_corr, 4)}
    except Exception as e:
        return {"decay": 0.5, "half_saturation": 1.0, "correlation": 0.0, "error": str(e)}

def _channel_adstock_profile(channel_name: str, attribution_basis: str = "click"):
    """
    Pick adstock type and parameter priors per channel.

    Digital channels (click-based) have near-instant response — people
    click the ad and convert the same day. Geometric with low decay (0.1-0.3)
    captures this.

    Broadcast offline (TV, radio) has delayed peak effect — TV spots shown
    in week 1 drive inquiries in weeks 2-4 (reach builds + consideration
    time). Weibull with shape~2 and scale~2-3 captures the delayed peak.

    Direct-response offline (events, direct_mail, call_center) falls between.
    Events have a clear bump during and immediately after; direct mail has
    a longer tail (recipients pull out the catalog weeks later).

    Returns (adstock_type, prior_decay, prior_shape, prior_scale, max_lag).
    The fitter still optimizes within bounds; these are starting points
    and type selection.
    """
    # Broadcast — delayed peak, long tail
    if channel_name in ("tv_national", "radio"):
        return {
            "adstock_type": "weibull",
            "prior_decay": None,
            "prior_shape": 2.0,      # bell curve with peak at scale
            "prior_scale": 3.0,      # peak ~3 weeks after spend
            "max_lag": 12,
            "expected_carryover_pct": 55,  # substantial carryover is expected
        }
    if channel_name == "ooh":
        return {
            "adstock_type": "weibull",
            "prior_decay": None,
            "prior_shape": 1.8,
            "prior_scale": 2.5,
            "max_lag": 10,
            "expected_carryover_pct": 45,
        }
    # Events — spike then decay
    if channel_name == "events":
        return {
            "adstock_type": "weibull",
            "prior_decay": None,
            "prior_shape": 2.5,
            "prior_scale": 1.5,
            "max_lag": 8,
            "expected_carryover_pct": 35,
        }
    # Direct mail — long tail (recipients act weeks later)
    if channel_name == "direct_mail":
        return {
            "adstock_type": "geometric",
            "prior_decay": 0.65,
            "prior_shape": None,
            "prior_scale": None,
            "max_lag": 10,
            "expected_carryover_pct": 50,
        }
    # Call center — operational, near-immediate (calls connect to lead)
    if channel_name == "call_center":
        return {
            "adstock_type": "geometric",
            "prior_decay": 0.2,
            "prior_shape": None,
            "prior_scale": None,
            "max_lag": 4,
            "expected_carryover_pct": 10,
        }
    # Digital channels — near-instant response
    return {
        "adstock_type": "geometric",
        "prior_decay": 0.25,
        "prior_shape": None,
        "prior_scale": None,
        "max_lag": 6,
        "expected_carryover_pct": 15,
    }


def compute_channel_adstock(df, adstock_type="auto"):
    """Fit adstock params for each channel using channel-aware defaults.

    When adstock_type="auto" (default), each channel uses the adstock type
    appropriate for its attribution basis — Weibull for broadcast, geometric
    for digital and direct response. Pass adstock_type="geometric" or
    "weibull" to force a single type across all channels (legacy behavior).

    Returns dict of fitted params + transformed series, with an added
    `channel_profile` block describing why each channel got the treatment
    it did.
    """
    results = {}
    time_col = "month" if "month" in df.columns else "date"
    # Detect attribution_basis per channel from the data (added by mock_data
    # generator in Week 2). Falls back to "click" if column is missing.
    has_basis = "attribution_basis" in df.columns
    for ch in df["channel"].unique():
        ch_data = df[df["channel"] == ch]
        monthly = ch_data.groupby(time_col).agg(
            spend=("spend", "sum"), revenue=("revenue", "sum")
        ).reset_index().sort_values(time_col)
        spend = monthly["spend"].values.astype(float)
        rev = monthly["revenue"].values.astype(float)

        basis = "click"
        if has_basis and len(ch_data) > 0:
            basis = str(ch_data["attribution_basis"].iloc[0])
        profile = _channel_adstock_profile(ch, basis)

        # Pick the adstock type — respect caller override if not "auto"
        effective_type = (profile["adstock_type"] if adstock_type == "auto"
                          else adstock_type)

        params = fit_adstock_params(spend, rev, effective_type)
        if effective_type == "geometric":
            ad = geometric_adstock(spend, params.get("decay", 0.5))
        else:
            ad = weibull_adstock(spend, params.get("shape", 2.0), params.get("scale", 1.0))

        results[ch] = {
            "params": params,
            "original_spend": spend.tolist(),
            "adstocked_spend": ad.tolist(),
            "revenue": rev.tolist(),
            "periods": monthly[time_col].tolist(),
            # Channel profile for transparency
            "channel_profile": {
                "adstock_type_used": effective_type,
                "attribution_basis": basis,
                "expected_carryover_pct": profile["expected_carryover_pct"],
                "notes": _profile_notes(ch, profile),
            },
        }
    return results


def _profile_notes(channel_name, profile):
    """Return human-readable explanation of why this channel got this adstock."""
    if profile["adstock_type"] == "weibull":
        if channel_name in ("tv_national", "radio"):
            return ("Broadcast media uses Weibull adstock — TV/radio drives "
                    "delayed response peaking ~3 weeks after airing as "
                    "consideration accumulates.")
        if channel_name == "ooh":
            return ("OOH uses Weibull adstock — billboard/transit reach builds "
                    "gradually over ~2-3 weeks of repeated exposure.")
        if channel_name == "events":
            return ("Events use Weibull adstock — clear response bump during "
                    "and in the 1-2 weeks following each event.")
    if profile["adstock_type"] == "geometric":
        if channel_name == "direct_mail":
            return ("Direct mail uses geometric adstock with slow decay — "
                    "recipients often respond weeks after receiving the piece.")
        if channel_name == "call_center":
            return ("Call center uses geometric adstock with fast decay — "
                    "inbound calls correlate tightly with same-week operational spend.")
        return ("Digital channel uses geometric adstock with fast decay — "
                "click-to-conversion is near-immediate.")
    return ""
