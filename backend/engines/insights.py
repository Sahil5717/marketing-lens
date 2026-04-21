"""
Narrative Insights Engine
=========================
Auto-generates human-readable insights from analytical outputs.
Produces 3 tiers: executive headlines, channel stories, and action narratives.
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
import logging
logger = logging.getLogger(__name__)


def generate_insights(
    campaign_df,
    response_curves: Dict = None,
    optimizer_result: Dict = None,
    pillars: Dict = None,
    attribution: Dict = None,
    mmm_result: Dict = None,
    trend_data: Dict = None,
    funnel_data: Dict = None,
) -> Dict:
    """Generate narrative insights from all available analytics outputs."""
    insights = {
        "executive_headlines": [],
        "channel_stories": [],
        "cross_model_insights": [],
        "risk_narratives": [],
        "opportunity_narratives": [],
        "generated_count": 0,
    }

    df = campaign_df
    time_col = "month" if "month" in df.columns else "date"
    conv_col = "conversions" if "conversions" in df.columns else "conv"
    total_spend = float(df["spend"].sum())
    total_rev = float(df["revenue"].sum())
    total_conv = float(df[conv_col].sum()) if conv_col in df.columns else 0
    overall_roi = (total_rev - total_spend) / max(total_spend, 1)
    overall_roas = total_rev / max(total_spend, 1)
    overall_cac = total_spend / max(total_conv, 1)

    # ═══ EXECUTIVE HEADLINES ═══
    # 1. Portfolio health (always fires)
    if overall_roi > 3:
        insights["executive_headlines"].append({
            "type": "positive", "priority": 1,
            "headline": f"Strong portfolio: {overall_roi:.1f}x ROI across all channels",
            "detail": f"Every $1 invested returns ${overall_roi+1:.2f}. Portfolio ROAS is {overall_roas:.1f}x, above typical B2B benchmarks of 2-5x.",
            "metric": "roi", "value": round(overall_roi, 2),
        })
    elif overall_roi > 1:
        insights["executive_headlines"].append({
            "type": "neutral", "priority": 1,
            "headline": f"Moderate portfolio ROI at {overall_roi:.1f}x",
            "detail": f"Returns are positive but there's meaningful room for improvement through reallocation. Portfolio CAC is ${overall_cac:,.0f}.",
            "metric": "roi", "value": round(overall_roi, 2),
        })
    else:
        insights["executive_headlines"].append({
            "type": "negative", "priority": 1,
            "headline": f"Portfolio ROI is only {overall_roi:.1f}x — needs urgent attention",
            "detail": f"Marketing spend is not generating sufficient returns. Every $1 returns only ${overall_roi+1:.2f}. Reallocation or spend cuts needed.",
            "metric": "roi", "value": round(overall_roi, 2),
        })

    # 2. Channel concentration risk (widened: 30% threshold, was 40%)
    ch_rev = df.groupby("channel")["revenue"].sum().sort_values(ascending=False)
    if len(ch_rev) > 0:
        top_ch = ch_rev.index[0]
        top_pct = float(ch_rev.iloc[0] / max(total_rev, 1) * 100)
        top2_pct = float(ch_rev.iloc[:2].sum() / max(total_rev, 1) * 100) if len(ch_rev) > 1 else top_pct
        if top_pct > 30:
            insights["executive_headlines"].append({
                "type": "warning", "priority": 2,
                "headline": f"Concentration risk: {top_ch.replace('_',' ').title()} drives {top_pct:.0f}% of revenue",
                "detail": f"Over-reliance on a single channel creates vulnerability. If {top_ch.replace('_',' ')} performance drops for any reason, there's no backup at scale.",
                "metric": "concentration", "value": round(top_pct, 1),
            })
        elif top2_pct > 55:
            insights["executive_headlines"].append({
                "type": "warning", "priority": 2,
                "headline": f"Top 2 channels drive {top2_pct:.0f}% of revenue",
                "detail": f"{ch_rev.index[0].replace('_',' ').title()} and {ch_rev.index[1].replace('_',' ').title()} together carry majority of revenue. Consider diversification for resilience.",
                "metric": "concentration_top2", "value": round(top2_pct, 1),
            })

    # 3. Online vs Offline efficiency gap (widened: 1x threshold, was 2x)
    online = df[df.get("channel_type", df.get("ct", pd.Series(dtype=str))) == "online"]
    offline = df[df.get("channel_type", df.get("ct", pd.Series(dtype=str))) == "offline"]
    if len(online) > 0 and len(offline) > 0:
        on_roi = (online["revenue"].sum() - online["spend"].sum()) / max(online["spend"].sum(), 1)
        off_roi = (offline["revenue"].sum() - offline["spend"].sum()) / max(offline["spend"].sum(), 1)
        gap = abs(on_roi - off_roi)
        if gap > 1:
            better = "Online" if on_roi > off_roi else "Offline"
            worse = "Offline" if on_roi > off_roi else "Online"
            insights["executive_headlines"].append({
                "type": "insight", "priority": 3,
                "headline": f"{better} channels outperform {worse} by {gap:.1f}x ROI",
                "detail": f"{better} ROI is {max(on_roi,off_roi):.1f}x vs {worse} at {min(on_roi,off_roi):.1f}x. Consider shifting budget toward {better} unless {worse} carries strategic value (brand, air cover, specific audiences).",
                "metric": "channel_gap", "value": round(gap, 1),
            })

    # 4. Trend momentum (widened: 5% threshold, was 10%)
    monthly_rev = df.groupby(time_col)["revenue"].sum().sort_index()
    if len(monthly_rev) >= 6:
        h1 = monthly_rev.iloc[:len(monthly_rev)//2].mean()
        h2 = monthly_rev.iloc[len(monthly_rev)//2:].mean()
        momentum = (h2 - h1) / max(h1, 1) * 100
        if abs(momentum) > 5:
            direction = "accelerating" if momentum > 0 else "decelerating"
            insights["executive_headlines"].append({
                "type": "positive" if momentum > 0 else "warning", "priority": 3,
                "headline": f"Revenue momentum is {direction}: {momentum:+.1f}% H2 vs H1",
                "detail": f"Second-half monthly average ${h2:,.0f} vs first-half ${h1:,.0f}. {'Maintain current strategy and monitor for sustainability.' if momentum > 0 else 'Investigate root cause — distinguish seasonal from structural drivers.'}",
                "metric": "momentum", "value": round(momentum, 1),
            })

    # 5. Saturation / headroom profile (NEW — fires when response curves
    #    show either widespread saturation or widespread untapped headroom)
    if response_curves:
        curves_list = [(ch, v) for ch, v in response_curves.items() if "error" not in v]
        if curves_list:
            # Share of spend on channels with <20% headroom (saturated)
            sat_spend = sum(v.get("current_avg_spend", 0) * 12 for _, v in curves_list
                            if v.get("headroom_pct", 0) < 20)
            total_ch_spend = sum(v.get("current_avg_spend", 0) * 12 for _, v in curves_list)
            sat_share = sat_spend / max(total_ch_spend, 1) * 100
            # Share of spend on channels with >50% headroom (growth room)
            growth_spend = sum(v.get("current_avg_spend", 0) * 12 for _, v in curves_list
                               if v.get("headroom_pct", 0) > 50 and not v.get("near_linear_fit", False))
            growth_share = growth_spend / max(total_ch_spend, 1) * 100

            if sat_share > 30:
                insights["executive_headlines"].append({
                    "type": "warning", "priority": 2,
                    "headline": f"{sat_share:.0f}% of spend sits on saturating channels",
                    "detail": f"Channels with less than 20% response-curve headroom absorb ${sat_spend/1e6:.1f}M of current annual spend. Further investment in these will likely show diminishing returns.",
                    "metric": "saturation_share", "value": round(sat_share, 1),
                })
            if growth_share > 20:
                insights["executive_headlines"].append({
                    "type": "positive", "priority": 2,
                    "headline": f"{growth_share:.0f}% of spend is on channels with substantial headroom",
                    "detail": f"Channels showing >50% response-curve headroom with reliable fits carry ${growth_spend/1e6:.1f}M of current annual spend. These are your near-term growth levers.",
                    "metric": "growth_share", "value": round(growth_share, 1),
                })

    # 6. CAC spread (NEW — fires when per-channel CAC varies dramatically,
    #    signaling reallocation opportunity)
    ch_data_temp = df.groupby("channel").agg(
        s=("spend","sum"),
        c=(conv_col, "sum") if conv_col in df.columns else ("revenue", "count"),
    ).reset_index()
    ch_data_temp["cac"] = ch_data_temp["s"] / ch_data_temp["c"].clip(lower=1)
    if len(ch_data_temp) >= 3:
        cac_ratio = float(ch_data_temp["cac"].max() / max(ch_data_temp["cac"].min(), 1))
        if cac_ratio > 5:
            best_ch = ch_data_temp.sort_values("cac").iloc[0]["channel"]
            worst_ch = ch_data_temp.sort_values("cac").iloc[-1]["channel"]
            insights["executive_headlines"].append({
                "type": "insight", "priority": 3,
                "headline": f"Per-channel CAC spans {cac_ratio:.0f}x between best and worst channel",
                "detail": (
                    f"{best_ch.replace('_',' ').title()} converts at ${ch_data_temp['cac'].min():,.0f} CAC; "
                    f"{worst_ch.replace('_',' ').title()} is ${ch_data_temp['cac'].max():,.0f}. "
                    f"Note: some of this is channel function (reach vs. response), not pure inefficiency."
                ),
                "metric": "cac_spread", "value": round(cac_ratio, 1),
            })

    # ═══ CHANNEL STORIES ═══
    ch_data = df.groupby("channel").agg(
        spend=("spend","sum"), revenue=("revenue","sum"),
        **({conv_col:("conversions","sum")} if "conversions" in df.columns else {conv_col:(conv_col,"sum")}),
    ).reset_index()
    ch_data["roi"] = (ch_data["revenue"] - ch_data["spend"]) / ch_data["spend"].clip(lower=1)
    ch_data["cac"] = ch_data["spend"] / ch_data[conv_col].clip(lower=1)
    ch_data["share"] = ch_data["revenue"] / max(total_rev, 1) * 100
    median_roi = ch_data["roi"].median()
    median_cac = ch_data["cac"].median()

    for _, row in ch_data.iterrows():
        ch = row["channel"]
        ch_label = ch.replace("_", " ").title()
        story = {"channel": ch, "narratives": []}

        # Performance narrative
        if row["roi"] > median_roi * 1.5:
            story["narratives"].append({
                "type": "strength",
                "text": f"{ch_label} is a top performer at {row['roi']:.1f}x ROI ({row['share']:.1f}% of revenue). It has room to absorb more budget if response curves confirm headroom.",
            })
        elif row["roi"] < median_roi * 0.5:
            story["narratives"].append({
                "type": "weakness",
                "text": f"{ch_label} underperforms at {row['roi']:.1f}x ROI vs portfolio median {median_roi:.1f}x. CAC is ${row['cac']:,.0f}. Review targeting and creative before cutting — it may assist other channels.",
            })

        # Response curve narrative
        if response_curves and ch in response_curves:
            cv = response_curves[ch]
            if "error" not in cv:
                hd = cv.get("headroom_pct", 0)
                mROI = cv.get("marginal_roi", 0)
                if hd > 40 and mROI > 1.5:
                    story["narratives"].append({
                        "type": "opportunity",
                        "text": f"Response curve shows {hd:.0f}% headroom with marginal ROI {mROI:.1f}x. This channel can profitably absorb {min(hd*0.5, 40):.0f}% more spend.",
                    })
                elif hd < 15:
                    story["narratives"].append({
                        "type": "saturation",
                        "text": f"Near saturation point — only {hd:.0f}% headroom. Additional spend yields marginal ROI of {mROI:.2f}x. Reallocate incremental budget elsewhere.",
                    })

        if story["narratives"]:
            insights["channel_stories"].append(story)

    # ═══ CROSS-MODEL INSIGHTS ═══
    if attribution and mmm_result and mmm_result.get("contributions"):
        mmm_contribs = mmm_result["contributions"]
        for model_name in ["last_touch", "linear", "position_based"]:
            attr_model = attribution.get(model_name, {})
            if not attr_model:
                continue
            for ch in attr_model:
                attr_rev = float(attr_model.get(ch, 0))
                mmm_rev = float(mmm_contribs.get(ch, {}).get("contribution", 0)) if ch in mmm_contribs else 0
                if attr_rev > 0 and mmm_rev > 0:
                    ratio = mmm_rev / attr_rev
                    if ratio > 2:
                        ch_label = ch.replace("_", " ").title()
                        insights["cross_model_insights"].append({
                            "type": "attribution_mmm_divergence", "channel": ch,
                            "text": f"MMM values {ch_label} {ratio:.1f}x higher than {model_name.replace('_',' ')} attribution. This suggests strong indirect/halo effects that touchpoint-based attribution misses.",
                            "attr_revenue": round(attr_rev, 0), "mmm_revenue": round(mmm_rev, 0),
                        })
                    elif ratio < 0.3:
                        ch_label = ch.replace("_", " ").title()
                        insights["cross_model_insights"].append({
                            "type": "attribution_mmm_divergence", "channel": ch,
                            "text": f"Attribution credits {ch_label} {1/ratio:.1f}x more than MMM. This channel may be capturing credit for conversions driven by other channels (last-touch bias).",
                            "attr_revenue": round(attr_rev, 0), "mmm_revenue": round(mmm_rev, 0),
                        })
            break  # only compare against first available model

    # ═══ RISK NARRATIVES ═══
    if pillars:
        leak = pillars.get("revenue_leakage", {}).get("total_leakage", 0)
        exp = pillars.get("experience_suppression", {}).get("total_suppression", 0)
        cost = pillars.get("avoidable_cost", {}).get("total_avoidable_cost", 0)
        total_risk = leak + exp + cost

        if total_risk > total_rev * 0.05:
            insights["risk_narratives"].append({
                "type": "material_risk", "priority": 1,
                "headline": f"${total_risk:,.0f} value at risk ({total_risk/max(total_rev,1)*100:.1f}% of revenue)",
                "detail": f"Revenue leakage (${leak:,.0f}) from misallocation, CX suppression (${exp:,.0f}) from conversion friction, and avoidable cost (${cost:,.0f}) from inefficient channels.",
                "breakdown": {"leakage": round(leak, 0), "cx_suppression": round(exp, 0), "avoidable_cost": round(cost, 0)},
            })

        # Specific CX risk
        exp_items = pillars.get("experience_suppression", {}).get("items", [])
        if exp_items:
            worst = exp_items[0]
            insights["risk_narratives"].append({
                "type": "cx_friction", "priority": 2,
                "headline": f"Conversion friction costing ${worst.get('suppressed_revenue', 0):,.0f} on {worst.get('campaign', 'top campaign')}",
                "detail": f"CVR is {worst.get('cvr',0)*100:.2f}% vs median. Fix landing page, CTAs, or form UX to recover this revenue without additional media spend.",
            })

    # ═══ OPPORTUNITY NARRATIVES ═══
    if optimizer_result and "summary" in optimizer_result:
        sm = optimizer_result["summary"]
        uplift = sm.get("uplift_pct", 0)
        rev_delta = sm.get("optimized_revenue", 0) - sm.get("current_revenue", 0)
        if uplift > 5:
            # Find biggest movers
            channels = optimizer_result.get("channels", [])
            increases = sorted([c for c in channels if c.get("change_pct", 0) > 10], key=lambda x: x.get("revenue_delta", 0), reverse=True)
            decreases = sorted([c for c in channels if c.get("change_pct", 0) < -10], key=lambda x: x.get("change_pct", 0))

            move_from = ", ".join([c["channel"].replace("_"," ").title() for c in decreases[:2]]) if decreases else "lower-performing channels"
            move_to = ", ".join([c["channel"].replace("_"," ").title() for c in increases[:2]]) if increases else "higher-performing channels"

            insights["opportunity_narratives"].append({
                "type": "reallocation", "priority": 1,
                "headline": f"Reallocation can unlock ${abs(rev_delta):,.0f} ({uplift:.1f}% uplift) without increasing budget",
                "detail": f"Shift spend from {move_from} toward {move_to}. The optimizer finds that marginal returns are higher in underfunded channels.",
                "uplift_pct": round(uplift, 1), "revenue_delta": round(rev_delta, 0),
            })

    # ═══ FUNNEL INSIGHTS ═══
    if funnel_data and funnel_data.get("bottlenecks"):
        for bn in funnel_data["bottlenecks"][:2]:
            insights["opportunity_narratives"].append({
                "type": "funnel_fix", "priority": 2,
                "headline": f"Funnel bottleneck at {bn.get('stage','')}: {bn.get('gap',0)}% below benchmark",
                "detail": f"Conversion from {bn.get('from','')} to {bn.get('stage','')} is {bn.get('actual',0)*100:.1f}% vs benchmark {bn.get('benchmark',0)*100:.1f}%. Fixing this could recover {bn.get('lostVolume',0):,} lost prospects.",
            })

    insights["generated_count"] = sum(len(v) for v in insights.values() if isinstance(v, list))
    return insights


def compute_qoq_yoy_trends(df, channel=None):
    """Compute QoQ and YoY trends per channel and overall. Returns structured trend data."""
    time_col = "month" if "month" in df.columns else "date"
    conv_col = "conversions" if "conversions" in df.columns else "conv"
    
    if channel:
        df = df[df["channel"] == channel]
    
    # Monthly aggregation
    monthly = df.groupby(time_col).agg(
        spend=("spend","sum"), revenue=("revenue","sum"), 
        conversions=(conv_col,"sum"), clicks=("clicks","sum"),
    ).reset_index().sort_values(time_col)
    monthly["month_str"] = monthly[time_col].astype(str)
    monthly["year"] = monthly["month_str"].str[:4].astype(int)
    monthly["month_num"] = monthly["month_str"].str[5:7].astype(int)
    monthly["quarter"] = ((monthly["month_num"] - 1) // 3) + 1
    monthly["yq"] = monthly["year"].astype(str) + "-Q" + monthly["quarter"].astype(str)
    monthly["roi"] = (monthly["revenue"] - monthly["spend"]) / monthly["spend"].clip(lower=1)
    monthly["cac"] = monthly["spend"] / monthly["conversions"].clip(lower=1)
    monthly["roas"] = monthly["revenue"] / monthly["spend"].clip(lower=1)
    
    # Quarterly aggregation
    quarterly = monthly.groupby("yq").agg(
        spend=("spend","sum"), revenue=("revenue","sum"),
        conversions=("conversions","sum"), clicks=("clicks","sum"),
    ).reset_index().sort_values("yq")
    quarterly["roi"] = (quarterly["revenue"] - quarterly["spend"]) / quarterly["spend"].clip(lower=1)
    quarterly["cac"] = quarterly["spend"] / quarterly["conversions"].clip(lower=1)
    quarterly["roas"] = quarterly["revenue"] / quarterly["spend"].clip(lower=1)
    
    result = {"qoq": {}, "yoy": {}, "trailing": {}}
    
    # QoQ: compare last quarter vs previous quarter
    if len(quarterly) >= 2:
        curr_q = quarterly.iloc[-1]
        prev_q = quarterly.iloc[-2]
        for metric in ["spend","revenue","roi","cac","roas","conversions"]:
            curr_v = float(curr_q[metric])
            prev_v = float(prev_q[metric])
            chg = (curr_v - prev_v) / max(abs(prev_v), 1) * 100
            result["qoq"][metric] = {
                "current": round(curr_v, 2), "previous": round(prev_v, 2),
                "change_pct": round(chg, 1),
                "direction": "up" if chg > 2 else ("down" if chg < -2 else "flat"),
                "current_period": str(curr_q["yq"]), "previous_period": str(prev_q["yq"]),
            }
    
    # YoY: compare last 12 months vs prior 12 months
    if len(monthly) >= 24:
        last_12 = monthly.iloc[-12:]
        prior_12 = monthly.iloc[-24:-12]
        for metric in ["spend","revenue","roi","cac","roas","conversions"]:
            curr_v = float(last_12[metric].sum()) if metric in ["spend","revenue","conversions","clicks"] else float(last_12[metric].mean())
            prev_v = float(prior_12[metric].sum()) if metric in ["spend","revenue","conversions","clicks"] else float(prior_12[metric].mean())
            chg = (curr_v - prev_v) / max(abs(prev_v), 1) * 100
            result["yoy"][metric] = {
                "current": round(curr_v, 2), "previous": round(prev_v, 2),
                "change_pct": round(chg, 1),
                "direction": "up" if chg > 2 else ("down" if chg < -2 else "flat"),
            }
    
    # Trailing 3-month trend (most recent 3 vs prior 3)
    if len(monthly) >= 6:
        last_3 = monthly.iloc[-3:]
        prior_3 = monthly.iloc[-6:-3]
        for metric in ["spend","revenue","roi","cac","roas","conversions"]:
            curr_v = float(last_3[metric].sum()) if metric in ["spend","revenue","conversions","clicks"] else float(last_3[metric].mean())
            prev_v = float(prior_3[metric].sum()) if metric in ["spend","revenue","conversions","clicks"] else float(prior_3[metric].mean())
            chg = (curr_v - prev_v) / max(abs(prev_v), 1) * 100
            result["trailing"][metric] = {
                "current": round(curr_v, 2), "previous": round(prev_v, 2),
                "change_pct": round(chg, 1),
                "direction": "up" if chg > 2 else ("down" if chg < -2 else "flat"),
            }
    
    return result


def generate_smart_recommendations(
    campaign_df, response_curves, attribution, optimizer_result, pillars,
    trend_data=None, mmm_result=None, model_selections=None,
):
    """
    Generate paragraph-style recommendations with:
    - Historical context (what happened)
    - Trailing trend (QoQ/YoY direction)
    - Cross-channel reasoning (move from X to Y)
    - Quantified actions (specific $ amounts)
    - Phased plan (Month 1, Month 2-3)
    - Model provenance (which models generated this)
    """
    conv_col = "conversions" if "conversions" in campaign_df.columns else "conv"
    recs = []
    
    # Overall trends
    overall_trends = compute_qoq_yoy_trends(campaign_df)
    
    # Per-channel data
    ch_data = {}
    for ch in campaign_df["channel"].unique():
        cr = campaign_df[campaign_df["channel"] == ch]
        s, rv, cv = float(cr["spend"].sum()), float(cr["revenue"].sum()), float(cr[conv_col].sum())
        roi = (rv - s) / max(s, 1)
        cac = s / max(cv, 1)
        ch_trends = compute_qoq_yoy_trends(campaign_df, channel=ch)
        
        curve = response_curves.get(ch, {}) if response_curves else {}
        headroom = curve.get("headroom_pct", 0) if "error" not in curve else 0
        marginal = curve.get("marginal_roi", 0) if "error" not in curve else 0
        model_used = curve.get("model", curve.get("_auto_selected", "power_law")) if "error" not in curve else "N/A"
        r2 = curve.get("r_squared", 0) if "error" not in curve else 0
        
        ch_data[ch] = {
            "spend": s, "revenue": rv, "conversions": cv, "roi": roi, "cac": cac,
            "headroom": headroom, "marginal_roi": marginal, "model": model_used, "r2": r2,
            "trends": ch_trends, "label": ch.replace("_", " ").title(),
        }
    
    # Sort by ROI
    sorted_channels = sorted(ch_data.items(), key=lambda x: x[1]["roi"], reverse=True)
    median_roi = float(np.median([v["roi"] for v in ch_data.values()]))
    median_cac = float(np.median([v["cac"] for v in ch_data.values()]))
    
    # Find best channels to move TO and FROM
    scale_candidates = [(ch, d) for ch, d in sorted_channels if d["headroom"] > 25 and d["marginal_roi"] > 1.5]
    reduce_candidates = [(ch, d) for ch, d in sorted_channels if d["headroom"] < 15 or d["marginal_roi"] < 1.0]
    
    # === REALLOCATION RECOMMENDATIONS (cross-channel) ===
    for i, (to_ch, to_d) in enumerate(scale_candidates[:3]):
        from_ch, from_d = reduce_candidates[i] if i < len(reduce_candidates) else (None, None)
        
        # Build provenance
        sources = ["Response Curves"]
        if mmm_result and to_ch in mmm_result.get("contributions", {}): sources.append("MMM")
        if attribution:
            for attr_model in ["markov", "position_based", "linear"]:
                if to_ch in attribution.get(attr_model, {}): sources.append(attr_model.replace("_"," ").title() + " Attribution"); break
        
        # Historical context
        roi_trend_qoq = to_d["trends"].get("qoq", {}).get("roi", {})
        roi_dir = roi_trend_qoq.get("direction", "flat")
        roi_chg = roi_trend_qoq.get("change_pct", 0)
        
        # Compute specific $ amounts
        monthly_spend = to_d["spend"] / 12
        increase_pct = min(to_d["headroom"] * 0.4, 35)
        monthly_increase = monthly_spend * increase_pct / 100
        annual_increase = monthly_increase * 12
        expected_rev = annual_increase * to_d["marginal_roi"]
        
        # Build narrative
        parts = []
        parts.append(f"{to_d['label']} has delivered {to_d['roi']:.1f}x ROI over the reporting period, "
                     f"contributing ${to_d['revenue']:,.0f} from ${to_d['spend']:,.0f} in spend.")
        
        if roi_dir == "up":
            parts.append(f"Performance is improving — ROI increased {roi_chg:+.1f}% QoQ.")
        elif roi_dir == "down":
            parts.append(f"However, ROI has declined {roi_chg:.1f}% QoQ, which needs monitoring.")
        
        parts.append(f"The response curve ({to_d['model']}, R²={to_d['r2']:.2f}) shows {to_d['headroom']:.0f}% growth potential "
                     f"with a return of ${to_d['marginal_roi']:.2f} on the next dollar invested.")
        
        if from_ch and from_d:
            from_roi_trend = from_d["trends"].get("qoq", {}).get("roi", {})
            parts.append(f"Meanwhile, {from_d['label']} is {'declining' if from_roi_trend.get('direction')=='down' else 'near saturation'} "
                        f"at {from_d['headroom']:.0f}% headroom with marginal returns of only ${from_d['marginal_roi']:.2f} per dollar.")
            parts.append(f"Recommendation: Shift ${monthly_increase:,.0f}/month from {from_d['label']} to {to_d['label']}.")
        else:
            parts.append(f"Recommendation: Increase {to_d['label']} spend by ${monthly_increase:,.0f}/month (${annual_increase:,.0f}/year).")
        
        parts.append(f"Expected impact: +${expected_rev:,.0f} annual revenue.")
        parts.append(f"Phased plan: Month 1 — test with {increase_pct*0.3:.0f}% increase (${monthly_increase*0.3:,.0f}). "
                    f"Month 2-3 — scale to full {increase_pct:.0f}% if CAC stays below ${to_d['cac']*1.15:,.0f}.")
        
        recs.append({
            "type": "REALLOCATE",
            "channel": to_ch,
            "from_channel": from_ch,
            "narrative": " ".join(parts),
            "action_summary": f"Shift ${monthly_increase:,.0f}/month {'from ' + from_d['label'] + ' ' if from_d else ''}to {to_d['label']}",
            "impact": round(expected_rev, 0),
            "monthly_amount": round(monthly_increase, 0),
            "confidence": "High" if to_d["r2"] > 0.5 else "Medium",
            "effort": "Low",
            "sources": sources,
            "trends": {
                "qoq_roi_change": roi_chg,
                "yoy_roi_change": to_d["trends"].get("yoy", {}).get("roi", {}).get("change_pct", 0),
            },
            "phased_plan": [
                {"month": "Month 1", "action": f"Test {increase_pct*0.3:.0f}% increase", "amount": round(monthly_increase*0.3, 0)},
                {"month": "Month 2-3", "action": f"Scale to {increase_pct:.0f}%", "amount": round(monthly_increase, 0), "condition": f"CAC < ${to_d['cac']*1.15:,.0f}"},
                {"month": "Month 4+", "action": "Monitor and sustain", "amount": round(monthly_increase, 0)},
            ],
        })
    
    # === DECLINING CHANNEL ALERTS ===
    for ch, d in sorted_channels:
        qoq_rev = d["trends"].get("qoq", {}).get("revenue", {})
        yoy_rev = d["trends"].get("yoy", {}).get("revenue", {})
        qoq_chg = qoq_rev.get("change_pct", 0)
        yoy_chg = yoy_rev.get("change_pct", 0)
        
        if qoq_chg < -10 or (qoq_chg < -5 and yoy_chg < -5):
            parts = []
            parts.append(f"{d['label']} revenue has declined {qoq_chg:.1f}% QoQ and {yoy_chg:.1f}% YoY.")
            
            # Check if spend increased while revenue declined
            qoq_spend = d["trends"].get("qoq", {}).get("spend", {}).get("change_pct", 0)
            if qoq_spend > 5:
                parts.append(f"Spending increased {qoq_spend:.1f}% during the same period — you're paying more for less.")
                parts.append("This suggests audience fatigue, creative degradation, or market-level cost inflation.")
            else:
                parts.append("This may indicate seasonal effects, competitive pressure, or channel saturation.")
            
            if d["headroom"] < 20:
                parts.append(f"Response curve confirms saturation at {d['headroom']:.0f}% headroom.")
            
            monthly_cut = d["spend"] / 12 * 0.2
            parts.append(f"Recommendation: Reduce spend by ${monthly_cut:,.0f}/month and reallocate to channels with growth potential.")
            
            sources = ["Trend Analysis", "Response Curves"]
            recs.append({
                "type": "DECLINING",
                "channel": ch,
                "narrative": " ".join(parts),
                "action_summary": f"Cut {d['label']} by ${monthly_cut:,.0f}/month — declining {qoq_chg:.1f}% QoQ",
                "impact": round(-monthly_cut * 12 * max(d["marginal_roi"], 0.5), 0),
                "confidence": "High" if abs(qoq_chg) > 15 else "Medium",
                "effort": "Low",
                "sources": sources,
                "trends": {"qoq_revenue": qoq_chg, "yoy_revenue": yoy_chg, "qoq_spend": qoq_spend},
            })
    
    # === CX FRICTION RECOMMENDATIONS ===
    if pillars and pillars.get("experience_suppression", {}).get("items"):
        for item in pillars["experience_suppression"]["items"][:3]:
            ch = item.get("channel", "")
            camp = item.get("campaign", "")
            suppressed = item.get("suppressed_revenue", 0)
            cvr = item.get("cvr", 0)
            br = item.get("bounce_rate", 0)
            
            parts = []
            parts.append(f"{camp} on {ch.replace('_',' ').title()} has a conversion rate of {cvr*100:.2f}%, significantly below the portfolio median.")
            if br > 0.5:
                parts.append(f"Bounce rate is {br*100:.0f}% — more than half of visitors leave immediately.")
            parts.append(f"This friction is suppressing an estimated ${suppressed:,.0f} in annual revenue.")
            parts.append(f"Recommendation: Audit landing page, test CTA variants, and review form UX. This is a no-media-spend fix — pure conversion optimization.")
            parts.append(f"Expected recovery: ${suppressed*0.3:,.0f} (30% of suppressed revenue, achievable in 60 days).")
            
            recs.append({
                "type": "FIX_CX",
                "channel": ch, "campaign": camp,
                "narrative": " ".join(parts),
                "action_summary": f"Fix {camp} landing page — ${suppressed:,.0f} suppressed revenue",
                "impact": round(suppressed * 0.3, 0),
                "confidence": "High", "effort": "Medium",
                "sources": ["Leakage Analysis", "Funnel Analysis"],
            })
    
    # === ATTRIBUTION DISAGREEMENT INSIGHTS ===
    if attribution:
        lt = attribution.get("last_touch", {})
        mk = attribution.get("markov", {})
        if lt and mk:
            for ch in lt:
                lt_v = float(lt.get(ch, 0))
                mk_v = float(mk.get(ch, 0))
                if lt_v > 0 and mk_v > 0 and mk_v / lt_v > 1.8:
                    d = ch_data.get(ch, {})
                    parts = []
                    parts.append(f"{d.get('label', ch)}: Markov attribution credits ${mk_v:,.0f} but last-touch only credits ${lt_v:,.0f}.")
                    parts.append("This means this channel assists conversions on other channels — it's an enabler, not a closer.")
                    parts.append("Cutting this channel based on last-touch data would damage downstream performance.")
                    parts.append(f"Recommendation: Maintain or increase spend. This channel's true value is {mk_v/lt_v:.1f}x what last-touch suggests.")
                    
                    recs.append({
                        "type": "HIDDEN_VALUE",
                        "channel": ch,
                        "narrative": " ".join(parts),
                        "action_summary": f"Don't cut {d.get('label', ch)} — Markov shows {mk_v/lt_v:.1f}x hidden value",
                        "impact": round(mk_v - lt_v, 0),
                        "confidence": "High", "effort": "None",
                        "sources": ["Markov Attribution", "Last-Touch Attribution"],
                    })
    
    # Sort by absolute impact
    recs.sort(key=lambda x: abs(x.get("impact", 0)), reverse=True)
    for i, r in enumerate(recs):
        r["id"] = f"INSIGHT-{i+1:03d}"
        r["priority"] = i + 1
        r.setdefault("campaign", "")
        r.setdefault("from_channel", "")
        r.setdefault("sources", [])
        r.setdefault("phased_plan", [])
        r.setdefault("trends", {})
    
    return recs
