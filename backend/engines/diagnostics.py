"""
Diagnostics & Recommendation Engine — Production Grade
=======================================================
Rule-based + statistically-validated recommendations.
Each recommendation is backed by a statistical test (z-test, t-test, or threshold test).

Libraries: scipy.stats (z-test, t-test, chi-square), numpy, pandas
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from scipy import stats as sp_stats
import logging
logger = logging.getLogger(__name__)

def generate_recommendations(df, response_curves, attribution, significance_level=0.05):
    """
    Generate actionable recommendations with statistical evidence.
    Each recommendation includes: type, rationale, action, impact, confidence, statistical_test.
    """
    conv_col = "conversions" if "conversions" in df.columns else "conv"
    time_col = "month" if "month" in df.columns else "date"
    recs = []
    
    # Aggregate channel metrics
    ch_metrics = {}
    for ch in df["channel"].unique():
        cr = df[df["channel"]==ch]
        s, rv, cv, cl, im = cr["spend"].sum(), cr["revenue"].sum(), cr[conv_col].sum(), cr["clicks"].sum(), cr.get("impressions", cr.get("imps", pd.Series([0]))).sum()
        roi = (rv-s)/max(s,1); cac = s/max(cv,1); ctr = cl/max(im,1); cvr = cv/max(cl,1)
        # Monthly ROIs for variability
        mo = cr.groupby(time_col).agg(ms=("spend","sum"),mr=("revenue","sum")).reset_index()
        monthly_rois = ((mo["mr"]-mo["ms"])/mo["ms"].clip(lower=1)).values
        ch_metrics[ch] = {"s":s,"rv":rv,"cv":cv,"cl":cl,"im":im,"roi":roi,"cac":cac,"ctr":ctr,"cvr":cvr,"monthly_rois":monthly_rois}
    
    all_rois = [m["roi"] for m in ch_metrics.values()]
    med_roi = float(np.median(all_rois))
    all_cacs = [m["cac"] for m in ch_metrics.values() if m["cv"]>0]
    med_cac = float(np.median(all_cacs)) if all_cacs else 0
    
    # ─── SCALE recommendations ───
    for ch, m in ch_metrics.items():
        curve = response_curves.get(ch, {})
        if "error" in curve or "params" not in curve: continue
        headroom = curve.get("headroom_pct", 0)
        mROI = curve.get("marginal_roi", 0)
        near_linear = curve.get("near_linear_fit", False)

        # Gate near-linear fits out of SCALE recs. When b ≈ 1 the curve is
        # effectively straight and we have no evidence of the diminishing
        # returns that would make "scale this channel" a safe call. A SCALE
        # rec on a near-linear fit is the fabricated "+40% on organic_search
        # with 100% headroom and 40x mROI" we used to produce.
        if near_linear:
            # Emit a MAINTAIN-WITH-CAVEAT rec instead, so the analyst sees
            # this channel was considered for scaling but the fit didn't
            # support it.
            recs.append({
                "type": "INVESTIGATE", "channel": ch,
                "rationale": (
                    f"{ch} response curve is near-linear (b={curve.get('params',{}).get('b',0):.2f}), "
                    f"meaning we can't reliably identify a saturation point from current data. "
                    f"ROI is {m['roi']:.1f}x. Recommend validating with an incrementality test "
                    f"before scaling — the headroom signal here is unreliable."
                ),
                "action": "Run a geo-lift test before reallocating budget to this channel",
                "impact": 0,  # no impact claim -- we don't know
                "confidence": "Low",
                "effort": "Medium",
                "statistical_test": {"test":"response_curve_shape","b":round(float(curve.get("params",{}).get("b",0)),3),"near_linear":True},
            })
            continue

        if m["roi"] > med_roi * 1.2 and headroom > 20 and mROI > 1.5:
            # t-test: is this channel's ROI significantly above median?
            if len(m["monthly_rois"]) > 2:
                t_stat, p_val = sp_stats.ttest_1samp(m["monthly_rois"], med_roi)
                sig = p_val < significance_level and t_stat > 0
            else:
                t_stat, p_val, sig = 0, 1, False

            # Impact estimate: conservative. Use mROI * 0.6 (not 0.8) and
            # cap the projected spend increase at 40% regardless of
            # headroom (same extrapolation cap philosophy as the optimizer).
            # This is the SCALE rec's "expected annual revenue uplift."
            increase_pct = min(headroom * 0.5, 40)
            # Extra cap: don't project impact larger than 50% of the
            # channel's current revenue. A SCALE rec claiming +$50M on a
            # $20M-revenue channel is almost always over-extrapolating.
            raw_impact = m["s"] * increase_pct/100 * mROI * 0.6
            impact = round(min(raw_impact, m["rv"] * 0.5), 0)
            recs.append({
                "type": "SCALE", "channel": ch,
                "rationale": f"ROI {m['roi']:.1f}x (median {med_roi:.1f}x), {headroom:.0f}% headroom, marginal ROI {mROI:.1f}x.",
                "action": f"Increase spend by {increase_pct:.0f}%",
                "impact": impact, "confidence": "High" if sig else "Medium",
                "effort": "Low",
                "statistical_test": {"test":"one_sample_t","t_stat":round(float(t_stat),3),"p_value":round(float(p_val),4),"significant":sig},
            })
    
    # ─── REDUCE recommendations ───
    for ch, m in ch_metrics.items():
        curve = response_curves.get(ch, {})
        if "error" in curve or "params" not in curve: continue
        mROI = curve.get("marginal_roi", 0)
        headroom = curve.get("headroom_pct", 0)
        
        if mROI < 1.5 and headroom < 15:
            if len(m["monthly_rois"]) > 2:
                t_stat, p_val = sp_stats.ttest_1samp(m["monthly_rois"], med_roi)
                sig = p_val < significance_level and t_stat < 0
            else:
                t_stat, p_val, sig = 0, 1, False
            
            recs.append({
                "type": "REDUCE", "channel": ch,
                "rationale": f"Marginal ROI {mROI:.2f}x below hurdle. Only {headroom:.0f}% headroom — near saturation.",
                "action": "Reduce 15-25%, reallocate to higher-yield channels",
                "impact": round(-m["s"]*0.2*mROI, 0), "confidence": "High" if sig else "Medium",
                "effort": "Low",
                "statistical_test": {"test":"one_sample_t","t_stat":round(float(t_stat),3),"p_value":round(float(p_val),4),"significant":sig},
            })
    
    # ─── RETARGET recommendations ───
    for ch, m in ch_metrics.items():
        if m["cac"] > med_cac * 1.5 and m["cv"] > 10:
            # z-test: is CAC significantly above median?
            if len(all_cacs) > 2:
                z = (m["cac"] - med_cac) / max(np.std(all_cacs), 1)
                p_val = 1 - sp_stats.norm.cdf(z)
                sig = p_val < significance_level
            else:
                z, p_val, sig = 0, 1, False
            
            recs.append({
                "type": "RETARGET", "channel": ch,
                "rationale": f"CAC ${m['cac']:.0f} is {m['cac']/med_cac:.1f}x the portfolio median ${med_cac:.0f}.",
                "action": "Tighten audience targeting, review bids",
                "impact": round((m["cac"]-med_cac)*m["cv"]*0.3, 0), "confidence": "High" if sig else "Medium",
                "effort": "Medium",
                "statistical_test": {"test":"z_test_cac","z_stat":round(float(z),3),"p_value":round(float(p_val),4),"significant":sig},
            })
    
    # ─── FIX recommendations (CTR high but CVR low = landing page issue) ───
    camp_col = "campaign" if "campaign" in df.columns else "camp"
    camp_metrics = df.groupby(["channel", camp_col]).agg(
        cl=("clicks","sum"), im=("impressions" if "impressions" in df.columns else "imps","sum"),
        cv=(conv_col,"sum"), s=("spend","sum")
    ).reset_index()
    camp_metrics["ctr"] = camp_metrics["cl"]/camp_metrics["im"].clip(lower=1)
    camp_metrics["cvr"] = camp_metrics["cv"]/camp_metrics["cl"].clip(lower=1)
    med_ctr = camp_metrics["ctr"].median(); med_cvr = camp_metrics["cvr"].median()
    
    for _, row in camp_metrics.iterrows():
        if row["ctr"] > med_ctr * 1.5 and row["cvr"] < med_cvr * 0.6 and row["cl"] > 500:
            recs.append({
                "type": "FIX", "channel": row["channel"], "campaign": row[camp_col],
                "rationale": f"CTR {row['ctr']*100:.1f}% (good) but CVR {row['cvr']*100:.2f}% (poor). Landing page or form friction likely.",
                "action": "Audit landing page, test CTAs, review form UX",
                "impact": round(row["cl"]*(med_cvr-row["cvr"])*350*0.4, 0),
                "confidence": "High", "effort": "Medium",
                "statistical_test": {"test":"threshold","ctr_vs_median":round(float(row["ctr"]/med_ctr),2),"cvr_vs_median":round(float(row["cvr"]/med_cvr),2)},
            })
    
    # ─── MAINTAIN recommendations (strong assist channels) ───
    if attribution:
        lt = attribution.get("last_touch", {})
        ln = attribution.get("linear", {})
        # Convert DataFrames to {channel: revenue} dicts if needed
        if hasattr(lt, "groupby"): lt = lt.groupby("channel")["attributed_revenue"].sum().to_dict()
        if hasattr(ln, "groupby"): ln = ln.groupby("channel")["attributed_revenue"].sum().to_dict()
        for ch in lt:
            lt_v = float(lt.get(ch, 0)); ln_v = float(ln.get(ch, 0))
            if lt_v > 0 and ln_v/lt_v > 1.4:
                recs.append({
                    "type": "MAINTAIN", "channel": ch,
                    "rationale": f"Last-touch ${lt_v/1e3:.0f}K vs linear ${ln_v/1e3:.0f}K — strong assist channel.",
                    "action": "Maintain spend; don't cut based on last-touch alone",
                    "impact": round(ln_v-lt_v, 0), "confidence": "Medium", "effort": "None",
                    "statistical_test": {"test":"attribution_divergence","ratio":round(ln_v/max(lt_v,1),2)},
                })
    
    # Sort by absolute impact
    recs.sort(key=lambda x: abs(x.get("impact",0)), reverse=True)
    for i, r in enumerate(recs):
        r["id"] = f"REC-{i+1:03d}"; r["priority"] = i+1; r["status"] = "pending"
        r.setdefault("campaign", "")
    
    return recs
