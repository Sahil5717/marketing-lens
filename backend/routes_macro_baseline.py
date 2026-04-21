"""
Macro baseline API routes.

Exposes the centrally-curated macro context to the frontend. These
endpoints are deliberately stateless and tenant-agnostic — callers pass
client context (category, regions) as query parameters.

Routes:
    GET /api/macro-baseline/freshness
        Per-table freshness metadata for Screen 02's data-foundation view.

    GET /api/market-context
        Demand trend + upcoming peak windows for Screen 01's bottom row,
        filtered to a category + region set.

Design note — why a new path, not a replacement:
    The existing /api/market-context handler in api.py conflates macro
    context with per-tenant uploaded "external data" (events, trends,
    competitive). It stays where it is for now; the new implementation
    is mounted at the *same* /api/market-context path, but only if the
    new router is included *before* the old declaration (FastAPI picks
    the first matching route). Including this router at import time in
    api.py supersedes the old endpoint cleanly without editing the
    1,000-line block that defines it.

    The old handler is scheduled for removal once callers migrate; until
    then, it's dead code after this router is mounted.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Query, Depends

from datatypes.macro_baseline import (
    DemandTrendPoint,
    PeakWindow,
    get_loader,
)
from auth import require_client_or_editor

router = APIRouter(prefix="/api", tags=["macro-baseline"])


def _parse_regions(raw: Optional[str]) -> Optional[List[str]]:
    """Parse a 'Mumbai,Delhi' query param into a list, or None for no filter."""
    if raw is None or not raw.strip():
        return None
    return [r.strip() for r in raw.split(",") if r.strip()]


def _parse_as_of(raw: Optional[str]) -> date:
    """Parse YYYY-MM-DD, default to today."""
    if not raw:
        return date.today()
    return datetime.strptime(raw, "%Y-%m-%d").date()


@router.get("/macro-baseline/freshness")
def get_freshness(user=Depends(require_client_or_editor)):
    """
    Per-table freshness metadata for the five macro baseline CSVs.
    Consumed by Screen 02's 'Macro baseline freshness' zone.
    """
    loader = get_loader()
    return {
        "tables": loader.freshness(),
        "curated_by": "YI team",
        "cadence": "quarterly refresh per build plan v2 §2A.1",
    }


@router.get("/market-context")
def get_market_context(
    as_of: Optional[str] = Query(None, description="YYYY-MM-DD; defaults to today"),
    category: Optional[str] = Query(None, description="Client category, e.g. FMCG"),
    regions: Optional[str] = Query(
        None,
        description="Comma-separated list of regions/states, e.g. 'Mumbai,Delhi' or 'MH,DL'",
    ),
    lookahead_days: int = Query(90, ge=1, le=365),
    lookback_months: int = Query(4, ge=1, le=24),
    peak_limit: int = Query(5, ge=1, le=20),
    engagement_id: str = Query(
        "default",
        description="Engagement to report against. No money is reported here, "
                    "but engagement metadata is returned for frontend consistency.",
    ),
    user=Depends(require_client_or_editor),
):
    """
    Combined macro-context payload for Screen 01's bottom row.

    Returns:
        - demand_trend: lookback_months of a blended category/sentiment index
        - upcoming_peaks: up to peak_limit festivals + holidays in the next
          lookahead_days, filtered for the given regions
        - atlas_narration: a short, source-attributed narration the frontend
          can drop directly into the Atlas rail (template-driven, no LLM)
        - engagement: metadata for the selected engagement (for consistent
          frontend handling across all screen endpoints)
    """
    # Lazy import so this module stays independently testable if engagements
    # persistence isn't available.
    try:
        from engagements import get_engagement
        engagement_meta = get_engagement(engagement_id).as_dict()
    except Exception:
        engagement_meta = {"id": engagement_id, "currency": "USD", "locale": "en-US"}

    ref_date = _parse_as_of(as_of)
    region_list = _parse_regions(regions)
    loader = get_loader()

    trend: List[DemandTrendPoint] = loader.demand_trend(
        as_of=ref_date,
        lookback_months=lookback_months,
        category=category,
    )
    peaks: List[PeakWindow] = loader.upcoming_events(
        as_of=ref_date,
        lookahead_days=lookahead_days,
        regions=region_list,
        category=category,
        limit=peak_limit,
    )

    narration = _compose_atlas_narration(
        trend=trend,
        peaks=peaks,
        category=category,
        regions=region_list,
        as_of=ref_date,
        lookback_months=lookback_months,
    )

    return {
        "engagement": engagement_meta,
        "as_of": ref_date.isoformat(),
        "category": category,
        "regions": region_list,
        "demand_trend": {
            "lookback_months": lookback_months,
            "points": [p.as_dict() for p in trend],
        },
        "upcoming_peaks": [p.as_dict() for p in peaks],
        "atlas_narration": narration,
        "source": "macro_baseline (YI-curated, per plan v2 §2A.1)",
    }


# ─── Atlas narration template ─────────────────────────────────────────────
#
# Proof-of-concept template demonstrating the pattern from plan §4.4 /
# §5. This template:
#   * declares its data-type dependencies (macro_baseline)
#   * degrades gracefully when signals are ambiguous
#   * names its source so the user can audit ("per the macro baseline")
#   * produces 2–4 sentences with a concrete number and a follow-up
#
# When the Atlas template infrastructure lands properly, this migrates
# to backend/atlas/templates/screen_01_market_context.py and gets
# registered with dependencies = [DataType.MACRO_BASELINE].

def _compose_atlas_narration(
    *,
    trend: List[DemandTrendPoint],
    peaks: List[PeakWindow],
    category: Optional[str],
    regions: Optional[List[str]],
    as_of: date,
    lookback_months: int,
) -> dict:
    """Template-driven narration for Screen 01's Atlas rail entry."""
    source_tag = "per the macro baseline"
    category_bit = f" for {category}" if category else ""

    # Trend direction — simple end-vs-start comparison
    if len(trend) >= 2:
        start_val = trend[0].value
        end_val = trend[-1].value
        delta_pct = 100.0 * (end_val - start_val) / start_val if start_val else 0.0
        if delta_pct > 3:
            trend_bit = (
                f"Demand{category_bit} has trended up about "
                f"{abs(delta_pct):.0f}% over the last {lookback_months} months, "
                f"{source_tag}."
            )
        elif delta_pct < -3:
            trend_bit = (
                f"Demand{category_bit} has softened by about "
                f"{abs(delta_pct):.0f}% over the last {lookback_months} months, "
                f"{source_tag}."
            )
        else:
            trend_bit = (
                f"Demand{category_bit} has been broadly flat over the last "
                f"{lookback_months} months, {source_tag}."
            )
    else:
        trend_bit = "Not enough macro history is available for a trend read."

    # Peak call-out — name the next high-significance peak, if any
    high_peaks = [p for p in peaks if p.significance_score >= 3]
    if high_peaks:
        next_peak = high_peaks[0]
        days = max(next_peak.days_away, 0)
        peak_bit = (
            f"The next major peak is {next_peak.name} in {days} days — "
            f"historically a {next_peak.significance.lower()}-impact window."
        )
    elif peaks:
        next_peak = peaks[0]
        days = max(next_peak.days_away, 0)
        peak_bit = (
            f"No tent-pole events in view; the next calendar-relevant "
            f"window is {next_peak.name} in {days} days."
        )
    else:
        peak_bit = "No peak windows in the lookahead range."

    follow_up = "Want me to overlay the last three years of this same period?"

    return {
        "headline": trend_bit,
        "detail": peak_bit,
        "follow_up": follow_up,
        "source": "macro_baseline",
        "confidence": "medium",
    }
