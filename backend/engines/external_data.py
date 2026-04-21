"""
External Data Engine — Competitive, Events, Market Trends
==========================================================
Processes 3 CSV upload types and generates enriched recommendations.
Integrates with optimizer (cost adjustment, competitive floors),
forecasting (event holidays, trend regressors), and diagnostics (benchmarks).
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
#  CSV 1: COMPETITIVE INTELLIGENCE
# ═══════════════════════════════════════════════════════

def process_competitive_data(comp_df: pd.DataFrame, our_data: pd.DataFrame) -> Dict:
    """Process competitive intelligence CSV into actionable metrics."""
    result = {"share_of_voice": {}, "competitive_pressure": {}, "recommendations": [], "summary": {}}
    
    # Normalize channel names
    comp_df["channel"] = comp_df["channel"].str.lower().str.strip().str.replace(" ", "_")
    
    # Our spend per channel
    our_spend = our_data.groupby("channel")["spend"].sum().to_dict()
    
    # Competitor spend per channel (latest period)
    latest_date = comp_df["date"].max()
    latest = comp_df[comp_df["date"] == latest_date]
    
    for ch in our_data["channel"].unique():
        our_s = our_spend.get(ch, 0)
        comp_s = float(latest[latest["channel"] == ch]["estimated_spend"].sum())
        total_market = our_s + comp_s
        
        sov = our_s / max(total_market, 1)
        cpi = sov  # Competitive Pressure Index = our share of voice
        
        result["share_of_voice"][ch] = {
            "our_spend": round(our_s, 0),
            "competitor_spend": round(comp_s, 0),
            "total_market": round(total_market, 0),
            "share_of_voice": round(sov, 3),
            "competitive_pressure_index": round(cpi, 3),
        }
        result["competitive_pressure"][ch] = round(cpi, 3)
    
    # Competitor trends (spend growth)
    if len(comp_df["date"].unique()) >= 2:
        dates = sorted(comp_df["date"].unique())
        early = comp_df[comp_df["date"] == dates[0]]
        late = comp_df[comp_df["date"] == dates[-1]]
        for ch in comp_df["channel"].unique():
            early_s = float(early[early["channel"] == ch]["estimated_spend"].sum())
            late_s = float(late[late["channel"] == ch]["estimated_spend"].sum())
            if early_s > 0:
                growth = (late_s - early_s) / early_s * 100
                cpi = result["competitive_pressure"].get(ch, 0.5)
                
                # DEFEND: competitor increasing spend on our strong channels
                if growth > 30 and cpi > 0.3:
                    competitors = latest[latest["channel"] == ch]["competitor"].unique()
                    result["recommendations"].append({
                        "type": "DEFEND", "channel": ch,
                        "narrative": (
                            f"{ch.replace('_',' ').title()}: Competitor spend increased {growth:.0f}% "
                            f"({', '.join(competitors)}). Your share of voice is {cpi*100:.0f}%. "
                            f"Maintain or increase budget to protect position. If you cut here, "
                            f"you'll lose impression share and CPC will rise as competitors bid more aggressively."
                        ),
                        "action_summary": f"Defend {ch.replace('_',' ').title()} — competitors up {growth:.0f}%",
                        "impact": round(our_spend.get(ch, 0) * 0.15, 0),
                        "confidence": "High", "effort": "Low",
                        "sources": ["Competitive Intelligence", "Share of Voice Analysis"],
                    })
                
                # OPPORTUNITY: competitor decreasing spend
                elif growth < -20:
                    result["recommendations"].append({
                        "type": "OPPORTUNITY", "channel": ch,
                        "narrative": (
                            f"{ch.replace('_',' ').title()}: Competitor spend dropped {abs(growth):.0f}%. "
                            f"This creates a window to gain share at lower cost. "
                            f"CPCs should decrease as auction pressure eases. "
                            f"Consider increasing spend by 15-20% to capture the gap."
                        ),
                        "action_summary": f"Opportunity on {ch.replace('_',' ').title()} — competitors down {abs(growth):.0f}%",
                        "impact": round(our_spend.get(ch, 0) * 0.10, 0),
                        "confidence": "Medium", "effort": "Low",
                        "sources": ["Competitive Intelligence"],
                    })
    
    # DIFFERENTIATE: high keyword overlap
    if "keyword_overlap" in comp_df.columns:
        for ch in comp_df["channel"].unique():
            overlap = comp_df[comp_df["channel"] == ch]["keyword_overlap"].mean()
            if overlap > 0.5:
                result["recommendations"].append({
                    "type": "DIFFERENTIATE", "channel": ch,
                    "narrative": (
                        f"{ch.replace('_',' ').title()}: {overlap*100:.0f}% keyword overlap with competitors. "
                        f"You're bidding on the same terms, driving up costs for everyone. "
                        f"Diversify to long-tail keywords, increase brand terms, or shift budget "
                        f"to content marketing for organic differentiation."
                    ),
                    "action_summary": f"Differentiate on {ch.replace('_',' ').title()} — {overlap*100:.0f}% keyword overlap",
                    "impact": round(our_spend.get(ch, 0) * 0.08, 0),
                    "confidence": "Medium", "effort": "Medium",
                    "sources": ["Competitive Intelligence", "Keyword Analysis"],
                })
    
    # Summary
    avg_sov = np.mean([v["share_of_voice"] for v in result["share_of_voice"].values()]) if result["share_of_voice"] else 0
    n_competitors = comp_df["competitor"].nunique() if "competitor" in comp_df.columns else 0
    result["summary"] = {
        "avg_share_of_voice": round(avg_sov, 3),
        "n_competitors": n_competitors,
        "n_channels_tracked": len(result["share_of_voice"]),
        "at_risk_channels": sum(1 for v in result["share_of_voice"].values() if v["competitive_pressure_index"] < 0.25),
    }
    
    return result


# ═══════════════════════════════════════════════════════
#  CSV 2: MARKET EVENTS
# ═══════════════════════════════════════════════════════

def process_market_events(events_df: pd.DataFrame, our_data: pd.DataFrame) -> Dict:
    """Process market events CSV into optimizer constraints and recommendations."""
    result = {"events": [], "recommendations": [], "prophet_holidays": [], "optimizer_adjustments": {}, "summary": {}}
    
    now = pd.Timestamp.now()
    our_spend = our_data.groupby("channel")["spend"].sum().to_dict()
    our_rev = our_data.groupby("channel")["revenue"].sum().to_dict()
    
    for _, row in events_df.iterrows():
        event_date = pd.to_datetime(row.get("event_date", ""))
        event_end = pd.to_datetime(row.get("event_end_date", "")) if pd.notna(row.get("event_end_date")) else event_date
        event_type = str(row.get("event_type", "")).lower()
        event_name = str(row.get("event_name", ""))
        direction = str(row.get("impact_direction", "neutral")).lower()
        magnitude = str(row.get("impact_magnitude", "medium")).lower()
        impact_pct = float(row.get("impact_pct", 0)) if pd.notna(row.get("impact_pct")) else None
        affected_ch = str(row.get("affected_channels", "")).split(";") if pd.notna(row.get("affected_channels")) else []
        affected_ch = [c.strip().lower().replace(" ", "_") for c in affected_ch if c.strip()]
        confidence = str(row.get("confidence", "estimated")).lower()
        
        days_away = (event_date - now).days
        is_upcoming = days_away > 0
        is_recent = -90 < days_away <= 0
        
        event = {
            "date": str(event_date.date()),
            "end_date": str(event_end.date()),
            "type": event_type, "name": event_name,
            "direction": direction, "magnitude": magnitude,
            "impact_pct": impact_pct,
            "affected_channels": affected_ch,
            "days_away": days_away,
            "is_upcoming": is_upcoming,
            "confidence": confidence,
        }
        result["events"].append(event)
        
        # Prophet holidays
        mag_scale = {"low": 0.05, "medium": 0.15, "high": 0.30}.get(magnitude, 0.15)
        if impact_pct: mag_scale = abs(impact_pct) / 100
        result["prophet_holidays"].append({
            "holiday": event_name.replace(" ", "_"),
            "ds": str(event_date.date()),
            "lower_window": 0,
            "upper_window": max(0, (event_end - event_date).days),
            "prior_scale": mag_scale * (1 if direction == "positive" else -1),
        })
        
        # Optimizer adjustments for upcoming events
        if is_upcoming and affected_ch:
            for ch in affected_ch:
                if ch not in result["optimizer_adjustments"]:
                    result["optimizer_adjustments"][ch] = {"weight_modifier": 1.0, "events": []}
                modifier = 1 + (impact_pct / 100 if impact_pct else (0.15 if direction == "positive" else -0.10))
                result["optimizer_adjustments"][ch]["weight_modifier"] *= modifier
                result["optimizer_adjustments"][ch]["events"].append(event_name)
        
        # Recommendations
        if is_upcoming and days_away <= 90:
            if event_type in ["seasonal_peak", "internal_launch"] and direction == "positive":
                ch_list = ", ".join([c.replace("_", " ").title() for c in affected_ch[:3]]) or "all channels"
                weeks = max(1, days_away // 7)
                result["recommendations"].append({
                    "type": "PREPARE", "channel": affected_ch[0] if affected_ch else "",
                    "narrative": (
                        f"{event_name} is {weeks} weeks away ({event_date.strftime('%b %d')}). "
                        f"Expected impact: {'+' if direction=='positive' else ''}{impact_pct or magnitude}% on {ch_list}. "
                        f"Based on historical patterns, start ramping budgets now — "
                        f"pre-load creative assets and increase budget allocation on affected channels "
                        f"2-3 weeks before the event for maximum impact. "
                        f"Confidence: {confidence}."
                    ),
                    "action_summary": f"Prepare for {event_name} — {weeks} weeks out",
                    "impact": round(sum(our_rev.get(c, 0) for c in affected_ch) * (abs(impact_pct or 10) / 100) * 0.3, 0),
                    "confidence": "High" if confidence == "confirmed" else "Medium",
                    "effort": "Medium",
                    "sources": ["Market Events Calendar", row.get("source", "")],
                    "event_date": str(event_date.date()),
                })
            
            elif event_type in ["competitor_launch", "cost_increase"] and direction == "negative":
                ch_list = ", ".join([c.replace("_", " ").title() for c in affected_ch[:3]]) or "affected channels"
                result["recommendations"].append({
                    "type": "MITIGATE", "channel": affected_ch[0] if affected_ch else "",
                    "narrative": (
                        f"{event_name} expected on {event_date.strftime('%b %d')}. "
                        f"Anticipated impact: {impact_pct or magnitude}% on {ch_list}. "
                        f"Prepare by diversifying spend away from affected channels, "
                        f"building organic content as a hedge, and pre-negotiating ad rates. "
                        f"Source: {row.get('source', 'market intelligence')}."
                    ),
                    "action_summary": f"Mitigate risk from {event_name}",
                    "impact": round(sum(our_spend.get(c, 0) for c in affected_ch) * (abs(impact_pct or 10) / 100), 0),
                    "confidence": "High" if confidence == "confirmed" else "Medium",
                    "effort": "Medium",
                    "sources": ["Market Events Calendar", row.get("source", "")],
                })
            
            elif event_type in ["competitor_exit", "cost_decrease"] and direction == "positive":
                ch_list = ", ".join([c.replace("_", " ").title() for c in affected_ch[:3]]) or "affected channels"
                result["recommendations"].append({
                    "type": "CAPITALIZE", "channel": affected_ch[0] if affected_ch else "",
                    "narrative": (
                        f"{event_name}: {ch_list} costs are expected to drop. "
                        f"This is a window to acquire reach and conversions at below-normal rates. "
                        f"Increase spend by 15-25% on affected channels while costs are favorable. "
                        f"Expected duration: {(event_end - event_date).days or 30} days."
                    ),
                    "action_summary": f"Capitalize on {event_name}",
                    "impact": round(sum(our_spend.get(c, 0) for c in affected_ch) * 0.12, 0),
                    "confidence": "Medium", "effort": "Low",
                    "sources": ["Market Events Calendar"],
                })
    
    result["summary"] = {
        "total_events": len(result["events"]),
        "upcoming_events": sum(1 for e in result["events"] if e["is_upcoming"]),
        "positive_upcoming": sum(1 for e in result["events"] if e["is_upcoming"] and e["direction"] == "positive"),
        "negative_upcoming": sum(1 for e in result["events"] if e["is_upcoming"] and e["direction"] == "negative"),
        "channels_affected": len(result["optimizer_adjustments"]),
    }
    
    return result


# ═══════════════════════════════════════════════════════
#  CSV 3: MARKET TRENDS & BENCHMARKS
# ═══════════════════════════════════════════════════════

def process_market_trends(trends_df: pd.DataFrame, our_data: pd.DataFrame) -> Dict:
    """Process market trends CSV into cost adjustments, benchmarks, and recommendations."""
    result = {
        "cost_adjustments": {},
        "benchmarks": {},
        "category_growth": None,
        "search_interest": {},
        "recommendations": [],
        "summary": {},
    }
    
    conv_col = "conversions" if "conversions" in our_data.columns else "conv"
    our_metrics = {}
    for ch in our_data["channel"].unique():
        cr = our_data[our_data["channel"] == ch]
        s, rv, cv, cl, im = cr["spend"].sum(), cr["revenue"].sum(), cr[conv_col].sum(), cr["clicks"].sum(), cr.get("impressions", cr.get("imps", pd.Series([0]))).sum()
        our_metrics[ch] = {
            "ctr": float(cl / max(im, 1)),
            "cvr": float(cv / max(cl, 1)),
            "cac": float(s / max(cv, 1)),
            "roas": float(rv / max(s, 1)),
            "spend": float(s), "revenue": float(rv),
        }
    
    # Process CPC/CPM trends
    for metric_type in ["cpc_trend", "cpm_trend"]:
        trend_rows = trends_df[trends_df["metric_type"] == metric_type].sort_values("date")
        if len(trend_rows) < 2:
            continue
        for ch in trend_rows["channel"].dropna().unique():
            ch_rows = trend_rows[trend_rows["channel"] == ch].sort_values("date")
            if len(ch_rows) >= 2:
                first_val = float(ch_rows.iloc[0]["value"])
                last_val = float(ch_rows.iloc[-1]["value"])
                yoy_chg = float(ch_rows["yoy_change_pct"].mean()) if "yoy_change_pct" in ch_rows.columns and ch_rows["yoy_change_pct"].notna().any() else 0
                
                inflation_factor = last_val / max(first_val, 0.01)
                result["cost_adjustments"][ch] = {
                    "metric": metric_type,
                    "current_value": round(last_val, 2),
                    "trend_start": round(first_val, 2),
                    "inflation_factor": round(inflation_factor, 3),
                    "yoy_change_pct": round(yoy_chg, 1),
                }
                
                # COST_ALERT if rising >15%
                if yoy_chg > 15:
                    cost_name = "CPC" if "cpc" in metric_type else "CPM"
                    result["recommendations"].append({
                        "type": "COST_ALERT", "channel": ch,
                        "narrative": (
                            f"{ch.replace('_',' ').title()} {cost_name} has increased {yoy_chg:.0f}% year-over-year "
                            f"(${first_val:.2f} → ${last_val:.2f}). This means the same budget buys "
                            f"{(1-1/inflation_factor)*100:.0f}% fewer impressions/clicks than last year. "
                            f"Consider shifting {round(yoy_chg*0.5):.0f}% of budget to channels with stable or declining costs, "
                            f"or negotiate volume discounts. Source: {ch_rows.iloc[-1].get('benchmark_source', 'market data')}."
                        ),
                        "action_summary": f"Cost alert: {ch.replace('_',' ').title()} {cost_name} up {yoy_chg:.0f}% YoY",
                        "impact": round(our_metrics.get(ch, {}).get("spend", 0) * yoy_chg / 100 * 0.5, 0),
                        "confidence": "High", "effort": "Low",
                        "sources": ["Market Trends", ch_rows.iloc[-1].get("benchmark_source", "")],
                    })
    
    # Process benchmarks
    for metric_type in ["channel_benchmark_ctr", "channel_benchmark_cvr", "channel_benchmark_cac", "channel_benchmark_roas"]:
        bm_rows = trends_df[trends_df["metric_type"] == metric_type]
        for _, row in bm_rows.iterrows():
            ch = str(row.get("channel", "")).lower().strip().replace(" ", "_")
            if not ch: continue
            metric_short = metric_type.replace("channel_benchmark_", "")
            if ch not in result["benchmarks"]:
                result["benchmarks"][ch] = {}
            result["benchmarks"][ch][metric_short] = float(row["value"])
            
            # BENCHMARK recommendations
            our_val = our_metrics.get(ch, {}).get(metric_short, None)
            bm_val = float(row["value"])
            if our_val is not None and bm_val > 0:
                ratio = our_val / bm_val
                if metric_short in ["ctr", "cvr", "roas"] and ratio < 0.7:
                    result["recommendations"].append({
                        "type": "BENCHMARK", "channel": ch,
                        "narrative": (
                            f"{ch.replace('_',' ').title()} {metric_short.upper()} is {our_val*100 if metric_short in ['ctr','cvr'] else our_val:.2f}"
                            f"{'%' if metric_short in ['ctr','cvr'] else 'x'} vs industry benchmark "
                            f"{bm_val*100 if metric_short in ['ctr','cvr'] else bm_val:.2f}"
                            f"{'%' if metric_short in ['ctr','cvr'] else 'x'}. "
                            f"That's {(1-ratio)*100:.0f}% below standard. "
                            f"{'Review ad copy, targeting, and landing pages.' if metric_short in ['ctr','cvr'] else 'Review channel strategy and audience quality.'} "
                            f"Closing this gap could unlock significant incremental performance."
                        ),
                        "action_summary": f"{ch.replace('_',' ').title()} {metric_short.upper()} {(1-ratio)*100:.0f}% below benchmark",
                        "impact": round(our_metrics.get(ch, {}).get("revenue", 0) * (1 - ratio) * 0.2, 0),
                        "confidence": "High", "effort": "Medium",
                        "sources": ["Market Benchmarks", row.get("benchmark_source", "")],
                    })
                elif metric_short == "cac" and ratio > 1.4:
                    result["recommendations"].append({
                        "type": "BENCHMARK", "channel": ch,
                        "narrative": (
                            f"{ch.replace('_',' ').title()} CAC is ${our_val:,.0f} vs industry benchmark ${bm_val:,.0f}. "
                            f"That's {(ratio-1)*100:.0f}% above standard. "
                            f"Tighten audience targeting, review bidding strategy, and audit conversion paths."
                        ),
                        "action_summary": f"{ch.replace('_',' ').title()} CAC {(ratio-1)*100:.0f}% above benchmark",
                        "impact": round((our_val - bm_val) * our_metrics.get(ch, {}).get("spend", 0) / max(our_val, 1) * 0.3, 0),
                        "confidence": "High", "effort": "Medium",
                        "sources": ["Market Benchmarks", row.get("benchmark_source", "")],
                    })
    
    # Category growth
    growth_rows = trends_df[trends_df["metric_type"] == "category_growth"]
    if len(growth_rows) > 0:
        result["category_growth"] = {
            "latest_value": round(float(growth_rows.iloc[-1]["value"]), 1),
            "trend": "up" if float(growth_rows.iloc[-1]["value"]) > 0 else "down",
            "n_periods": len(growth_rows),
        }
    
    # Search interest
    interest_rows = trends_df[trends_df["metric_type"] == "search_interest"]
    for ch in interest_rows["channel"].dropna().unique():
        ch_rows = interest_rows[interest_rows["channel"] == ch].sort_values("date")
        result["search_interest"][ch] = {
            "latest": float(ch_rows.iloc[-1]["value"]),
            "trend_direction": "up" if float(ch_rows.iloc[-1].get("yoy_change_pct", 0)) > 0 else "down",
            "data_points": len(ch_rows),
        }
    
    result["summary"] = {
        "n_cost_adjustments": len(result["cost_adjustments"]),
        "n_benchmarks": sum(len(v) for v in result["benchmarks"].values()),
        "category_growth": result["category_growth"]["latest_value"] if result["category_growth"] else None,
        "n_recommendations": len(result["recommendations"]),
    }
    
    return result


# ═══════════════════════════════════════════════════════
#  UNIFIED: Merge all external recs with smart recs
# ═══════════════════════════════════════════════════════

def merge_external_recommendations(smart_recs: List, comp_result: Dict = None, events_result: Dict = None, trends_result: Dict = None) -> List:
    """Merge externally-sourced recommendations into the smart recs list."""
    all_recs = list(smart_recs)
    
    if comp_result:
        for r in comp_result.get("recommendations", []):
            r.setdefault("campaign", "")
            r.setdefault("from_channel", "")
            r.setdefault("phased_plan", [])
            r.setdefault("trends", {})
            all_recs.append(r)
    
    if events_result:
        for r in events_result.get("recommendations", []):
            r.setdefault("campaign", "")
            r.setdefault("from_channel", "")
            r.setdefault("phased_plan", [])
            r.setdefault("trends", {})
            all_recs.append(r)
    
    if trends_result:
        for r in trends_result.get("recommendations", []):
            r.setdefault("campaign", "")
            r.setdefault("from_channel", "")
            r.setdefault("phased_plan", [])
            r.setdefault("trends", {})
            all_recs.append(r)
    
    # Re-sort and re-number
    all_recs.sort(key=lambda x: abs(x.get("impact", 0)), reverse=True)
    for i, r in enumerate(all_recs):
        r["id"] = f"INSIGHT-{i+1:03d}"
        r["priority"] = i + 1
    
    return all_recs
