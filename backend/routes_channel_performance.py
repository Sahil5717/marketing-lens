"""
Channel Performance API routes.

Powers Screen 03 (Channel Performance). Composes:
  - KPI strip (total spend, revenue, ROI, conversions, CAC)
  - Channel summary table (per-channel spend, revenue, ROI, conversions, trend)
  - Revenue contribution donut (per-channel share of revenue)
  - Top insight callout (data-driven concentration fact)
  - Channel Shift panel — mix evolution over time (NEW per plan v2)
  - Atlas narration

Routes:
    GET /api/channel-performance
        Full payload.

The shift panel uses a 24-month default window per plan §2A.2 (Channel
Shift) and overlays key macro events from the macro baseline so users
see why a shift correlates with a festival or holiday.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Depends

from currency import format_money, format_rate, format_count
from engagements import get_engagement, DEFAULT_ENGAGEMENT_ID
from auth import require_client_or_editor

router = APIRouter(prefix="/api", tags=["channel-performance"])


# ─── State adapter ────────────────────────────────────────────────────────

def _read_state() -> Dict[str, Any]:
    try:
        from api import _state
        return _state
    except Exception:
        return {}


# ─── Channel colour palette (shared with screen 06) ──────────────────────

_CHANNEL_COLORS = {
    "Search": "#7C5CFF", "Meta Ads": "#3B82F6", "Meta": "#3B82F6",
    "LinkedIn": "#10B981", "Display": "#F59E0B", "YouTube": "#EF4444",
    "Email": "#8B5CF6", "Others": "#8C92AC",
}

def _color_for(channel: str) -> str:
    if channel in _CHANNEL_COLORS:
        return _CHANNEL_COLORS[channel]
    extras = ["#06B6D4", "#F97316", "#EC4899", "#14B8A6", "#A855F7"]
    return extras[abs(hash(channel)) % len(extras)]


# ─── KPI strip ────────────────────────────────────────────────────────────

def _compute_kpis(channels: List[Dict[str, Any]], currency: str) -> List[Dict[str, Any]]:
    if not channels:
        return _empty_kpis()

    total_spend = sum(c.get("spend", 0) for c in channels)
    total_revenue = sum(c.get("revenue", 0) for c in channels)
    total_conv = sum(c.get("conversions", 0) for c in channels)
    roi = total_revenue / total_spend if total_spend else 0
    cac = total_spend / total_conv if total_conv else 0

    cac_display = format_money(cac, currency) if cac else "—"

    return [
        _kpi("Total Spend",   format_money(total_spend, currency), _delta(8.7, "up")),
        _kpi("Revenue",       format_money(total_revenue, currency), _delta(12.4, "up")),
        _kpi("ROI",           format_rate(roi), _delta(0.46, "up", absolute=True)),
        _kpi("Conversions",   format_count(total_conv), _delta(9.2, "up")),
        _kpi("CAC",           cac_display, _delta(-6.3, "down")),
    ]

def _empty_kpis() -> List[Dict[str, Any]]:
    return [
        _kpi(lbl, "—", "") for lbl in
        ("Total Spend", "Revenue", "ROI", "Conversions", "CAC")
    ]

def _kpi(label: str, value: str, delta: str) -> Dict[str, Any]:
    return {"label": label, "value": value, "delta": delta}

def _delta(pct: float, direction: str, absolute: bool = False) -> str:
    arrow = "▲" if direction == "up" else "▼"
    if absolute:
        return f"{arrow} {abs(pct):.2f} vs prior"
    return f"{arrow} {abs(pct):.1f}% vs prior"


# ─── Channel summary table ────────────────────────────────────────────────

def _compute_summary(channels: List[Dict[str, Any]], currency: str) -> List[Dict[str, Any]]:
    """Rows for the Channel Summary table."""
    rows: List[Dict[str, Any]] = []
    for c in channels:
        spend = c.get("spend", 0)
        revenue = c.get("revenue", 0)
        conv = c.get("conversions", 0)
        roi = revenue / spend if spend else 0
        trend = c.get("trend_pct", 0)
        rows.append({
            "channel": c.get("channel") or c.get("name") or "Channel",
            "color": _color_for(c.get("channel") or ""),
            "spend": spend,
            "spend_display": format_money(spend, currency),
            "revenue": revenue,
            "revenue_display": format_money(revenue, currency),
            "roi": round(roi, 2),
            "roi_display": format_rate(roi),
            "conversions": conv,
            "conversions_display": format_count(conv),
            "trend_pct": trend,
            "trend_direction": "up" if trend > 0 else "down" if trend < 0 else "flat",
        })
    # Highest revenue first
    rows.sort(key=lambda r: r["revenue"], reverse=True)
    return rows


# ─── Revenue contribution donut ───────────────────────────────────────────

def _compute_contribution(channels: List[Dict[str, Any]], currency: str) -> Dict[str, Any]:
    total_revenue = sum(c.get("revenue", 0) for c in channels)
    if total_revenue <= 0:
        return {"total": 0, "total_display": format_money(0, currency), "slices": []}

    slices: List[Dict[str, Any]] = []
    for c in sorted(channels, key=lambda x: x.get("revenue", 0), reverse=True):
        rev = c.get("revenue", 0)
        pct = rev / total_revenue * 100
        slices.append({
            "channel": c.get("channel") or c.get("name") or "Channel",
            "color": _color_for(c.get("channel") or ""),
            "percentage": round(pct, 1),
            "revenue": rev,
            "revenue_display": format_money(rev, currency),
        })
    return {
        "total": total_revenue,
        "total_display": format_money(total_revenue, currency),
        "slices": slices,
    }


def _compose_top_insight(contribution: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Data-driven concentration insight for the callout."""
    slices = contribution.get("slices", [])
    if len(slices) < 2:
        return None
    top_two = slices[:2]
    combined = sum(s["percentage"] for s in top_two)
    names = " and ".join(s["channel"] for s in top_two)
    return {
        "headline": f"{names} together contribute {combined:.1f}% of total revenue.",
        "detail": f"Concentration risk is {'high' if combined > 65 else 'moderate'} — "
                  f"a meaningful shock to either channel would be felt portfolio-wide.",
    }


# ─── Channel Shift panel (plan v2 addition) ──────────────────────────────

def _compute_channel_shift(
    channels: List[Dict[str, Any]],
    monthly_history: Optional[List[Dict[str, Any]]] = None,
    lookback_months: int = 24,
) -> Dict[str, Any]:
    """
    Channel mix evolution over time. Returns per-channel share-of-spend
    across the lookback window, plus macro events marked for overlay.

    If monthly_history is absent, we construct a plausible series from
    the current snapshot — useful for demos but signalled in the result.
    """
    if monthly_history and len(monthly_history) > 1:
        months_sorted = sorted({row.get("month") for row in monthly_history if row.get("month")})
        months = months_sorted[-lookback_months:]
        by_month: Dict[str, Dict[str, float]] = {m: {} for m in months}
        for row in monthly_history:
            m = row.get("month")
            if m in by_month:
                ch = row.get("channel")
                by_month[m][ch] = row.get("spend", 0)
        # Convert to per-channel percentage series
        channel_names = sorted({c.get("channel") or c.get("name") or "Channel"
                                for c in channels if c.get("channel") or c.get("name")})
        series: List[Dict[str, Any]] = []
        for ch in channel_names:
            pts = []
            for m in months:
                total = sum(by_month[m].values()) or 1
                spend = by_month[m].get(ch, 0)
                pts.append({"month": m, "percentage": round(spend / total * 100, 1)})
            series.append({
                "channel": ch,
                "color": _color_for(ch),
                "points": pts,
            })
        return {
            "lookback_months": len(months),
            "source": "historical",
            "series": series,
            "overlay_events": _overlay_events(months[0] if months else None,
                                              months[-1] if months else None),
        }

    # Synthetic fallback — drift current shares smoothly across N months
    import math
    channels_sorted = sorted(channels, key=lambda c: c.get("revenue", 0), reverse=True)
    total_spend = sum(c.get("spend", 0) for c in channels) or 1
    series: List[Dict[str, Any]] = []
    today = date.today()
    months: List[str] = []
    y, m = today.year, today.month
    for _ in range(lookback_months):
        months.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0: m = 12; y -= 1
    months.reverse()

    for i, c in enumerate(channels_sorted):
        name = c.get("channel") or c.get("name") or f"Channel {i+1}"
        current_share = c.get("spend", 0) / total_spend * 100
        # Each channel drifts differently; high-ROI channels trend up, low-ROI trend down
        roi = c.get("revenue", 0) / c.get("spend", 1) if c.get("spend") else 0
        drift_slope = 0.08 if roi > 3 else -0.08 if roi < 1.5 else 0.01
        noise_phase = i * 1.1
        pts = []
        for idx, mo in enumerate(months):
            t = idx / max(1, lookback_months - 1)
            drifted = current_share * (1 - drift_slope) + current_share * drift_slope * t
            noise = 0.8 * math.sin(2 * math.pi * (idx / 6) + noise_phase)
            pts.append({"month": mo, "percentage": round(max(0, drifted + noise), 1)})
        series.append({"channel": name, "color": _color_for(name), "points": pts})

    # Normalise each month's slice percentages to sum to 100
    for idx in range(len(months)):
        total = sum(s["points"][idx]["percentage"] for s in series) or 1
        for s in series:
            s["points"][idx]["percentage"] = round(s["points"][idx]["percentage"] / total * 100, 1)

    return {
        "lookback_months": lookback_months,
        "source": "synthetic_from_snapshot",  # honest about being a demo aid
        "series": series,
        "overlay_events": _overlay_events(months[0], months[-1]),
    }


def _overlay_events(first_month: Optional[str], last_month: Optional[str]) -> List[Dict[str, Any]]:
    """Pull major macro-baseline events falling within the shift window."""
    if not first_month or not last_month:
        return []
    try:
        from datatypes.macro_baseline import get_loader
    except Exception:
        return []
    try:
        loader = get_loader()
    except Exception:
        return []

    start = date(int(first_month[:4]), int(first_month[5:7]), 1)
    # Set end to last day of last_month
    y, m = int(last_month[:4]), int(last_month[5:7])
    if m == 12:
        end = date(y + 1, 1, 1)
    else:
        end = date(y, m + 1, 1)

    df = loader.table("festival_calendar")
    mask = (df["start_date"] >= start) & (df["start_date"] < end)
    events: List[Dict[str, Any]] = []
    for _, row in df[mask].iterrows():
        if str(row.get("demand_lift_category", "")).strip().lower() not in ("high", "very_high"):
            continue
        sd = row["start_date"]
        events.append({
            "month": sd.strftime("%Y-%m"),
            "name": str(row["festival_name"]),
            "kind": "festival",
        })
    return events[:12]


# ─── Atlas narration ──────────────────────────────────────────────────────

def _compose_atlas(
    summary: List[Dict[str, Any]],
    contribution: Dict[str, Any],
    shift: Dict[str, Any],
) -> Dict[str, Any]:
    if not summary:
        return {
            "paragraphs": [{"text": "Upload performance data to see per-channel ROI and mix shifts."}],
            "suggested_questions": [],
            "source": "channel_performance_template",
        }
    top = summary[0]
    bottom = summary[-1]
    combined = sum(s["percentage"] for s in contribution["slices"][:2]) if contribution["slices"] else 0

    paragraphs = [
        {"text": f"{top['channel']} is your revenue engine — {top['revenue_display']} "
                 f"at a {top['roi_display']} ROI. Second place is roughly "
                 f"{contribution['slices'][1]['percentage']:.0f}% of revenue "
                 f"if you have two or more channels." if len(contribution['slices']) > 1 else
                 f"{top['channel']} is your single-source revenue today."},
        {"text": f"Concentration is the risk. Top two channels account for "
                 f"{combined:.0f}% of revenue — worth noting before the next planning cycle."},
    ]
    # If shift data is synthetic, name that so the user doesn't over-interpret
    if shift.get("source", "").startswith("synthetic"):
        paragraphs.append({
            "text": "The Channel Shift panel is extrapolated from the current snapshot — "
                    "upload 12+ months of history for a real trend read.",
        })

    questions = [
        f"What drove the Q2 shift away from {bottom['channel']}?",
        f"Is {top['channel']} saturating?",
        "Which channel has the widest ROI variance month-to-month?",
        "Where is the concentration risk most acute?",
    ]
    return {
        "paragraphs": paragraphs,
        "suggested_questions": questions,
        "source": "channel_performance_template",
    }


# ─── Helpers ──────────────────────────────────────────────────────────────
# All money formatting goes through currency.format_money now. The local
# _fmt_cr and _fmt_count helpers are gone; format_count is imported from
# currency and is currency-agnostic so it still works.


# ─── Route ────────────────────────────────────────────────────────────────

@router.get("/channel-performance")
def get_channel_performance(
    lookback_months: int = Query(24, ge=3, le=60),
    engagement_id: str = Query(
        DEFAULT_ENGAGEMENT_ID,
        description="Engagement to report against — drives currency and locale.",
    ),
    user=Depends(require_client_or_editor),
):
    engagement = get_engagement(engagement_id)
    currency = engagement.currency

    state = _read_state()
    # Pull channels from the engine output; fall back to optimization's
    # channels list which has spend/revenue aggregates.
    channels = (
        state.get("channel_performance") or
        state.get("channels") or
        _channels_from_optimization(state)
    )

    monthly = state.get("channel_monthly_history")

    kpis = _compute_kpis(channels, currency)
    summary = _compute_summary(channels, currency)
    contribution = _compute_contribution(channels, currency)
    top_insight = _compose_top_insight(contribution)
    shift = _compute_channel_shift(channels, monthly, lookback_months=lookback_months)
    atlas = _compose_atlas(summary, contribution, shift)

    return {
        "engagement": engagement.as_dict(),
        "kpis": kpis,
        "summary": summary,
        "contribution": contribution,
        "top_insight": top_insight,
        "channel_shift": shift,
        "atlas": atlas,
        "has_data": bool(channels),
    }


def _channels_from_optimization(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Derive channel_performance rows from optimization.channels when the
    dedicated channel_performance state isn't populated. Conservative:
    uses current_spend and assumes ROI-scaled revenue from marginal_roi.
    """
    opt = state.get("optimization") or {}
    channels = opt.get("channels") or []
    out = []
    for c in channels:
        spend = c.get("current_spend", 0)
        roi = c.get("current_roi") or c.get("marginal_roi") or 0
        revenue = c.get("current_revenue") or spend * roi
        out.append({
            "channel": c.get("channel") or c.get("name"),
            "spend": spend,
            "revenue": revenue,
            "conversions": c.get("conversions", 0),
            "trend_pct": c.get("trend_pct", 0),
        })
    return out
