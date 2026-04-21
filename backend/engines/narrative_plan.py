"""
Narrative Engine — Plan Screen
==============================

Produces the structured content for the Plan screen ("here's what to do").
Reads the optimizer's per-channel allocation output and produces:

- headline_paragraph: 2-3 sentence consulting-style rationale
- kpis: total reallocation $, expected uplift, plan confidence
- moves: per-channel action cards (increase/decrease/hold)
- tradeoffs: honest caveats the client needs to see alongside the plan
- methodology: underlying engines + assumptions
- ey_overrides: placeholders for the editor overlay

Like the Diagnosis engine, this is TEMPLATE-BASED (no LLM). Quality
ceiling is "correct, grammatical, uses real numbers." EY analysts
override prose via the commentary/rewrite layer.

Same pattern as engines/narrative.py:
- Each move gets a stable `key` so editor overrides survive re-runs
- generate_plan() takes an engagement_id and view ("client" or "editor")
- Client view filters suppressed moves, applies rewrites transparently
- Editor view returns everything with flags for the editor UI
"""

from typing import Dict, List, Optional
import pandas as pd


# ─── Formatting helpers (duplicated from narrative.py to keep modules
# independent; could refactor to a shared utils module but the cost is
# 20 lines of duplication vs. a new coupling) ───

def _format_dollars(amount: float) -> str:
    """Format a dollar amount in compact form ($14.2M, $820K, $450)."""
    if amount is None or amount != amount:
        return "—"
    a = abs(amount)
    sign = "-" if amount < 0 else ""
    if a >= 1e9:
        return f"{sign}${a/1e9:.1f}B"
    if a >= 1e6:
        return f"{sign}${a/1e6:.1f}M"
    if a >= 1e3:
        return f"{sign}${a/1e3:.0f}K"
    return f"{sign}${a:.0f}"


def _signed_dollars(amount: float) -> str:
    """Like _format_dollars but always prepends +/- for clarity on deltas."""
    if amount is None or amount != amount:
        return "—"
    if amount == 0:
        return "$0"
    sign = "+" if amount > 0 else "-"
    a = abs(amount)
    if a >= 1e9:
        return f"{sign}${a/1e9:.1f}B"
    if a >= 1e6:
        return f"{sign}${a/1e6:.1f}M"
    if a >= 1e3:
        return f"{sign}${a/1e3:.0f}K"
    return f"{sign}${a:.0f}"


def _plain_channel_name(ch: str) -> str:
    return ch.replace("_", " ").title() if ch else ""


def _move_key(channel: str, action: str) -> str:
    """
    Stable key for a Plan move, used to pin editor overrides across re-runs.
    Format matches the Diagnosis finding key: "move:<channel>:<action>".
    """
    ch = (channel or "unknown").strip().lower().replace(" ", "_")
    act = (action or "hold").strip().lower()
    return f"move:{ch}:{act}"


# ─── Core narrative logic ───

def classify_move(change_pct: float, revenue_delta: float) -> str:
    """
    Classify a channel allocation change into increase / decrease / hold.

    Thresholds:
      - |change_pct| < 2%: hold (within optimizer noise tolerance)
      - change_pct >= 2%: increase
      - change_pct <= -2%: decrease
    """
    if abs(change_pct or 0) < 2.0:
        return "hold"
    return "increase" if change_pct > 0 else "decrease"


def generate_move_narrative(move: Dict, action: str) -> str:
    """
    Produce 1-2 sentences of prose explaining the move's rationale.

    The narrative should answer "why this change?" — not repeat the
    numbers shown in the header. Ties back to the response curve
    (headroom, marginal ROI) for increases and decreases; keeps the hold
    message short.

    Special case: when the channel's response curve is near-linear, the
    standard "the curve shows headroom" story is misleading — a near-
    linear fit means we don't actually KNOW where the curve bends. We
    produce a narrative that flags this explicitly rather than pretending
    confidence we don't have.
    """
    ch_name = _plain_channel_name(move.get("channel", ""))
    current_roi = move.get("current_roi", 0)
    optimized_roi = move.get("optimized_roi", 0)
    marginal_roi = move.get("marginal_roi", 0)
    near_linear = move.get("near_linear_fit", False)

    # Near-linear override: honest language about the uncertainty
    if near_linear and action != "hold":
        direction = "increase" if action == "increase" else "reduction"
        return (
            f"{ch_name}'s response curve is near-linear in the training data, "
            f"meaning we can't reliably identify where saturation begins. "
            f"The optimizer is suggesting this {direction} based on the "
            f"fitted mROI of {marginal_roi:.1f}x, but that number is "
            f"extrapolating past observed spend levels. Validate with a "
            f"geo-lift test before committing the full allocation."
        )

    if action == "increase":
        return (
            f"{ch_name} currently operates at {current_roi:.1f}x ROI with marginal "
            f"returns of {marginal_roi:.1f}x — meaning the next dollar still "
            f"generates meaningful revenue. The response curve shows room for "
            f"additional spend before saturation begins to meaningfully "
            f"compress returns."
        )
    elif action == "decrease":
        return (
            f"{ch_name} is showing diminishing returns at its current spend "
            f"level: marginal ROI of {marginal_roi:.1f}x is below what other "
            f"channels deliver. Pulling spend back improves portfolio ROI to "
            f"{optimized_roi:.1f}x without significant revenue loss — the "
            f"channel is operating past its efficient frontier."
        )
    else:  # hold
        return (
            f"{ch_name} is near its efficient point — neither meaningfully "
            f"underinvested nor approaching saturation. The optimizer converged "
            f"on holding current spend as the best allocation given the rest "
            f"of the portfolio."
        )


def build_moves(
    opt_channels: List[Dict],
    curves: Optional[Dict] = None,
    bayes_result: Optional[Dict] = None,
) -> List[Dict]:
    """
    Convert the optimizer's per-channel output into ranked move cards.

    Ranking: by absolute revenue delta, descending. The biggest-impact
    reallocations surface first, regardless of direction. This matters
    because the Plan screen's purpose is to tell the client what to DO —
    a $3M increase ranks above a $500K decrease.

    The `curves` parameter (response-curve fits) is used to flag moves
    whose impact estimate depends on a near-linear fit. The optimizer
    itself doesn't distinguish reliable from unreliable curves; it
    reads whatever mROI is reported and allocates accordingly. We flag
    these moves so the UI can render them with an "inconclusive
    saturation" warning rather than presenting $7.7M of fabricated
    uplift as reliable.

    The `bayes_result` parameter (when present) is used to attach an 80%
    credible region to each move's revenue delta for channels in the
    Bayesian subset. This lets the UI show "+$5.2M (HDI +$2.1M to +$7.8M)"
    honestly — the frequentist point estimate with the Bayesian uncertainty
    range around it. Graceful degradation: moves for channels NOT in the
    Bayesian subset render without HDI (frequentist-only).
    """
    curves = curves or {}
    bayes_contribs = ((bayes_result or {}).get("contributions") or {}) if bayes_result else {}
    moves = []
    for ch in opt_channels:
        change_pct = ch.get("change_pct", 0) or 0
        spend_delta = ch.get("optimized_spend", 0) - ch.get("current_spend", 0)
        revenue_delta = ch.get("revenue_delta", 0) or 0
        action = classify_move(change_pct, revenue_delta)

        channel = ch.get("channel", "")
        ch_name = _plain_channel_name(channel)

        # Near-linear guard — same flag we set in response_curves engine
        # (v17). When true, the optimizer's revenue delta for this channel
        # is an extrapolation past what the data supports; the UI must
        # communicate this alongside the number.
        near_linear = bool(curves.get(channel, {}).get("near_linear_fit", False))

        # Bayesian delta range: for channels in the Bayesian subset, estimate
        # an 80% credible interval around the revenue impact of this move.
        # Uses ROAS HDI × spend_delta as a first-order approximation.
        #
        # Honest framing: the Bayesian model is separate from the frequentist
        # one, so the interval isn't "uncertainty on the frequentist estimate"
        # — it's the Bayesian model's own best guess of the delta with 80%
        # credible region. The width reflects Bayesian-model uncertainty.
        bayes_delta_hdi = None
        bayes_delta_point = None
        bayes_roas_hdi = None
        bayes_roas_point = None
        bc = bayes_contribs.get(channel)
        if bc is not None:
            roas_hdi = bc.get("mmm_roas_hdi_90") or []
            roas_point = bc.get("mmm_roas")
            if len(roas_hdi) == 2 and roas_point is not None:
                # For an increase, revenue gained = spend_delta × ROAS
                # For a decrease, revenue lost = spend_delta × ROAS (spend_delta is negative)
                # HDI multiplication: lo_roas × spend_delta and hi_roas × spend_delta
                # give the interval endpoints, but we must keep them ordered.
                d_lo = float(roas_hdi[0]) * float(spend_delta)
                d_hi = float(roas_hdi[1]) * float(spend_delta)
                if d_lo > d_hi:
                    d_lo, d_hi = d_hi, d_lo
                bayes_delta_hdi = [round(d_lo, 0), round(d_hi, 0)]
                bayes_delta_point = round(float(roas_point) * float(spend_delta), 0)
                bayes_roas_hdi = [round(float(roas_hdi[0]), 2), round(float(roas_hdi[1]), 2)]
                bayes_roas_point = round(float(roas_point), 2)

        # Action verb + channel name for headline. Kept consistent with
        # how Diagnosis findings phrase prescriptions (verb-first clarity).
        if action == "increase":
            headline = f"Increase {ch_name} by {change_pct:.1f}%"
        elif action == "decrease":
            headline = f"Reduce {ch_name} by {abs(change_pct):.1f}%"
        else:
            headline = f"Hold {ch_name} at current levels"

        # Build a merged dict for narrative generation that includes the
        # near_linear flag — the narrative function checks this flag to
        # produce honest prose for inconclusive fits.
        narrative_input = {**ch, "near_linear_fit": near_linear}
        narrative = generate_move_narrative(narrative_input, action)

        moves.append({
            "key": _move_key(channel, action),
            "channel": channel,
            "action": action,
            "headline": headline,
            "narrative": narrative,
            # Numbers for the card display — kept as a nested dict so the
            # UI can reformat without re-calling the backend.
            "current_spend": round(float(ch.get("current_spend", 0)), 0),
            "optimized_spend": round(float(ch.get("optimized_spend", 0)), 0),
            "spend_delta": round(float(spend_delta), 0),
            "spend_delta_display": _signed_dollars(spend_delta),
            "change_pct": round(float(change_pct), 1),
            "revenue_delta": round(float(revenue_delta), 0),
            "revenue_delta_display": _signed_dollars(revenue_delta),
            "current_roi": round(float(ch.get("current_roi", 0)), 2),
            "optimized_roi": round(float(ch.get("optimized_roi", 0)), 2),
            "marginal_roi": round(float(ch.get("marginal_roi", 0)), 2),
            "locked": bool(ch.get("locked", False)),
            "reliability": "inconclusive" if near_linear else "reliable",
            "near_linear_fit": near_linear,
            # Execution constraints (lead time, swing cap, min floor) from
            # the optimizer. Offline channels have non-null values that
            # the UI surfaces as honest timing/floor notes.
            "constraints": ch.get("constraints") or {},
            # Bayesian revenue delta HDI (80% credible region), None when
            # the channel isn't in the Bayesian subset or the fit isn't
            # ready yet. UI shows a range badge when present, nothing when
            # not — never a misleading zero-width interval.
            "bayes_delta_hdi_90": bayes_delta_hdi,
            "bayes_delta_point": bayes_delta_point,
            "bayes_roas_hdi_90": bayes_roas_hdi,
            "bayes_roas_point": bayes_roas_point,
            # Used by the dedupe/rank
            "_rank": -abs(revenue_delta),
        })

    moves.sort(key=lambda m: m["_rank"])
    for m in moves:
        m.pop("_rank", None)
    return moves


def generate_plan_hero(summary: Dict, moves: List[Dict]) -> Dict:
    """
    Build the structured answer-first hero for the Plan screen.

    Per UX redesign (mockup Image 3). The headline reads:
        "Reallocate $4.8M across six channels. Total spend holds at
         $48.7M; expected revenue lift is +$24.3M."

    with "$4.8M" and "+$24.3M" rendered as italic accent-colored
    fragments. Same segments[] pattern as the Diagnosis hero.

    Two-clause structure: action clause ("Reallocate X across N channels")
    then outcome clause ("Total spend holds at Y; expected revenue lift
    is Z"). Picked this shape because Plan is prescriptive — it answers
    "what do we do?" not "what's wrong?" — and the shape mirrors that:
    first what you do, then what you get.
    """
    total_budget = float(summary.get("total_budget", 0))
    revenue_uplift = float(summary.get("revenue_uplift", 0))

    increases = [m for m in moves if m["action"] == "increase"]
    decreases = [m for m in moves if m["action"] == "decrease"]
    affected = increases + decreases
    n_channels = len({m["channel"] for m in affected})

    # Reallocation magnitude — half the sum of absolute deltas, same
    # as generate_plan_headline uses. Each dollar moved appears once
    # as a subtraction and once as an addition, so dividing by 2 gives
    # the true net reallocation size.
    total_moved = sum(abs(m["spend_delta"]) for m in moves) / 2
    reallocation_display = _format_dollars(total_moved)
    uplift_display = _signed_dollars(revenue_uplift)
    total_budget_display = _format_dollars(total_budget)

    # Channel count word — mockup uses "six" for 6. We do the same for
    # 1-10 (reads better in serif display type than a digit); higher
    # counts fall back to digits because spelling them out gets awkward.
    channel_word = _number_word(n_channels)

    # Hero branches — different structure depending on the shape of the plan
    if n_channels == 0 or total_moved < total_budget * 0.01:
        # No meaningful reallocation — plan is essentially "hold current"
        segments = [
            {"text": "Current allocation is close to optimal. The plan is "
                     "largely about maintaining today's portfolio."},
        ]
        tone = "hold"
    elif revenue_uplift <= 0:
        # Reallocating for structure not yield (rare but possible)
        segments = [
            {"text": "Reallocate "},
            {"text": reallocation_display, "emphasis": True},
            {"text": f" across {channel_word} channels to rebalance the "
                     "portfolio. Total spend holds at "},
            {"text": total_budget_display, "emphasis": False},
            {"text": "."},
        ]
        tone = "rebalance"
    else:
        # Standard case — reallocation with expected uplift
        segments = [
            {"text": "Reallocate "},
            {"text": reallocation_display, "emphasis": True},
            {"text": f" across {channel_word} channels. Total spend holds at "},
            {"text": total_budget_display, "emphasis": False},
            {"text": "; expected revenue lift is "},
            {"text": uplift_display, "emphasis": True},
            {"text": "."},
        ]
        tone = "reallocate_with_uplift"

    # Lede — supports the headline. Mentions what's increasing and
    # what's decreasing, and the phasing intent. Keep to 2 sentences max.
    if increases and decreases:
        top_inc_names = [_plain_channel_name(m["channel"]) for m in increases[:2]]
        top_dec_names = [_plain_channel_name(m["channel"]) for m in decreases[:2]]
        lede = (
            f"Cuts in {_join_and(top_dec_names)} fund shifts into "
            f"{_join_and(top_inc_names)} where response curves show the "
            f"best marginal return. No channel is dropped entirely — "
            f"the plan is a rebalancing, not a restructuring."
        )
    elif increases:
        top_inc_names = [_plain_channel_name(m["channel"]) for m in increases[:2]]
        lede = (
            f"The plan scales {_join_and(top_inc_names)} where response "
            f"curves show meaningful headroom. Other channels hold."
        )
    elif decreases:
        top_dec_names = [_plain_channel_name(m["channel"]) for m in decreases[:2]]
        lede = (
            f"The plan pulls spend from {_join_and(top_dec_names)} which are "
            f"operating past their efficient frontier. Other channels hold."
        )
    else:
        lede = "The allocation is close to optimal; only minor adjustments are suggested."

    return {
        "segments": segments,
        "lede": lede,
        "tone": tone,
    }


def _number_word(n: int) -> str:
    """Spell out small counts — reads better in serif display type."""
    words = {
        0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
        6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
    }
    return words.get(n, str(n))


def _join_and(items: List[str]) -> str:
    """Oxford-comma join: ['A','B','C'] -> 'A, B, and C'."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def generate_plan_headline(summary: Dict, moves: List[Dict]) -> str:
    """
    2-3 sentence consulting-style rationale for the plan.

    Structure:
      S1: current position and what's changing (total reallocation)
      S2: the mechanism (which moves drive the uplift)
      S3: quantified outcome (uplift, new ROI) — only if meaningful
    """
    total_budget = float(summary.get("total_budget", 0))
    current_revenue = float(summary.get("current_revenue", 0))
    optimized_revenue = float(summary.get("optimized_revenue", 0))
    revenue_uplift = float(summary.get("revenue_uplift", 0))
    uplift_pct = float(summary.get("uplift_pct", 0))
    current_roi = float(summary.get("current_roi", 0))
    optimized_roi = float(summary.get("optimized_roi", 0))

    # Total $ moved = half the sum of absolute spend deltas (each dollar
    # moved shows up once as a subtraction and once as an addition, so
    # dividing by 2 gives the true reallocation magnitude).
    total_moved = sum(abs(m["spend_delta"]) for m in moves) / 2

    # Count of meaningful moves (excluding holds)
    increases = [m for m in moves if m["action"] == "increase"]
    decreases = [m for m in moves if m["action"] == "decrease"]

    # S1: current position
    s1 = (
        f"Your current {_format_dollars(total_budget)} marketing budget is "
        f"delivering {current_roi:.1f}x ROI. The optimizer identifies "
        f"{_format_dollars(total_moved)} of reallocation — "
        f"roughly {(total_moved / max(total_budget, 1) * 100):.1f}% of the "
        f"budget — that can improve returns without changing total spend."
    )

    # S2: the mechanism
    if increases and decreases:
        top_inc = increases[0]
        top_dec = decreases[0]
        s2 = (
            f" The plan increases spend on {len(increases)} underinvested "
            f"channels (led by {_plain_channel_name(top_inc['channel']).lower()}) "
            f"and reduces spend on {len(decreases)} saturating channels "
            f"(led by {_plain_channel_name(top_dec['channel']).lower()})."
        )
    elif increases:
        s2 = (
            f" The plan scales {len(increases)} channels where response "
            f"curves show meaningful headroom."
        )
    elif decreases:
        s2 = (
            f" The plan pulls spend from {len(decreases)} channels operating "
            f"past their efficient frontier."
        )
    else:
        s2 = " The allocation is close to optimal as-is; only minor adjustments are suggested."

    # S3: quantified outcome (only if uplift is meaningful)
    if revenue_uplift > total_budget * 0.02:  # >2% of budget as uplift threshold
        s3 = (
            f" Expected outcome: {_format_dollars(revenue_uplift)} of additional "
            f"annual revenue ({uplift_pct:.1f}% uplift), lifting portfolio ROI "
            f"from {current_roi:.1f}x to {optimized_roi:.1f}x."
        )
    else:
        s3 = ""

    return s1 + s2 + s3


def build_tradeoffs(opt_info: Dict, moves: List[Dict], curves: Dict) -> List[Dict]:
    """
    Produce an honest list of caveats and tradeoffs the client should
    understand alongside the plan.

    A consulting deliverable that shows moves without acknowledging their
    limits is a calculator pretending to be a recommendation. These
    tradeoffs are what separates "the model says" from "we recommend."
    """
    tradeoffs = []

    # 1. Large moves deserve validation
    large_moves = [m for m in moves if abs(m["change_pct"]) > 25]
    if large_moves:
        names = ", ".join(
            _plain_channel_name(m["channel"])
            for m in large_moves[:3]
        )
        tradeoffs.append({
            "key": "tradeoff:large-moves",
            "severity": "warning",
            "headline": "Large moves warrant incrementality validation",
            "narrative": (
                f"Changes above 25% push channels outside their observed spend "
                f"range — particularly on {names}. Response curves are fitted "
                f"on historical data; at these levels of change, we recommend "
                f"running a geo-lift test or phased rollout before committing "
                f"the full reallocation."
            ),
        })

    # 2. Near-linear fits in the plan
    near_linear_channels = [
        ch for ch, v in (curves or {}).items()
        if v.get("near_linear_fit") and any(m["channel"] == ch for m in moves)
    ]
    if near_linear_channels:
        names = ", ".join(_plain_channel_name(c) for c in near_linear_channels[:3])
        tradeoffs.append({
            "key": "tradeoff:near-linear",
            "severity": "warning",
            "headline": "Some channels have inconclusive saturation profiles",
            "narrative": (
                f"{names} show near-linear response curves in the training "
                f"data, meaning the optimizer can't reliably identify where "
                f"saturation begins. The allocation for these channels is a "
                f"best-estimate under uncertainty; validate with an "
                f"incrementality test before treating these moves as precise."
            ),
        })

    # 3. Warnings the optimizer itself surfaced
    opt_warnings = opt_info.get("warnings", []) or []
    if opt_warnings:
        tradeoffs.append({
            "key": "tradeoff:optimizer-warnings",
            "severity": "info",
            "headline": "Optimizer constraints applied",
            "narrative": (
                "The optimizer capped some moves to respect per-channel "
                "practical limits. Specifically: "
                + "; ".join(w for w in opt_warnings[:3])
                + "."
            ),
        })

    # 4. Always-on caveat about model assumptions
    tradeoffs.append({
        "key": "tradeoff:assumptions",
        "severity": "info",
        "headline": "This plan assumes current conditions hold",
        "narrative": (
            "The allocation reflects historical response curves and current "
            "attribution patterns. Major shifts in market conditions, "
            "competitive dynamics, or creative performance would require "
            "re-running the analysis with updated data."
        ),
    })

    return tradeoffs


def compute_plan_kpis(summary: Dict, moves: List[Dict], plan_confidence: str) -> Dict:
    """KPI pills shown at the top of the Plan screen."""
    total_moved = sum(abs(m["spend_delta"]) for m in moves) / 2
    revenue_uplift = float(summary.get("revenue_uplift", 0))
    optimized_roi = float(summary.get("optimized_roi", 0))
    current_roi = float(summary.get("current_roi", 0))
    roi_delta = optimized_roi - current_roi

    return {
        "reallocation_size": {
            "value": round(total_moved, 0),
            "display": _format_dollars(total_moved),
            "label": "Reallocation Size",
            "tone": "neutral",
            "context": f"{len([m for m in moves if m['action'] != 'hold'])} channels affected",
        },
        "expected_uplift": {
            "value": round(revenue_uplift, 0),
            "display": _signed_dollars(revenue_uplift),
            "label": "Expected Uplift",
            "tone": "positive" if revenue_uplift > 0 else "warning",
            "context": f"{float(summary.get('uplift_pct', 0)):+.1f}% vs. current allocation",
        },
        "plan_confidence": {
            "value": plan_confidence,
            "display": plan_confidence,
            "label": "Plan Confidence",
            "tone": {
                "High": "positive",
                "Directional": "neutral",
                "Inconclusive": "warning",
            }.get(plan_confidence, "neutral"),
            "context": f"ROI: {current_roi:.1f}x → {optimized_roi:.1f}x ({roi_delta:+.1f})",
        },
    }


def generate_plan(
    optimization: Dict,
    response_curves: Dict,
    engagement_id: str = "default",
    view: str = "client",
    bayes_result: Optional[Dict] = None,
) -> Dict:
    """
    Top-level assembly. Produces the full Plan screen payload.

    Mirror of generate_diagnosis() in engines/narrative.py — same view
    semantics ("client" filters suppressions, "editor" returns everything
    with flags), same override layering, same metadata shape.

    `bayes_result` (optional) attaches Bayesian credible intervals to
    moves for channels in the Bayesian subset. Safe to pass None.
    """
    if not optimization or "channels" not in optimization:
        return _empty_plan(engagement_id, view)

    summary = optimization.get("summary", {}) or {}
    opt_info = optimization.get("optimizer_info", {}) or {}
    moves = build_moves(optimization["channels"], curves=response_curves, bayes_result=bayes_result)

    # Layer editor overrides the same way generate_diagnosis does
    overrides = _load_overrides_safely(engagement_id)
    commentary_map = overrides["commentary"]
    suppressions_map = overrides["suppressions"]
    rewrites_map = overrides["rewrites"]

    processed_moves = []
    for m in moves:
        key = m["key"]
        is_suppressed = key in suppressions_map
        if is_suppressed and view == "client":
            continue
        if key in commentary_map:
            m["ey_commentary"] = commentary_map[key]
        if key in rewrites_map:
            rw = rewrites_map[key]
            if view == "client":
                for field, new_text in rw.items():
                    m[field] = new_text
            else:
                m["rewrites"] = rw
        if is_suppressed and view == "editor":
            m["suppressed"] = True
            m["suppression_reason"] = suppressions_map[key]["reason"]
        processed_moves.append(m)

    headline = generate_plan_headline(summary, moves)
    hero = generate_plan_hero(summary, moves)
    tradeoffs = build_tradeoffs(opt_info, moves, response_curves or {})

    # Plan confidence logic: derived from optimizer convergence + curve
    # quality, same pattern as Diagnosis's compute_plan_confidence.
    if not opt_info.get("converged"):
        plan_confidence = "Inconclusive"
    elif opt_info.get("warnings"):
        plan_confidence = "Directional"
    else:
        # Check fraction of moves with near-linear fits
        near_linear_count = sum(
            1 for m in moves
            if (response_curves or {}).get(m["channel"], {}).get("near_linear_fit")
        )
        if near_linear_count > len(moves) / 3:
            plan_confidence = "Directional"
        else:
            plan_confidence = "High"

    kpis = compute_plan_kpis(summary, moves, plan_confidence)

    methodology = [
        {
            "engine": "Budget Optimizer",
            "method": opt_info.get("method", "scipy_SLSQP") + " with multi-start",
            "objective": opt_info.get("objective", "balanced"),
            "converged": opt_info.get("converged", False),
        },
        {
            "engine": "Response Curves",
            "method": "Power-law fits with LOO cross-validation",
            "channels_fitted": sum(
                1 for v in (response_curves or {}).values()
                if "error" not in v
            ),
        },
    ]

    return {
        "hero": hero,
        "headline_paragraph": headline,
        "kpis": kpis,
        "moves": processed_moves,
        "tradeoffs": tradeoffs,
        "methodology": methodology,
        "summary": {
            "total_budget": round(float(summary.get("total_budget", 0)), 0),
            "current_revenue": round(float(summary.get("current_revenue", 0)), 0),
            "optimized_revenue": round(float(summary.get("optimized_revenue", 0)), 0),
            "uplift_pct": round(float(summary.get("uplift_pct", 0)), 1),
        },
        "ey_overrides": {
            "engagement_id": engagement_id,
            "view": view,
            "counts": {
                "commentary": len(commentary_map),
                "suppressions": len(suppressions_map),
                "rewrites": sum(len(v) for v in rewrites_map.values()),
            },
        },
    }


def _empty_plan(engagement_id: str, view: str) -> Dict:
    """Fallback payload when the optimizer hasn't run."""
    return {
        "headline_paragraph": (
            "The budget optimizer hasn't produced an allocation yet. "
            "Run the analysis pipeline to generate a reallocation plan."
        ),
        "kpis": {},
        "moves": [],
        "tradeoffs": [],
        "methodology": [],
        "summary": {},
        "ey_overrides": {
            "engagement_id": engagement_id,
            "view": view,
            "counts": {"commentary": 0, "suppressions": 0, "rewrites": 0},
        },
    }


def _load_overrides_safely(engagement_id: str) -> Dict:
    """Load overrides from persistence, degrading to empty on failure."""
    try:
        from persistence import get_all_overrides
        return get_all_overrides(engagement_id)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            "Could not load plan overrides for engagement '%s': %s",
            engagement_id, e,
        )
        return {"commentary": {}, "suppressions": {}, "rewrites": {}}
