"""
Cross-Channel Leakage Engine — Production Grade
=================================================
Detects timing misalignment, regional leakage, online-offline flow issues.
Libraries: scipy.stats (Pearson correlation significance, KS test), numpy, pandas
"""
import numpy as np
import pandas as pd
from typing import Dict, List
from scipy import stats as sp_stats
import logging
logger = logging.getLogger(__name__)

def run_cross_channel_analysis(df):
    """Comprehensive cross-channel leakage with statistical significance tests."""
    time_col = "month" if "month" in df.columns else "date"
    monthly = df.groupby(time_col).agg(s=("spend","sum"), rv=("revenue","sum")).reset_index().sort_values(time_col)
    tS, tR = monthly["s"].sum(), monthly["rv"].sum()
    
    # Timing leakage with significance
    spend_shares = (monthly["s"]/tS).values
    rev_shares = (monthly["rv"]/tR).values
    timing_corr, timing_p = sp_stats.pearsonr(spend_shares, rev_shares) if len(spend_shares) > 2 else (0, 1)
    misalignment = np.abs(spend_shares - rev_shares)
    timing_leak = sum(monthly["s"].iloc[i] - tS*rev_shares[i] for i in range(len(monthly)) 
                      if spend_shares[i] > rev_shares[i]*1.15) * (tR/tS) * 0.3
    timing = [{"spend_share":round(float(spend_shares[i]),4),"rev_share":round(float(rev_shares[i]),4),
               "misalignment":round(float(misalignment[i]),4),
               "status":"overspend" if spend_shares[i]>rev_shares[i]*1.15 else ("underspend" if spend_shares[i]<rev_shares[i]*0.85 else "aligned")}
              for i in range(len(monthly))]
    
    # Regional leakage with efficiency test
    regions = {}
    for _, r in df.iterrows():
        reg = r.get("region", r.get("reg", "All"))
        if reg not in regions: regions[reg] = {"s":0,"rv":0}
        regions[reg]["s"] += r["spend"]; regions[reg]["rv"] += r["revenue"]
    
    reg_arr = []
    for reg, m in regions.items():
        eff = (m["rv"]/tR) / (m["s"]/tS) if m["s"] > 0 else 0
        status = "underfunded" if eff > 1.3 else ("overfunded" if eff < 0.7 else "balanced")
        reg_arr.append({"region":reg,"spend":round(m["s"],0),"revenue":round(m["rv"],0),
            "roi":round((m["rv"]-m["s"])/max(m["s"],1),3),"spend_share":round(m["s"]/tS,3),
            "rev_share":round(m["rv"]/tR,3),"efficiency":round(eff,3),"status":status})
    
    aud_leak = sum(max(0, (tS*r["rev_share"]-r["spend"])*r["roi"]*0.5) for r in reg_arr if r["status"]=="underfunded")
    
    # Online vs offline flow
    on = df[df.get("channel_type", df.get("ct", pd.Series(["online"]*len(df)))) == "online"]
    off = df[df.get("channel_type", df.get("ct", pd.Series(["offline"]*len(df)))) == "offline"]
    onR, offR = on["revenue"].sum(), off["revenue"].sum()
    onS, offS = on["spend"].sum(), off["spend"].sum()
    
    # KS test: are online and offline revenue distributions significantly different?
    if len(on) > 5 and len(off) > 5:
        on_monthly = on.groupby(time_col)["revenue"].sum().values
        off_monthly = off.groupby(time_col)["revenue"].sum().values
        ks_stat, ks_p = sp_stats.ks_2samp(on_monthly, off_monthly) if len(on_monthly)>2 and len(off_monthly)>2 else (0,1)
    else:
        ks_stat, ks_p = 0, 1
    
    return {
        "timing_leakage": round(float(timing_leak),0),
        "timing_correlation": {"pearson_r":round(float(timing_corr),4),"p_value":round(float(timing_p),4),
                               "significant":timing_p<0.05},
        "timing_details": timing,
        "audience_leakage": round(float(aud_leak),0),
        "regions": sorted(reg_arr, key=lambda x:x["efficiency"], reverse=True),
        "online_offline": {"online_revenue":round(onR,0),"offline_revenue":round(offR,0),
            "online_spend":round(onS,0),"offline_spend":round(offS,0),
            "online_roi":round((onR-onS)/max(onS,1),3),"offline_roi":round((offR-offS)/max(offS,1),3),
            "distribution_test":{"ks_statistic":round(float(ks_stat),4),"p_value":round(float(ks_p),4),
                "significantly_different":ks_p<0.05}},
        "total_cross_channel_leakage": round(float(timing_leak+aud_leak),0),
    }
