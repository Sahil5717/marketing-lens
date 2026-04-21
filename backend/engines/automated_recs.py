"""
Automated Recommendation Engine + Value Realization + Model Recalibration (Phase 3)

1. Automated Recommendations: Statistical triggers instead of fixed rules
   - Anomaly-triggered recommendations
   - Trend-triggered recommendations
   - Model-confidence-triggered recommendations

2. Value Realization Tracker: Actual vs plan comparison over time

3. Continuous Model Recalibration: Detect drift, signal retrain needs
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from scipy import stats


# ═══════════════════════════════════════
# 1. AUTOMATED RECOMMENDATIONS
# ═══════════════════════════════════════

def automated_recommendations(
    current_data: pd.DataFrame,
    historical_data: pd.DataFrame = None,
    response_curves: Dict = None,
    attribution_results: Dict = None,
    significance_level: float = 0.05,
) -> List[Dict]:
    """
    Generate recommendations using statistical triggers instead of fixed thresholds.
    More sophisticated than Phase 1 rule-based engine.
    """
    recs = []
    rev_col = "revenue" if "revenue" in current_data.columns else "rev"
    ch_col = "channel" if "channel" in current_data.columns else "ch"
    
    # Trigger 1: Anomaly-based (z-score > 2 on recent performance change)
    recs.extend(_anomaly_triggers(current_data, rev_col, ch_col))
    
    # Trigger 2: Trend-based (statistically significant trend change)
    recs.extend(_trend_triggers(current_data, rev_col, ch_col))
    
    # Trigger 3: Efficiency deterioration (ROI declining over rolling window)
    recs.extend(_efficiency_triggers(current_data, rev_col, ch_col))
    
    # Trigger 4: Response curve saturation approach
    if response_curves:
        recs.extend(_saturation_triggers(current_data, response_curves, ch_col))
    
    # Trigger 5: Attribution shift detection
    if attribution_results and len(attribution_results) >= 2:
        recs.extend(_attribution_shift_triggers(attribution_results))
    
    recs.sort(key=lambda r: r.get("statistical_confidence", 0), reverse=True)
    for i, r in enumerate(recs):
        r["id"] = f"AUTO-{i+1:03d}"
        r["engine"] = "automated_model_driven"
    
    return recs


def _anomaly_triggers(df, rev_col, ch_col):
    """Detect anomalous recent performance and generate recommendations."""
    recs = []
    time_col = "month" if "month" in df.columns else "date"
    
    for ch in df[ch_col].unique():
        ch_data = df[df[ch_col] == ch]
        monthly = ch_data.groupby(time_col).agg(
            revenue=(rev_col, "sum"),
            spend=("spend", "sum"),
        ).reset_index().sort_values(time_col)
        
        if len(monthly) < 6:
            continue
        
        monthly["roi"] = (monthly["revenue"] - monthly["spend"]) / monthly["spend"].clip(lower=1)
        
        # Check if last 2 months are anomalous
        roi_values = monthly["roi"].values
        recent = roi_values[-2:]
        historical = roi_values[:-2]
        
        if len(historical) < 3:
            continue
        
        mean_hist = np.mean(historical)
        std_hist = np.std(historical)
        
        if std_hist == 0:
            continue
        
        for val in recent:
            z = (val - mean_hist) / std_hist
            
            if z < -2.0:
                recs.append({
                    "type": "INVESTIGATE",
                    "trigger": "anomaly_detection",
                    "channel": ch,
                    "rationale": f"ROI dropped to {val:.2f}x, which is {abs(z):.1f} standard deviations below historical mean ({mean_hist:.2f}x). Statistically significant deterioration.",
                    "action": "Immediate investigation required — check creative fatigue, audience saturation, or competitive changes",
                    "statistical_confidence": min(0.99, stats.norm.cdf(abs(z))),
                    "z_score": round(z, 2),
                    "severity": "high" if z < -3 else "medium",
                })
            elif z > 2.5:
                recs.append({
                    "type": "SCALE",
                    "trigger": "anomaly_detection",
                    "channel": ch,
                    "rationale": f"ROI spiked to {val:.2f}x, {z:.1f}σ above mean. If sustainable, this channel has untapped potential.",
                    "action": "Validate spike is sustainable (not seasonal/one-off), then increase budget by 15-25%",
                    "statistical_confidence": min(0.99, stats.norm.cdf(z)),
                    "z_score": round(z, 2),
                    "severity": "medium",
                })
    
    return recs


def _trend_triggers(df, rev_col, ch_col):
    """Detect statistically significant trends."""
    recs = []
    time_col = "month" if "month" in df.columns else "date"
    
    for ch in df[ch_col].unique():
        ch_data = df[df[ch_col] == ch]
        monthly = ch_data.groupby(time_col).agg(
            revenue=(rev_col, "sum"),
            spend=("spend", "sum"),
        ).reset_index().sort_values(time_col)
        
        if len(monthly) < 6:
            continue
        
        monthly["roi"] = (monthly["revenue"] - monthly["spend"]) / monthly["spend"].clip(lower=1)
        
        # Linear regression on ROI over time
        x = np.arange(len(monthly))
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, monthly["roi"].values)
        
        if p_value < 0.1 and abs(slope) > 0.01:
            if slope < 0:
                recs.append({
                    "type": "REDUCE",
                    "trigger": "trend_detection",
                    "channel": ch,
                    "rationale": f"ROI has a statistically significant downward trend (slope: {slope:.3f}/month, p={p_value:.3f}). At this rate, ROI will fall below breakeven in {int(-intercept/slope) if slope != 0 else 99} months.",
                    "action": "Reduce spend gradually while testing new creative/audiences",
                    "statistical_confidence": 1 - p_value,
                    "trend_slope": round(slope, 4),
                    "p_value": round(p_value, 4),
                    "severity": "medium",
                })
            else:
                recs.append({
                    "type": "SCALE",
                    "trigger": "trend_detection",
                    "channel": ch,
                    "rationale": f"ROI has a statistically significant upward trend (slope: {slope:.3f}/month, p={p_value:.3f}). Channel is improving over time.",
                    "action": "Increase budget by 10-20% to capitalize on improving efficiency",
                    "statistical_confidence": 1 - p_value,
                    "trend_slope": round(slope, 4),
                    "p_value": round(p_value, 4),
                    "severity": "low",
                })
    
    return recs


def _efficiency_triggers(df, rev_col, ch_col):
    """Detect efficiency deterioration using rolling window comparison."""
    recs = []
    time_col = "month" if "month" in df.columns else "date"
    
    for ch in df[ch_col].unique():
        ch_data = df[df[ch_col] == ch]
        monthly = ch_data.groupby(time_col).agg(
            revenue=(rev_col, "sum"),
            spend=("spend", "sum"),
        ).reset_index().sort_values(time_col)
        
        if len(monthly) < 8:
            continue
        
        # Compare last 3 months vs previous 3 months
        try:
            recent_roi = ((monthly["revenue"].tail(3).sum() - monthly["spend"].tail(3).sum()) / 
                          max(monthly["spend"].tail(3).sum(), 1))
            prior_roi = ((monthly["revenue"].iloc[-6:-3].sum() - monthly["spend"].iloc[-6:-3].sum()) / 
                         max(monthly["spend"].iloc[-6:-3].sum(), 1))
            if prior_roi > 0 and recent_roi / prior_roi < 0.7:
                recs.append({
                    "type": "REVIEW",
                    "trigger": "efficiency_deterioration",
                    "channel": ch,
                    "rationale": f"Recent 3-month ROI ({recent_roi:.2f}x) is {(1-recent_roi/prior_roi)*100:.0f}% lower than prior 3-month ({prior_roi:.2f}x). Efficiency is deteriorating.",
                    "action": "Review audience fatigue, creative rotation, competitive landscape",
                    "statistical_confidence": 0.85,
                    "severity": "high" if recent_roi / prior_roi < 0.5 else "medium",
                })
        except Exception:
            continue
    
    return recs


def _saturation_triggers(df, curves, ch_col):
    """Detect channels approaching or past saturation."""
    recs = []
    
    for ch, curve in curves.items():
        headroom = curve.get("headroom_pct", curve.get("hd", 50))
        marginal = curve.get("marginal_roi", curve.get("mROI", 1))
        
        if headroom < 5 and marginal < 1.0:
            recs.append({
                "type": "REDUCE",
                "trigger": "saturation_approach",
                "channel": ch,
                "rationale": f"Channel is past saturation point ({headroom:.0f}% headroom, marginal ROI {marginal:.2f}x). Additional spend produces negative returns.",
                "action": "Cut spend to efficiency zone and reallocate to channels with headroom",
                "statistical_confidence": 0.90 if curve.get("r_squared", curve.get("r2", 0)) > 0.7 else 0.60,
                "severity": "high",
            })
        elif headroom > 40 and marginal > 3.0:
            recs.append({
                "type": "SCALE",
                "trigger": "headroom_opportunity",
                "channel": ch,
                "rationale": f"Channel has {headroom:.0f}% headroom with marginal ROI {marginal:.2f}x. Significant scaling opportunity.",
                "action": f"Increase budget by {min(30, headroom*0.4):.0f}% — projected marginal return justifies investment",
                "statistical_confidence": 0.85 if curve.get("r_squared", curve.get("r2", 0)) > 0.7 else 0.55,
                "severity": "low",
            })
    
    return recs


def _attribution_shift_triggers(attribution_results):
    """Detect significant shifts between attribution models."""
    recs = []
    
    if "last_touch" not in attribution_results or "linear" not in attribution_results:
        return recs
    
    lt_raw = attribution_results["last_touch"]
    ln_raw = attribution_results["linear"]
    
    # Handle both DataFrame and dict formats
    import pandas as pd
    if isinstance(lt_raw, pd.DataFrame):
        lt = lt_raw.groupby("channel")["attributed_revenue"].sum().to_dict()
    elif isinstance(lt_raw, dict):
        lt = {k: float(v) if not isinstance(v, dict) else v.get("attributed_revenue", 0) for k, v in lt_raw.items()}
    else:
        return recs
    
    if isinstance(ln_raw, pd.DataFrame):
        ln = ln_raw.groupby("channel")["attributed_revenue"].sum().to_dict()
    elif isinstance(ln_raw, dict):
        ln = {k: float(v) if not isinstance(v, dict) else v.get("attributed_revenue", 0) for k, v in ln_raw.items()}
    else:
        return recs
    
    for ch in set(list(lt.keys()) + list(ln.keys())):
        try:
            lt_val = float(lt.get(ch, 0))
            ln_val = float(ln.get(ch, 0))
            if lt_val > 0 and ln_val / lt_val > 2.0:
                recs.append({
                    "type": "INVESTIGATE",
                    "trigger": "attribution_divergence",
                    "channel": ch,
                    "rationale": f"Linear attribution ({ln_val:,.0f}) is {ln_val/lt_val:.1f}x higher than last-touch ({lt_val:,.0f}).",
                    "action": "Do NOT cut based on platform-reported ROAS. Run incrementality test.",
                    "statistical_confidence": 0.75,
                    "severity": "medium",
                })
        except Exception:
            continue
    
    return recs


# ═══════════════════════════════════════
# 2. VALUE REALIZATION TRACKER
# ═══════════════════════════════════════

def track_realization(
    planned: Dict[str, float],
    actual: pd.DataFrame,
    time_col: str = "month",
    rev_col: str = "revenue",
) -> Dict:
    """
    Compare actual performance against the optimized plan.
    """
    actual_monthly = actual.groupby(time_col)[rev_col].sum().to_dict()
    
    periods = sorted(set(list(planned.keys()) + list(actual_monthly.keys())))
    
    tracking = []
    cum_planned = 0
    cum_actual = 0
    
    for period in periods:
        p = planned.get(period, 0)
        a = actual_monthly.get(period, None)
        cum_planned += p
        if a is not None:
            cum_actual += a
        
        tracking.append({
            "period": period,
            "planned": round(p, 0),
            "actual": round(a, 0) if a is not None else None,
            "variance": round(a - p, 0) if a is not None else None,
            "variance_pct": round((a - p) / p * 100, 1) if a is not None and p > 0 else None,
            "cumulative_planned": round(cum_planned, 0),
            "cumulative_actual": round(cum_actual, 0) if a is not None else None,
        })
    
    # Overall realization rate
    total_planned = sum(planned.values())
    total_actual = sum(v for v in actual_monthly.values() if v is not None)
    
    return {
        "tracking": tracking,
        "realization_rate": round(total_actual / total_planned * 100, 1) if total_planned > 0 else 0,
        "total_planned": round(total_planned, 0),
        "total_actual": round(total_actual, 0),
        "total_variance": round(total_actual - total_planned, 0),
        "on_track": total_actual >= total_planned * 0.9,
    }


# ═══════════════════════════════════════
# 3. MODEL RECALIBRATION
# ═══════════════════════════════════════

def check_model_drift(
    response_curves: Dict,
    recent_data: pd.DataFrame,
    drift_threshold: float = 0.20,
) -> Dict:
    """
    Check if response curve models still fit recent data well.
    If predictions deviate from actuals by > threshold, signal recalibration.
    """
    rev_col = "revenue" if "revenue" in recent_data.columns else "rev"
    ch_col = "channel" if "channel" in recent_data.columns else "ch"
    time_col = "month" if "month" in recent_data.columns else "date"
    
    drift_report = {}
    
    for ch, curve in response_curves.items():
        ch_data = recent_data[recent_data[ch_col] == ch]
        if len(ch_data) == 0:
            continue
        
        monthly = ch_data.groupby(time_col).agg(
            spend=("spend", "sum"),
            actual_revenue=(rev_col, "sum"),
        ).reset_index()
        
        if len(monthly) < 3:
            continue
        
        # Predict using current model
        a = curve.get("a", curve.get("params", {}).get("a", 1))
        b = curve.get("b", curve.get("params", {}).get("b", 0.5))
        
        monthly["predicted_revenue"] = monthly["spend"].apply(
            lambda s: a * np.power(max(s, 1), b)
        )
        
        # Calculate MAPE
        mape = np.mean(np.abs(
            (monthly["actual_revenue"] - monthly["predicted_revenue"]) / 
            monthly["actual_revenue"].clip(lower=1)
        ))
        
        # Trend in prediction error (is model getting worse?)
        errors = (monthly["actual_revenue"] - monthly["predicted_revenue"]).values
        if len(errors) >= 3:
            error_trend = np.polyfit(range(len(errors)), errors, 1)[0]
        else:
            error_trend = 0
        
        needs_recalibration = mape > drift_threshold or abs(error_trend) > monthly["actual_revenue"].mean() * 0.05
        
        drift_report[ch] = {
            "mape": round(float(mape * 100), 1),
            "error_trend": round(float(error_trend), 0),
            "error_trend_direction": "increasing" if error_trend > 0 else "decreasing",
            "needs_recalibration": needs_recalibration,
            "model_age_months": len(monthly),
            "recommendation": (
                "Recalibrate: model predictions deviating significantly from actuals"
                if needs_recalibration else
                "Model performing within acceptable range"
            ),
        }
    
    channels_needing_recal = [ch for ch, info in drift_report.items() if info["needs_recalibration"]]
    
    return {
        "channel_drift": drift_report,
        "channels_needing_recalibration": channels_needing_recal,
        "overall_health": "good" if len(channels_needing_recal) == 0 else (
            "warning" if len(channels_needing_recal) <= 2 else "critical"
        ),
        "recommendation": (
            f"{len(channels_needing_recal)} channel(s) need model recalibration: "
            f"{', '.join(channels_needing_recal)}" if channels_needing_recal else
            "All models performing within acceptable drift thresholds"
        ),
    }


if __name__ == "__main__":
    from mock_data import generate_all_data
    from response_curves import fit_response_curves
    from attribution import run_all_attribution
    
    data = generate_all_data()
    df = data["campaign_performance"]
    curves = fit_response_curves(df)
    attr = run_all_attribution(data["user_journeys"])
    
    print("=== Automated Recommendations ===")
    auto_recs = automated_recommendations(df, response_curves=curves, attribution_results=attr)
    print(f"{len(auto_recs)} model-driven recommendations generated")
    for r in auto_recs[:5]:
        print(f"  [{r['trigger']}] {r['type']}: {r.get('channel', 'N/A')} "
              f"(conf: {r['statistical_confidence']:.0%})")
    
    print("\n=== Model Drift Check ===")
    drift = check_model_drift(curves, df)
    print(f"Overall health: {drift['overall_health']}")
    print(f"Recalibration needed: {len(drift['channels_needing_recalibration'])} channels")
    for ch, info in drift["channel_drift"].items():
        print(f"  {ch}: MAPE={info['mape']:.1f}% {'⚠️ RECAL' if info['needs_recalibration'] else '✅'}")
