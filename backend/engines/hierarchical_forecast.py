"""
Hierarchical Forecasting — Production Grade
=============================================
Forecasts at region × channel × campaign level, then reconciles to total.
Uses Prophet per series with top-down reconciliation.

Libraries: prophet (per-series forecast), numpy, pandas
"""
import numpy as np
import pandas as pd
from typing import Dict
import logging
logger = logging.getLogger(__name__)

def run_hierarchical_forecast(df, metric="revenue", periods=12, group_cols=None):
    """Forecast at granular level, reconcile to total."""
    from engines.forecasting import run_forecast
    
    if group_cols is None: group_cols = ["channel"]
    time_col = "month" if "month" in df.columns else "date"
    
    # Total forecast
    total_fc = run_forecast(df, metric, periods)
    total_pred = sum(total_fc.get("forecast",{}).get("predicted",[0]))
    
    # Per-group forecasts
    group_forecasts = {}
    group_totals = {}
    for name, grp in df.groupby(group_cols):
        key = name if isinstance(name, str) else "_".join(str(n) for n in name)
        try:
            fc = run_forecast(grp, metric, periods, method="auto")
            pred_sum = sum(fc.get("forecast",{}).get("predicted",[0]))
            group_forecasts[key] = fc
            group_totals[key] = pred_sum
        except Exception as e:
            logger.warning(f"Forecast failed for {key}: {e}")
            group_totals[key] = 0
    
    # Top-down reconciliation: scale group forecasts to match total
    raw_total = sum(group_totals.values()) or 1
    scale_factor = total_pred / raw_total if raw_total > 0 else 1
    
    reconciled = {}
    for key, fc in group_forecasts.items():
        preds = fc.get("forecast",{}).get("predicted",[])
        reconciled[key] = {
            "raw_forecast": preds,
            "reconciled_forecast": [round(p * scale_factor) for p in preds],
            "raw_total": round(group_totals.get(key,0),0),
            "reconciled_total": round(group_totals.get(key,0) * scale_factor, 0),
            "method": fc.get("method","unknown"),
        }
    
    return {
        "total_forecast": total_fc,
        "group_forecasts": reconciled,
        "reconciliation": {"method":"top_down","scale_factor":round(scale_factor,4),
            "raw_group_sum":round(raw_total,0),"total_forecast":round(total_pred,0)},
        "group_columns": group_cols,
    }
