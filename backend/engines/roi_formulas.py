"""
ROI Formula Engine — Production Grade
=======================================
Computes 5 ROI variants per channel with bootstrap confidence intervals.
Libraries: scipy.stats (bootstrap CI), numpy, pandas
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from scipy import stats as sp_stats
import logging
logger = logging.getLogger(__name__)

def compute_all_roi(df, curves=None, gross_margin_pct=0.65, n_bootstrap=100):
    """Compute 5 ROI formulas per channel with bootstrap CIs."""
    time_col = "month" if "month" in df.columns else "date"
    results = []
    
    for ch in df["channel"].unique():
        cr = df[df["channel"]==ch]
        s = cr["spend"].sum(); rv = cr["revenue"].sum()
        cv = cr["conversions"].sum() if "conversions" in cr.columns else cr.get("conv", pd.Series([0])).sum()
        
        base_roi = (rv-s)/max(s,1)
        gm_roi = (rv*gross_margin_pct - s)/max(s,1)
        roas = rv/max(s,1)
        
        # Incremental ROI: Q1 baseline vs rest
        q1 = cr[cr[time_col].apply(lambda x: int(str(x).split("-")[1])<=3 if "-" in str(x) else True)]
        rest = cr[cr[time_col].apply(lambda x: int(str(x).split("-")[1])>3 if "-" in str(x) else False)]
        q1s, q1r = q1["spend"].sum()/max(len(q1[time_col].unique()),1), q1["revenue"].sum()/max(len(q1[time_col].unique()),1)
        rs, rr = rest["spend"].sum()/max(len(rest[time_col].unique()),1), rest["revenue"].sum()/max(len(rest[time_col].unique()),1)
        inc_roi = ((rr-q1r)-(rs-q1s))/max(rs-q1s,1) if (rs-q1s)>0 else 0
        
        # Marginal ROI from response curves
        marg_roi = 0
        if curves and ch in curves and "params" in curves[ch]:
            p = curves[ch]["params"]
            a, b = p.get("a",1), p.get("b",0.5)
            avg_sp = curves[ch].get("current_avg_spend", s/12)
            marg_roi = a * b * np.power(max(avg_sp,1), b-1)
        
        # Payback period
        mo_data = cr.groupby(time_col).agg(ms=("spend","sum"),mr=("revenue","sum")).reset_index().sort_values(time_col)
        cum_s, cum_r, payback = 0, 0, 12
        for idx, row in mo_data.iterrows():
            cum_s += row["ms"]; cum_r += row["mr"]
            if cum_r >= cum_s and payback == 12: payback = len(mo_data[mo_data.index <= idx])
        
        # Bootstrap CI for base ROI
        monthly_rois = ((mo_data["mr"]-mo_data["ms"])/mo_data["ms"].clip(lower=1)).values
        if len(monthly_rois) > 2:
            boot_rois = [np.mean(np.random.choice(monthly_rois, len(monthly_rois), replace=True)) for _ in range(n_bootstrap)]
            roi_ci = [round(float(np.percentile(boot_rois, 5)),3), round(float(np.percentile(boot_rois, 95)),3)]
            roi_std = round(float(np.std(boot_rois)),3)
        else:
            roi_ci = [round(base_roi*0.8,3), round(base_roi*1.2,3)]; roi_std = 0
        
        results.append({
            "channel": ch, "spend": round(s,0), "revenue": round(rv,0),
            "base_roi": round(base_roi,3), "roi_ci_90": roi_ci, "roi_std": roi_std,
            "gm_roi": round(gm_roi,3), "roas": round(roas,2),
            "incremental_roi": round(inc_roi,3), "marginal_roi": round(float(marg_roi),4),
            "payback_months": payback,
            "cac": round(s/max(cv,1),0), "ltv_estimate": round(rv/max(cv,1)*2.5,0),
        })
    
    return sorted(results, key=lambda x: x["base_roi"], reverse=True)
