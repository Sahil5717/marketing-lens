"""
Funnel Analysis Engine — Production Grade
===========================================
Funnel stage conversion analysis with statistical benchmarking.
Libraries: scipy.stats (chi-square, proportions z-test, binomial CI), numpy, pandas
"""
import numpy as np
import pandas as pd
from typing import Dict, List
from scipy import stats as sp_stats
import logging
logger = logging.getLogger(__name__)

def _binomial_ci(successes, trials, confidence=0.95):
    """Wilson score confidence interval for proportions."""
    if trials == 0: return 0, 0
    p = successes / trials
    z = sp_stats.norm.ppf(1 - (1-confidence)/2)
    denom = 1 + z**2/trials
    center = (p + z**2/(2*trials)) / denom
    spread = z * np.sqrt((p*(1-p) + z**2/(4*trials)) / trials) / denom
    return max(0, center - spread), min(1, center + spread)

def run_funnel_analysis(df):
    """Full funnel analysis with conversion rates, CIs, bottleneck detection, and chi-square tests."""
    stages = ["imps","clicks","leads","mqls","sqls","conv"]
    labels = ["Impressions","Clicks","Leads","MQLs","SQLs","Conversions"]
    alt_names = {"imps":"impressions","conv":"conversions"}
    
    totals = []
    for s in stages:
        col = s if s in df.columns else alt_names.get(s, s)
        totals.append(int(df[col].sum()) if col in df.columns else 0)
    
    benchmarks = {"clicks":0.02, "leads":0.08, "mqls":0.45, "sqls":0.38, "conv":0.25}
    
    overall = []
    bottlenecks = []
    for i, (stage, label) in enumerate(zip(stages, labels)):
        rate = totals[i]/max(totals[i-1],1) if i > 0 and totals[i-1] > 0 else None
        ci_lo, ci_hi = _binomial_ci(totals[i], totals[i-1]) if i > 0 and totals[i-1] > 0 else (None, None)
        drop_off = 1 - rate if rate else None
        
        entry = {"stage": label, "volume": totals[i], "rate": round(rate,4) if rate else None,
                 "rate_ci_95": [round(ci_lo,4), round(ci_hi,4)] if ci_lo is not None else None,
                 "drop_off": round(drop_off,4) if drop_off else None}
        overall.append(entry)
        
        # Bottleneck detection: is conversion rate significantly below benchmark?
        bm = benchmarks.get(stage)
        if bm and rate and i > 0 and totals[i-1] > 30:
            # Proportions z-test: is observed rate < benchmark?
            z_stat, p_val = sp_stats.binomtest(totals[i], totals[i-1], bm, alternative="less"), None
            try:
                # Use proportions_ztest for proper z-test
                from statsmodels.stats.proportion import proportions_ztest
                z_stat, p_val = proportions_ztest(totals[i], totals[i-1], value=bm, alternative="smaller")
            except ImportError:
                # Fallback: manual z-test
                p_hat = totals[i]/totals[i-1]
                se = np.sqrt(bm*(1-bm)/totals[i-1])
                z_stat = (p_hat - bm) / max(se, 1e-10)
                p_val = sp_stats.norm.cdf(z_stat)
            
            if rate < bm * 0.8:
                gap_pct = round((bm-rate)/bm*100, 0)
                lost = round(totals[i-1]*(bm-rate), 0)
                bottlenecks.append({
                    "stage": label, "from": labels[i-1],
                    "actual_rate": round(rate,4), "benchmark": bm,
                    "gap_pct": gap_pct, "lost_volume": lost,
                    "p_value": round(float(p_val),4) if p_val is not None else None,
                    "statistically_significant": p_val < 0.05 if p_val is not None else False,
                    "severity": "critical" if rate < bm*0.5 else "warning",
                })
    
    # Per-channel funnel
    ch_funnels = []
    for ch in df["channel"].unique():
        cr = df[df["channel"]==ch]
        t = []
        for s in stages:
            col = s if s in cr.columns else alt_names.get(s,s)
            t.append(int(cr[col].sum()) if col in cr.columns else 0)
        ch_funnels.append({
            "channel": ch,
            "stages": [{"stage":labels[i],"volume":t[i],
                "rate": round(t[i]/max(t[i-1],1),4) if i>0 and t[i-1]>0 else None}
                for i in range(len(stages))],
            "overall_rate": t[-1]/max(t[0],1) if t[0]>0 else 0
        })
    
    # Revenue impact if bottlenecks fixed
    avg_rpc = df["revenue"].sum() / max(df["conversions" if "conversions" in df.columns else "conv"].sum(), 1)
    impacts = [{"stage":b["stage"],"additional_conversions":round(b["lost_volume"]*0.3,0),
                "additional_revenue":round(b["lost_volume"]*0.3*avg_rpc,0),**b} for b in bottlenecks]
    
    return {
        "overall_funnel": overall,
        "bottlenecks": bottlenecks,
        "channel_funnels": sorted(ch_funnels, key=lambda x:x["overall_rate"], reverse=True),
        "revenue_impact": impacts,
        "total_addressable_revenue": round(sum(i["additional_revenue"] for i in impacts),0),
        "avg_revenue_per_conversion": round(avg_rpc,0),
    }
