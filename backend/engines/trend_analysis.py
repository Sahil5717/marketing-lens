"""
Trend Analysis Engine — Production Grade
==========================================
Decomposes time-series into trend + seasonal + residual.
Detects anomalies via z-score + Grubbs test. Measures ROI consistency.

Libraries: statsmodels (seasonal_decompose, Grubbs), scipy.stats (z-test, normality), numpy, pandas
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from scipy import stats as sp_stats
import logging
logger = logging.getLogger(__name__)

def _seasonal_decompose(series, period=12):
    """Decompose into trend + seasonal + residual using statsmodels if available."""
    try:
        from statsmodels.tsa.seasonal import seasonal_decompose
        result = seasonal_decompose(series, model="additive", period=min(period, len(series)//2))
        return {"trend": result.trend, "seasonal": result.seasonal, "residual": result.resid, "method": "statsmodels"}
    except (ImportError, Exception):
        # Manual decomposition fallback
        n = len(series)
        trend = pd.Series(series).rolling(window=min(period, n//2), center=True).mean().values
        detrended = series - np.nan_to_num(trend, nan=np.nanmean(series))
        seasonal = np.array([np.nanmean(detrended[i::period]) for i in range(period)])
        seasonal = np.tile(seasonal, n//period + 1)[:n]
        residual = series - np.nan_to_num(trend, nan=np.nanmean(series)) - seasonal
        return {"trend": trend, "seasonal": seasonal, "residual": residual, "method": "manual"}

def run_trend_analysis(df, metric="revenue"):
    """Full trend analysis with decomposition, anomaly detection, and ROI consistency."""
    time_col = "month" if "month" in df.columns else "date"
    monthly = df.groupby(time_col).agg(
        revenue=("revenue","sum"), spend=("spend","sum"), conversions=("conversions","sum") if "conversions" in df.columns else ("conv","sum")
    ).reset_index().sort_values(time_col)
    
    vals = monthly[metric].values.astype(float)
    n = len(vals)
    
    # MoM changes
    mom = [0] + [((vals[i]-vals[i-1])/max(vals[i-1],1)*100) for i in range(1,n)]
    roi_series = [(monthly["revenue"].iloc[i]-monthly["spend"].iloc[i])/max(monthly["spend"].iloc[i],1) for i in range(n)]
    
    # Moving averages
    ma3 = pd.Series(vals).rolling(3, min_periods=1).mean().values
    
    # Seasonal decomposition
    decomp = _seasonal_decompose(vals, period=min(12, n//2)) if n >= 6 else None
    
    # Anomaly detection via z-score + Grubbs test
    mean_v, std_v = vals.mean(), vals.std()
    z_scores = (vals - mean_v) / max(std_v, 1)
    
    anomalies = []
    for i in range(n):
        if abs(z_scores[i]) > 1.96:  # 95% confidence
            # Grubbs test p-value
            G = abs(z_scores[i])
            t_crit = sp_stats.t.ppf(1 - 0.05/(2*n), n-2)
            G_crit = ((n-1)/np.sqrt(n)) * np.sqrt(t_crit**2 / (n-2+t_crit**2))
            is_outlier = G > G_crit
            anomalies.append({
                "period": str(monthly[time_col].iloc[i]),
                "value": round(float(vals[i]),0),
                "z_score": round(float(z_scores[i]),2),
                "direction": "spike" if z_scores[i]>0 else "dip",
                "grubbs_outlier": is_outlier,
            })
    
    # H1 vs H2 variance decomposition
    h1 = df[df[time_col].apply(lambda x: int(str(x).split("-")[1]) <= 6 if "-" in str(x) else True)]
    h2 = df[df[time_col].apply(lambda x: int(str(x).split("-")[1]) > 6 if "-" in str(x) else False)]
    var_decomp = []
    for ch in df["channel"].unique():
        h1r = h1[h1["channel"]==ch]["revenue"].sum()
        h2r = h2[h2["channel"]==ch]["revenue"].sum()
        var_decomp.append({"channel":ch, "h1_revenue":round(h1r,0), "h2_revenue":round(h2r,0),
            "change":round(h2r-h1r,0), "change_pct":round((h2r-h1r)/max(h1r,1)*100,1)})
    var_decomp.sort(key=lambda x: x["change"], reverse=True)
    
    # ROI consistency per channel (coefficient of variation)
    roi_consistency = {}
    for ch in df["channel"].unique():
        ch_mo = df[df["channel"]==ch].groupby(time_col).agg(s=("spend","sum"),r=("revenue","sum")).reset_index()
        rois = ((ch_mo["r"]-ch_mo["s"])/ch_mo["s"].clip(lower=1)).values
        if len(rois) > 1:
            avg, sd = rois.mean(), rois.std()
            cv = sd/abs(avg) if avg != 0 else 99
            # Levene's test for homogeneity of variance (split in half)
            mid = len(rois)//2
            if mid > 0:
                _, lev_p = sp_stats.levene(rois[:mid], rois[mid:])
            else:
                lev_p = 1.0
            roi_consistency[ch] = {"mean_roi":round(float(avg),3), "std_roi":round(float(sd),3),
                "cv":round(float(cv),3), "consistency":"High" if cv<0.15 else ("Medium" if cv<0.3 else "Low"),
                "variance_stable": lev_p > 0.05, "levene_pvalue": round(float(lev_p),4)}
    
    # Trend significance (Mann-Kendall-like via scipy)
    if n >= 4:
        tau, mk_p = sp_stats.kendalltau(np.arange(n), vals)
        trend_sig = {"tau": round(float(tau),4), "p_value": round(float(mk_p),4),
                     "significant": mk_p < 0.05, "direction": "increasing" if tau > 0 else "decreasing"}
    else:
        trend_sig = {"warning": "Not enough data points for trend test"}
    
    return {
        "monthly": [{"period":str(monthly[time_col].iloc[i]),"value":round(float(vals[i]),0),
            "mom_change":round(mom[i],1),"roi":round(roi_series[i],3),"ma3":round(float(ma3[i]),0),
            "z_score":round(float(z_scores[i]),2)} for i in range(n)],
        "anomalies": anomalies,
        "variance_decomposition": var_decomp,
        "roi_consistency": roi_consistency,
        "trend_test": trend_sig,
        "decomposition_method": decomp["method"] if decomp else None,
        "n_periods": n,
    }
