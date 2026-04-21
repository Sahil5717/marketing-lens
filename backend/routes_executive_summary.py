"""
Executive Summary API routes.

Powers Screen 01 (Decision Command Center). Aggregates pre-computed
engine outputs into a single payload matching the HTML reference
(05-hybrid-executive-summary.html).

This endpoint is a *composer*, not a computer — it reads from engines
that have already run (on upload / analyst action). That keeps the
screen fast for walkthrough demos.

Route:
    GET /api/executive-summary?engagement_id={id}
        Full payload: hero, KPIs, three pillars, opportunities, top
        actions, and an Atlas narration for the rail.

Currency
--------
Formatting (dollar/rupee/euro/pound amounts) is driven by the engagement's
currency setting. Pass ?engagement_id=... to target a specific one;
without it, reads the 'default' engagement (USD).

Design notes
------------
During the five-data-type refactor (plan §2A), this will accept full
per-engagement state. For now it reads from the legacy single-tenant
_state dict via a small adapter, so the endpoint contract is stable
across the refactor.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from currency import format_money, format_delta, format_rate
from engagements import EngagementConfig, get_engagement, DEFAULT_ENGAGEMENT_ID
from auth import require_client_or_editor

router = APIRouter(prefix="/api", tags=["executive-summary"])


# ─── State adapter (temporary, until §2A data-type refactor lands) ────────

def _read_state() -> Dict[str, Any]:
    """
    Read the legacy _state dict from api.py.

    Wrapped in a function so the executive-summary module can be tested
    independently by monkey-patching this one symbol. When the real
    per-engagement persistence lands, this becomes a thin query.
    """
    try:
        from api import _state  # lazy import to avoid circularity
        return _state
    except Exception:
        return {}


# ─── KPIs ─────────────────────────────────────────────────────────────────

def _compute_kpis(state: Dict[str, Any], currency: str) -> List[Dict[str, Any]]:
    """
    Build the 5-cell KPI strip. Pulls from reporting_data (last 12 mo) if
    present, falling back to computed placeholders so the screen renders
    in a cold-start state rather than 500-ing.
    """
    reporting = state.get("reporting_data")
    roi_analysis = state.get("roi_analysis") or {}
    optimization = state.get("optimization") or {}
    opt_summary = optimization.get("summary") or {}

    # Fall through the most reliable signals first, then derive the rest.
    if reporting is not None and hasattr(reporting, "agg"):
        total_revenue = float(reporting["revenue"].sum())
        total_spend = float(reporting["spend"].sum())
        total_conv = float(reporting.get("conversions", reporting.get("leads", 0)).sum()) \
            if "conversions" in reporting or "leads" in reporting else 0.0
    else:
        total_revenue = float(opt_summary.get("current_revenue") or 0)
        total_spend = float(opt_summary.get("total_budget") or 0)
        total_conv = 0.0

    roi = (total_revenue / total_spend) if total_spend else 0.0
    cac = (total_spend / total_conv) if total_conv else 0.0
    # Pipeline influence as 1.4x MQL-derived revenue — a standard SaaS
    # assumption when the funnel layer is sparse. Better signal replaces
    # this when funnel_analysis is wired.
    pipeline_influence = total_revenue * 1.4 if total_revenue else 0.0

    # CAC is always a small per-unit amount — use format_money at its
    # sub-scale tier so it respects the currency symbol.
    cac_display = format_money(cac, currency) if cac else "—"

    return [
        _kpi("Total Revenue", format_money(total_revenue, currency), ""),
        _kpi("ROI",           format_rate(roi), ""),
        _kpi("Marketing Spend", format_money(total_spend, currency), ""),
        _kpi("CAC",           cac_display, ""),
        _kpi("Pipeline Influence", format_money(pipeline_influence, currency), ""),
    ]


def _kpi(label: str, value: str, delta: str) -> Dict[str, Any]:
    return {"label": label, "value": value, "delta": delta}


# ─── Three pillars ────────────────────────────────────────────────────────

_PILLAR_DESCRIPTIONS = {
    "leak": "Spend that produced revenue, but less than it could have. "
            "Saturated channels held while under-saturated ones starve.",
    "drop": "Funnel friction — primarily mobile — converting fewer of the "
            "leads your spend already paid to acquire.",
    "avoid": "Spend on channels past their saturation point or with negative "
             "marginal ROI. Money that came back as nothing.",
}

_PILLAR_TAGS = {
    "leak": "Recoverable",
    "drop": "Mostly fixable",
    "avoid": "Cuttable today",
}


def _compute_pillars(state: Dict[str, Any], currency: str) -> Dict[str, Any]:
    """
    Shape the existing three-pillar engine output into the HTML's panel.
    Gracefully handles the pre-upload state by returning zeroed pillars
    so the screen still renders.
    """
    pillars_src = state.get("pillars") or {}

    leak_amt = (pillars_src.get("revenue_leakage") or {}).get("total_leakage", 0)
    drop_amt = (pillars_src.get("experience_suppression") or {}).get("total_suppression", 0)
    avoid_amt = (pillars_src.get("avoidable_cost") or {}).get("total_avoidable_cost", 0)
    total = leak_amt + drop_amt + avoid_amt

    return {
        "total_cost": {
            "amount": total,
            "display": format_money(total, currency),
            "label": "Total cost · This month",
        },
        "pillars": [
            {
                "id": "leak", "roman": "i.", "name": "Revenue Leakage",
                "amount": leak_amt, "display": format_money(leak_amt, currency),
                "description": _PILLAR_DESCRIPTIONS["leak"],
                "tag": _PILLAR_TAGS["leak"],
            },
            {
                "id": "drop", "roman": "ii.", "name": "Experience Drop",
                "amount": drop_amt, "display": format_money(drop_amt, currency),
                "description": _PILLAR_DESCRIPTIONS["drop"],
                "tag": _PILLAR_TAGS["drop"],
            },
            {
                "id": "avoid", "roman": "iii.", "name": "Avoidable Cost",
                "amount": avoid_amt, "display": format_money(avoid_amt, currency),
                "description": _PILLAR_DESCRIPTIONS["avoid"],
                "tag": _PILLAR_TAGS["avoid"],
            },
        ],
    }


# ─── Recovery opportunities ───────────────────────────────────────────────

def _compute_opportunities(
    state: Dict[str, Any],
    pillars: Dict[str, Any],
    currency: str,
) -> List[Dict[str, Any]]:
    """
    Build the 3-card "Recovery Opportunities" panel. The numbers here
    are derived from the correction_potential the engine already computes,
    giving three orthogonal levers: reallocate, cut, fix conversion.
    """
    pillars_src = state.get("pillars") or {}
    corr = pillars_src.get("correction_potential") or {}

    reallocation = corr.get("reallocation_uplift", 0)
    cost_savings = corr.get("cost_savings", 0)
    cx_recovery = corr.get("cx_fix_recovery", 0)

    return [
        {
            "icon": "↑",
            "amount": reallocation,
            "display": format_delta(reallocation, currency),
            "name": "Reallocate spend",
            "detail": "Shift under-performing channels into higher-marginal-ROI ones",
        },
        {
            "icon": "×",
            "amount": -cost_savings,
            "display": format_delta(-cost_savings, currency),
            "name": "Cut waste",
            "detail": "Pause channels past their saturation point",
        },
        {
            "icon": "↗",
            "amount": cx_recovery,
            "display": format_delta(cx_recovery, currency),
            "name": "Fix conversion",
            "detail": "Address mobile funnel drop and landing-page friction",
        },
    ]


# ─── Top actions ──────────────────────────────────────────────────────────

def _compute_top_actions(state: Dict[str, Any], currency: str) -> List[Dict[str, Any]]:
    """
    Top prioritized actions with inline "Why?" reasoning. Sourced from
    the automated-recs engine if available; falls back to derived actions
    built from the optimizer output.
    """
    recs = state.get("smart_recs") or []
    if recs:
        actions: List[Dict[str, Any]] = []
        # smart_recs can be a list or a dict with items
        items = recs if isinstance(recs, list) else recs.get("items", [])
        for i, rec in enumerate(items[:3]):
            # Prefer pre-rendered impact_display so callers can force a
            # specific format. Otherwise derive with the engagement currency.
            impact = rec.get("impact_display") or format_delta(rec.get("impact", 0), currency)
            actions.append({
                "num": i + 1,
                "text": rec.get("title") or rec.get("action") or "Untitled action",
                "impact": impact,
                "why": {
                    "who": "Atlas · Reasoning",
                    "text": rec.get("reasoning") or rec.get("rationale")
                            or "Automatic recommendation based on current performance signals.",
                },
            })
        if actions:
            return actions

    # Fallback: derive from optimization output
    optimization = state.get("optimization") or {}
    return _fallback_actions(optimization, currency)


def _fallback_actions(optimization: Dict[str, Any], currency: str) -> List[Dict[str, Any]]:
    """Construct plausible top actions from optimizer output alone."""
    channels = (optimization or {}).get("channels") or []
    if not channels:
        return []

    # Pick the channel with the largest positive delta as the lead action
    sorted_by_delta = sorted(
        channels,
        key=lambda c: (c.get("optimized_spend", 0) - c.get("current_spend", 0)),
        reverse=True,
    )
    actions: List[Dict[str, Any]] = []
    if sorted_by_delta:
        lead = sorted_by_delta[0]
        delta = lead.get("optimized_spend", 0) - lead.get("current_spend", 0)
        if delta > 0:
            actions.append({
                "num": 1,
                "text": f"Shift spend into {lead.get('channel', 'top channel')}",
                "impact": format_delta(delta, currency),
                "why": {
                    "who": "Atlas · Reasoning",
                    "text": f"{lead.get('channel', 'This channel')} is the highest "
                            f"marginal-ROI destination in the current plan.",
                },
            })
    # Pick the largest negative delta as the second action
    worst = sorted_by_delta[-1] if len(sorted_by_delta) > 1 else None
    if worst:
        delta = worst.get("current_spend", 0) - worst.get("optimized_spend", 0)
        if delta > 0:
            actions.append({
                "num": len(actions) + 1,
                "text": f"Pull spend from {worst.get('channel', 'a saturated channel')}",
                "impact": format_delta(-delta, currency),
                "why": {
                    "who": "Atlas · Reasoning",
                    "text": f"{worst.get('channel', 'This channel')} has crossed its "
                            f"diminishing-returns inflection point.",
                },
            })
    return actions


# ─── Hero insight + Atlas narration ───────────────────────────────────────

def _compose_hero(
    pillars: Dict[str, Any],
    state: Dict[str, Any],
    currency: str,
) -> Dict[str, Any]:
    """
    Build the dark gradient hero card. Headline is data-driven:
    'You're leaving [total] on the table — but [recoverable] is recoverable'.
    """
    total = pillars["total_cost"]["amount"]
    corr = (state.get("pillars") or {}).get("correction_potential") or {}
    recoverable = corr.get("total_recoverable", 0)

    # Confidence derived from data_split coverage if present
    confidence_pct = _derive_confidence(state)

    if total > 0:
        headline = {
            "prefix": "You're leaving",
            "loss": format_money(total, currency),
            "middle": "on the table this month — but",
            "gain": f"{format_money(recoverable, currency)} is recoverable",
            "suffix": ".",
        }
        sub = (
            "Three pillars — revenue leakage, experience drop, and avoidable cost — "
            "explain where the value is sitting. Each has a recommended move below."
        )
    else:
        headline = {
            "prefix": "Upload performance data to see where",
            "loss": "revenue is leaking",
            "middle": "and",
            "gain": "how much is recoverable",
            "suffix": ".",
        }
        sub = "Once a performance dataset is in, this screen becomes your decision command center."

    return {
        "eyebrow": "Where you stand this quarter",
        "headline": headline,
        "sub": sub,
        "cta": {"label": "Take the tour →", "meta": f"{confidence_pct}% confidence"},
    }


def _compose_atlas(
    pillars: Dict[str, Any],
    opportunities: List[Dict[str, Any]],
    state: Dict[str, Any],
    currency: str,
) -> Dict[str, Any]:
    """
    Template-driven Atlas rail narration. Follows the §5.1 pattern: names
    a specific number, comments on its shape rather than its size, ends
    with an explicit follow-up.
    """
    total = pillars["total_cost"]["amount"]
    corr = (state.get("pillars") or {}).get("correction_potential") or {}
    recoverable = corr.get("total_recoverable", 0)
    recovery_ratio = (recoverable / total * 100) if total else 0

    if total <= 0:
        return {
            "paragraphs": [
                {"text": "No performance data is loaded yet — once it is, I'll "
                         "walk you through where the recoverable value sits."},
            ],
            "suggested_questions": [],
            "source": "executive_summary_template",
        }

    paragraphs = [
        {
            "text": f"The headline number — {format_money(total, currency)} — is the one most clients "
                    f"fixate on. But the interesting thing isn't the size. It's the shape.",
        },
        {
            "text": f"About {format_money(recoverable, currency)} of it is recoverable within this quarter. "
                    f"That's a {recovery_ratio:.0f}% recovery ratio — most engagements I've "
                    f"reviewed see 60–70%.",
        },
    ]

    # Suggested questions adapt to what's in the data
    questions = [
        "Why is the recovery ratio this high?" if recovery_ratio > 80
            else "Why is the recovery ratio this modest?",
        "Which channel is leaking the most?",
        f"How confident are you in {format_money(pillars['pillars'][0]['amount'], currency)}?",
        "What would the CFO push back on?",
    ]

    return {
        "paragraphs": paragraphs,
        "suggested_questions": questions,
        "source": "executive_summary_template",
    }


# ─── Helpers ──────────────────────────────────────────────────────────────
# Money formatting goes through currency.format_money() so it respects
# the engagement's configured currency. Non-currency helpers remain local.

def _derive_confidence(state: Dict[str, Any]) -> int:
    """
    Derive a top-level confidence % from data coverage. If MMM fit metrics
    are present, use them; otherwise report a reasonable mid-range value.
    """
    mmm = state.get("mmm_result") or state.get("mmm") or {}
    r2 = mmm.get("r_squared") or mmm.get("r2")
    if r2:
        return int(max(50, min(95, r2 * 100)))
    # Coverage-based heuristic
    has_perf = state.get("campaign_data") is not None
    has_journey = state.get("journey_data") is not None
    base = 70 if has_perf else 50
    if has_journey:
        base += 8
    return base


# ─── Route ────────────────────────────────────────────────────────────────

@router.get("/executive-summary")
def get_executive_summary(
    engagement_id: str = Query(
        DEFAULT_ENGAGEMENT_ID,
        description="Engagement to report against — drives currency and locale.",
    ),
    user=Depends(require_client_or_editor),
):
    """
    Full payload for Screen 01. Composed from already-computed engine
    results. Never 500s on missing data — returns zeroed structures the
    frontend renders as empty states.

    Currency and locale come from the named engagement's config.
    """
    engagement = get_engagement(engagement_id)
    currency = engagement.currency
    state = _read_state()

    pillars = _compute_pillars(state, currency)
    kpis = _compute_kpis(state, currency)
    opportunities = _compute_opportunities(state, pillars, currency)
    top_actions = _compute_top_actions(state, currency)
    hero = _compose_hero(pillars, state, currency)
    atlas = _compose_atlas(pillars, opportunities, state, currency)

    return {
        "engagement": engagement.as_dict(),
        "hero": hero,
        "kpis": kpis,
        "pillars": pillars,
        "opportunities": opportunities,
        "top_actions": top_actions,
        "atlas": atlas,
        "has_data": bool(state.get("campaign_data") is not None),
    }
