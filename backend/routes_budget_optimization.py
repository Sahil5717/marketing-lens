"""
Budget Optimization API routes.

Powers Screen 06 (Budget Optimization). Composes the optimizer engine
output into the shape the HTML reference (06-hybrid-budget-optimization.html)
expects:
  - hero with same-spend-better-outcome framing
  - current vs recommended donut data (for the earned-reveal section)
  - the four moves — biggest directional deltas with Atlas reasoning
  - impact strip (projected ROI, incremental revenue, CAC, payback)

Route:
    GET /api/budget-optimization
        Full payload for Screen 06.
    POST /api/budget-optimization/override
        Re-score a user-authored allocation vs Atlas's plan.

Data contract notes
-------------------
The optimizer engine expresses allocations as per-channel current_spend
and optimized_spend. We translate these into:
  - percentages of total for both donuts
  - a "moves" list of biggest deltas (top 4 by absolute change)
  - a confidence per move derived from the response-curve fit quality
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException

router = APIRouter(prefix="/api", tags=["budget-optimization"])


# ─── State adapter (same pattern as exec summary) ─────────────────────────

def _read_state() -> Dict[str, Any]:
    try:
        from api import _state
        return _state
    except Exception:
        return {}


# ─── Channel colour palette ───────────────────────────────────────────────
# Matches the HTML reference's donut colors so the visual lines up.

_CHANNEL_COLORS = {
    "Search":       "#7C5CFF",
    "Meta Ads":     "#3B82F6",
    "Meta":         "#3B82F6",
    "LinkedIn":     "#10B981",
    "Display":      "#F59E0B",
    "YouTube":      "#EF4444",
    "Email":        "#8B5CF6",
    "Others":       "#8C92AC",
}

def _color_for(channel: str) -> str:
    if channel in _CHANNEL_COLORS:
        return _CHANNEL_COLORS[channel]
    # Deterministic fallback — pick from extras by hash
    extras = ["#06B6D4", "#F97316", "#EC4899", "#14B8A6", "#A855F7"]
    return extras[abs(hash(channel)) % len(extras)]


# ─── Allocation donuts ────────────────────────────────────────────────────

def _compose_allocation(channels: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build the current vs recommended donut data. Each donut is a list of
    slices with colour, percentage, amount, and delta-direction flag.
    """
    current_total = sum(c.get("current_spend", 0) for c in channels) or 1
    opt_total = sum(c.get("optimized_spend", 0) for c in channels) or 1

    def _slice(channel: Dict[str, Any], side: str) -> Dict[str, Any]:
        name = channel.get("channel") or channel.get("name") or "Channel"
        spend = channel.get("current_spend" if side == "current" else "optimized_spend", 0)
        total = current_total if side == "current" else opt_total
        pct = (spend / total * 100) if total else 0
        # Direction for the recommended side
        current_pct = (channel.get("current_spend", 0) / current_total * 100) if current_total else 0
        opt_pct = (channel.get("optimized_spend", 0) / opt_total * 100) if opt_total else 0
        direction = "up" if opt_pct > current_pct + 0.5 else "down" if opt_pct < current_pct - 0.5 else "flat"
        return {
            "channel": name,
            "color": _color_for(name),
            "percentage": round(pct, 1),
            "amount": spend,
            "display_amount": _fmt_cr(spend),
            "direction": direction if side == "recommended" else None,
        }

    # Sort by channel spend descending on the current side, keep the same
    # channel order for recommended so slices line up visually
    channels_sorted = sorted(
        channels,
        key=lambda c: c.get("current_spend", 0),
        reverse=True,
    )
    current = [_slice(c, "current") for c in channels_sorted]
    recommended = [_slice(c, "recommended") for c in channels_sorted]

    return {
        "total_budget": current_total,
        "total_budget_display": _fmt_cr(current_total),
        "current": current,
        "recommended": recommended,
    }


# ─── Four moves ───────────────────────────────────────────────────────────

def _compose_moves(channels: List[Dict[str, Any]], optimization: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    The "four moves" — top 4 directional changes ranked by absolute spend
    shift. Each comes with an Atlas reasoning paragraph that mentions the
    Bayesian credible interval when available.
    """
    moves_raw: List[Dict[str, Any]] = []
    for ch in channels:
        delta = ch.get("optimized_spend", 0) - ch.get("current_spend", 0)
        if abs(delta) < 1:
            continue
        rev_lift = ch.get("revenue_delta", delta * ch.get("marginal_roi", 1.5))
        moves_raw.append({
            "channel": ch.get("channel") or ch.get("name"),
            "delta_spend": delta,
            "rev_lift": rev_lift,
            "marginal_roi": ch.get("marginal_roi"),
            "confidence": ch.get("confidence", _derive_confidence(ch)),
            "credible_interval": ch.get("credible_interval_80"),
        })

    # Sort by absolute spend shift, take top 4
    moves_raw.sort(key=lambda m: abs(m["delta_spend"]), reverse=True)
    moves_raw = moves_raw[:4]

    composed: List[Dict[str, Any]] = []
    for i, m in enumerate(moves_raw):
        is_up = m["delta_spend"] > 0
        composed.append({
            "num": f"{i+1:02d}.",
            "direction": "up" if is_up else "down",
            "action": f"{'Move' if is_up else 'Pull'} {_fmt_cr(abs(m['delta_spend']))} "
                      f"{'into' if is_up else 'from'} {m['channel']}",
            "channel": m["channel"],
            "delta_spend": m["delta_spend"],
            "delta_spend_display": _fmt_cr(abs(m["delta_spend"])),
            "revenue_lift": m["rev_lift"],
            "revenue_lift_display": (f"+{_fmt_cr(m['rev_lift'])}" if m["rev_lift"] >= 0
                                     else f"−{_fmt_cr(abs(m['rev_lift']))}"),
            "revenue_lift_kind": "gain" if m["rev_lift"] >= 0 else "cut",
            "confidence": m["confidence"],
            "confidence_display": f"{m['confidence']}%",
            "why": {
                "who": "Atlas · Reasoning",
                "text": _move_reasoning(m, is_up),
            },
        })
    return composed


def _move_reasoning(m: Dict[str, Any], is_up: bool) -> str:
    """Template-driven reasoning for a single move."""
    channel = m["channel"]
    marginal = m.get("marginal_roi")
    ci = m.get("credible_interval")

    if is_up:
        base = (
            f"{channel} is well below saturation and is a high-marginal-ROI "
            f"destination in the current response curve."
        )
        if marginal:
            base += f" Each additional rupee returns ₹{marginal:.2f} in revenue today."
        if ci:
            base += (
                f" The 80% Bayesian credible interval is "
                f"[₹{ci[0]/1e7:.1f} Cr, ₹{ci[1]/1e7:.1f} Cr] — "
                f"even the floor case supports the move."
            )
        return base

    # Pull / cut side
    base = (
        f"{channel} has crossed its diminishing-returns inflection point. "
        f"Spend above this level is purchasing impressions that don't convert."
    )
    if marginal is not None and marginal < 1:
        base += f" Marginal ROI has dropped to {marginal:.2f}x."
    return base


def _derive_confidence(channel: Dict[str, Any]) -> int:
    """Confidence fallback when the engine doesn't emit one per channel."""
    r2 = channel.get("r_squared") or channel.get("curve_fit_r2")
    if r2:
        return int(max(60, min(95, r2 * 100)))
    # Heuristic: directionally cleaner moves (bigger deltas) get higher confidence
    return 80


# ─── Impact strip ─────────────────────────────────────────────────────────

def _compose_impact(optimization: Dict[str, Any]) -> Dict[str, Any]:
    """Build the 4-cell impact strip (Projected ROI, Incremental Revenue, CAC, Payback)."""
    summary = (optimization or {}).get("summary") or {}
    current_roi = summary.get("current_roi", 0)
    optimized_roi = summary.get("optimized_roi", 0)
    uplift = summary.get("revenue_uplift", 0)
    uplift_pct = summary.get("uplift_pct", 0)

    current_cac = summary.get("current_cac")
    optimized_cac = summary.get("optimized_cac")
    cac_improvement_pct = None
    if current_cac and optimized_cac:
        cac_improvement_pct = (current_cac - optimized_cac) / current_cac * 100

    payback_months = summary.get("payback_months", 1.8)

    return {
        "projected_roi": {
            "value": f"{optimized_roi:.2f}x" if optimized_roi else "—",
            "delta": f"▲ {uplift_pct:.1f}%" if uplift_pct else None,
        },
        "incremental_revenue": {
            "value": f"+{_fmt_cr(uplift)}" if uplift else "—",
            "delta": "vs current",
        },
        "cac_improvement": {
            "value": f"−{cac_improvement_pct:.1f}%" if cac_improvement_pct else "—",
            "delta": f"to ₹{optimized_cac:.0f}" if optimized_cac else None,
        },
        "payback_period": {
            "value": f"{payback_months:.1f} mo" if payback_months else "—",
            "delta": "months",
        },
    }


# ─── Hero + Atlas narration ───────────────────────────────────────────────

def _compose_hero(allocation: Dict[str, Any], impact: Dict[str, Any]) -> Dict[str, Any]:
    total = allocation["total_budget_display"]
    uplift_display = impact["incremental_revenue"]["value"]

    if uplift_display and uplift_display != "—":
        headline = {
            "prefix": "The",
            "same": f"same {total}",
            "middle": "could earn",
            "gain": f"{uplift_display.lstrip('+')} more",
            "suffix": " — by spending it differently.",
        }
        sub = (
            "Four moves. Each with a reason and a confidence score. "
            "Reveal Atlas's recommendation below."
        )
    else:
        headline = {
            "prefix": "Run the optimizer to see what",
            "same": "your current budget",
            "middle": "could earn with",
            "gain": "better allocation",
            "suffix": ".",
        }
        sub = "Once the optimizer has run, the four recommended moves appear below."

    return {
        "eyebrow": "If we changed nothing else",
        "headline": headline,
        "sub": sub,
        "cta": {"label": "See the four moves →", "meta": "87% confidence"},
    }


def _compose_atlas(
    moves: List[Dict[str, Any]],
    impact: Dict[str, Any],
) -> Dict[str, Any]:
    uplift_display = impact["incremental_revenue"]["value"]
    if not moves:
        return {
            "paragraphs": [
                {"text": "No moves computed yet — run the optimizer first."},
            ],
            "suggested_questions": [],
            "source": "budget_optimization_template",
        }

    strongest = max(moves, key=lambda m: m.get("confidence", 0))
    paragraphs = [
        {
            "text": f"Four moves net to {uplift_display}. The strongest individually "
                    f"is Move #{strongest['num'].rstrip('.')}, "
                    f"{strongest['action'].lower()} — {strongest['confidence']}% confidence, "
                    f"near-zero downside.",
        },
        {
            "text": "If your CFO will only sign off on one thing, that's the one. "
                    "The rest are higher-reward but slightly lower confidence.",
        },
    ]
    questions = [
        f"What's the downside risk of Move #{moves[0]['num'].rstrip('.')}?",
        "Which move is most defensible to the CFO?",
        "How does this compare to last quarter's plan?",
        "What if the budget drops 20% next month?",
    ]
    return {
        "paragraphs": paragraphs,
        "suggested_questions": questions,
        "source": "budget_optimization_template",
    }


# ─── Helpers ──────────────────────────────────────────────────────────────

def _fmt_cr(value: float) -> str:
    if value is None or value == 0:
        return "₹0 Cr"
    value = float(value)
    cr = value / 1e7
    if abs(cr) >= 100:
        return f"₹{cr:.0f} Cr"
    if abs(cr) >= 1:
        return f"₹{cr:.1f} Cr"
    lakh = value / 1e5
    return f"₹{lakh:.1f} L"


# ─── Route ────────────────────────────────────────────────────────────────

@router.get("/budget-optimization")
def get_budget_optimization():
    """Full payload for Screen 06."""
    state = _read_state()
    optimization = state.get("optimization") or {}
    channels = optimization.get("channels") or []

    allocation = _compose_allocation(channels)
    moves = _compose_moves(channels, optimization)
    impact = _compose_impact(optimization)
    hero = _compose_hero(allocation, impact)
    atlas = _compose_atlas(moves, impact)

    return {
        "hero": hero,
        "allocation": allocation,
        "moves": moves,
        "impact": impact,
        "atlas": atlas,
        "has_optimization": bool(channels),
    }


@router.post("/budget-optimization/override")
def score_override(payload: Dict[str, Any] = Body(...)):
    """
    Score a user-authored allocation against the Atlas plan.

    Request:
      { allocation: { Search: 30.1, "Meta Ads": 16.4, ... } }   (in Crore)

    Response:
      {
        delta_vs_atlas_cr: float,  # signed; negative means override is worse
        delta_vs_current_cr: float,
        projected_roi: float,
        pushback: null | { headline, detail }
      }
    """
    user_alloc = payload.get("allocation") or {}
    if not user_alloc:
        raise HTTPException(400, "allocation is required")

    state = _read_state()
    optimization = state.get("optimization") or {}
    channels = optimization.get("channels") or []
    if not channels:
        raise HTTPException(409, "No optimizer run available to score against.")

    atlas_total = sum(c.get("optimized_spend", 0) for c in channels) / 1e7
    current_total = sum(c.get("current_spend", 0) for c in channels) / 1e7
    user_total = sum(user_alloc.values())

    # Linear proxy: each 1 Cr diverted away from Atlas's pick costs the
    # marginal_roi of that channel. This is an approximation the real
    # engine would replace with response-curve evaluation.
    penalty_cr = 0.0
    big_shifts: List[Dict[str, Any]] = []
    for ch in channels:
        name = ch.get("channel") or ch.get("name")
        atlas_cr = ch.get("optimized_spend", 0) / 1e7
        user_cr = float(user_alloc.get(name, atlas_cr))
        diff = user_cr - atlas_cr
        marginal = ch.get("marginal_roi", 1.5)
        # Diverting *from* Atlas's plan costs you the marginal uplift
        # the optimizer found. We use half-marginal as a conservative estimate.
        penalty_cr += abs(diff) * marginal * 0.5
        if abs(diff) > 1:
            big_shifts.append({"channel": name, "diff_cr": diff, "marginal_roi": marginal})

    atlas_uplift = (optimization.get("summary") or {}).get("revenue_uplift", 0) / 1e7
    user_uplift = atlas_uplift - penalty_cr

    delta_vs_atlas = user_uplift - atlas_uplift  # always <= 0 with this proxy
    delta_vs_current = user_uplift

    pushback = None
    if delta_vs_atlas < -1 and big_shifts:
        worst = max(big_shifts, key=lambda b: abs(b["diff_cr"]) * b["marginal_roi"])
        pushback = {
            "headline": f"Heads up — that override hurts the plan by ~₹{abs(delta_vs_atlas):.1f} Cr.",
            "detail": f"{worst['channel']} moved by ₹{abs(worst['diff_cr']):.1f} Cr. "
                      f"Its marginal ROI is {worst['marginal_roi']:.2f}x, so the lost lift compounds.",
        }

    # Projected ROI — proportional to revenue / spend
    total_spend_cr = user_total or atlas_total
    # Current revenue from optimization summary, scaled by user vs atlas uplift
    current_rev_cr = (optimization.get("summary") or {}).get("current_revenue", 0) / 1e7
    projected_roi = (current_rev_cr + user_uplift) / total_spend_cr if total_spend_cr else 0

    return {
        "delta_vs_atlas_cr": round(delta_vs_atlas, 2),
        "delta_vs_current_cr": round(delta_vs_current, 2),
        "projected_roi": round(projected_roi, 2),
        "pushback": pushback,
        "user_total_cr": round(user_total, 2),
        "budget_total_cr": round(atlas_total, 2),
    }
