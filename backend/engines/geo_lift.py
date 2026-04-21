"""
Geo-Lift / Incrementality Testing Engine
==========================================
Measures true incremental impact of marketing by comparing test vs control regions.
Uses Synthetic Control Method via statsmodels OLS to construct counterfactual.

Libraries: statsmodels (OLS for synthetic control), scipy.stats (significance testing), numpy, pandas
"""
import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, List, Optional
import logging
logger = logging.getLogger(__name__)

def synthetic_control(df, test_region, control_regions, metric="revenue",
                      pre_period_end=None, intervention_col="channel"):
    """
    Synthetic Control Method: builds a weighted combination of control regions
    to match the test region's pre-period behavior, then measures the gap
    (= incremental effect) during the treatment period.
    
    Uses OLS to find control weights that best predict test region in pre-period.
    """
    try:
        from statsmodels.api import OLS, add_constant
    except ImportError:
        raise ImportError("statsmodels required for synthetic control")

    time_col = "month" if "month" in df.columns else "date"
    
    # Aggregate by region × time
    region_ts = {}
    for reg in [test_region] + control_regions:
        reg_data = df[df["region"] == reg].groupby(time_col)[metric].sum().reset_index()
        reg_data = reg_data.sort_values(time_col)
        region_ts[reg] = reg_data.set_index(time_col)[metric]
    
    # Align all regions to same time index
    all_idx = region_ts[test_region].index
    if pre_period_end is None:
        pre_period_end = all_idx[len(all_idx) * 2 // 3]  # first 2/3 = pre-period
    
    pre_mask = all_idx <= pre_period_end
    post_mask = ~pre_mask
    
    if post_mask.sum() == 0:
        return {"error": "No post-intervention periods available"}
    
    # Build control matrix (pre-period)
    y_pre = region_ts[test_region][pre_mask].values
    X_pre = np.column_stack([region_ts[r][pre_mask].values for r in control_regions if r in region_ts])
    
    if X_pre.shape[1] == 0:
        return {"error": "No valid control regions"}
    
    # Fit OLS: test_pre ~ weighted sum of controls_pre
    X_pre_c = add_constant(X_pre)
    model = OLS(y_pre, X_pre_c).fit()
    weights = model.params[1:]  # exclude intercept
    
    # Predict counterfactual for full period
    X_all = np.column_stack([region_ts[r].values for r in control_regions if r in region_ts])
    X_all_c = add_constant(X_all)
    counterfactual = model.predict(X_all_c)
    
    actual_post = region_ts[test_region][post_mask].values
    cf_post = counterfactual[post_mask.values]
    
    # Incremental effect
    incremental = actual_post - cf_post
    total_lift = float(incremental.sum())
    avg_lift_pct = float(np.mean(incremental / np.maximum(cf_post, 1)) * 100)
    
    # Statistical significance (paired t-test)
    if len(incremental) > 1:
        t_stat, p_value = stats.ttest_1samp(incremental, 0)
        significant = p_value < 0.05
    else:
        t_stat, p_value, significant = 0, 1.0, False
    
    # Pre-period fit quality
    pre_r2 = float(model.rsquared)
    pre_mape = float(np.mean(np.abs((y_pre - model.fittedvalues) / np.maximum(y_pre, 1))) * 100)
    
    return {
        "test_region": test_region,
        "control_regions": control_regions,
        "method": "synthetic_control_ols",
        "results": {
            "total_incremental_revenue": round(total_lift, 0),
            "avg_lift_pct": round(avg_lift_pct, 1),
            "p_value": round(float(p_value), 4),
            "significant": significant,
            "t_statistic": round(float(t_stat), 3),
            "confidence_level": "95%",
        },
        "diagnostics": {
            "pre_period_r_squared": round(pre_r2, 4),
            "pre_period_mape": round(pre_mape, 2),
            "n_pre_periods": int(pre_mask.sum()),
            "n_post_periods": int(post_mask.sum()),
            "control_weights": {r: round(float(w), 4) for r, w in zip(control_regions, weights)},
        },
        "series": {
            "periods": [str(p) for p in all_idx],
            "actual": region_ts[test_region].values.tolist(),
            "counterfactual": counterfactual.tolist(),
            "incremental": (region_ts[test_region].values - counterfactual).tolist(),
        },
    }

def run_geo_lift(df, test_region=None, control_regions=None, metric="revenue"):
    """Public API for geo-lift analysis."""
    regions = df["region"].unique().tolist() if "region" in df.columns else []
    if len(regions) < 2:
        return {"error": "Need at least 2 regions for geo-lift testing"}
    if test_region is None:
        test_region = regions[0]
    if control_regions is None:
        control_regions = [r for r in regions if r != test_region]
    return synthetic_control(df, test_region, control_regions, metric)
