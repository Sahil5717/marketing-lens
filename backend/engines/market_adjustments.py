"""
Market adjustments engine.

Consumes the outputs of external_data.py (events, trends, competitive)
and produces structured adjustments that the Plan screen can layer on
top of the optimizer's frequentist + Bayesian baseline.

Honest framing:
  Baseline numbers come from the MMM + optimizer (response curves fit
  against historical data — "past").
  Adjustments here come from current market conditions — "present".
  The pitch story: "Plan uses Bayesian MMM for baseline ROAS + market
  overlay for current conditions."

This engine produces NO new statistical claims. Every adjustment has:
  - an explicit source (events / cost_trends / competitive)
  - a deterministic formula (documented in-code)
  - a magnitude that can be traced to the source data
  - a toggle state (editor can override via the UI)

When a CMO asks "why 8%?", the answer is traceable to a specific
CSV row and a specific formula, not a hidden posterior sample.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════════════════════
# Channel archetype mapping — used by competitive dampening logic.
# Reach-based channels (TV, OOH, radio, events) are most affected by
# competitive share-of-voice shifts because their value comes from
# grabbing audience attention that competitors are ALSO competing for.
# Digital performance channels (paid_search, social_paid) are less
# sensitive — clicks are clicks regardless of SOV.
# ═══════════════════════════════════════════════════════════════════════

REACH_CHANNELS = {
    "tv_national", "tv_regional", "ooh", "radio",
    "events", "direct_mail",
}


def _signed_pct(x: float) -> str:
    sign = "+" if x >= 0 else ""
    return f"{sign}{x:.1f}%"


def generate_market_adjustments(
    plan_moves: List[Dict],
    events_result: Optional[Dict],
    trends_result: Optional[Dict],
    competitive_result: Optional[Dict],
) -> Dict[str, Any]:
    """
    Build the structured market-adjustments overlay.

    Returns:
      {
        "adjustments": [ { ... per-adjustment dict ... }, ... ],
        "baseline_total_revenue_delta": float,   # sum of plan moves pre-adjustment
        "adjusted_total_revenue_delta": float,   # after adjustments applied
        "summary": {
          "adjustment_count": int,
          "net_delta": float,              # adjusted - baseline
          "has_market_data": bool,         # False → UI hides the section
        }
      }

    Adjustment schema:
      {
        "id": "evt_diwali_2025" | "cost_paid_search_cpc" | "comp_tv_sov",
        "source": "events" | "cost_trends" | "competitive",
        "kind": "baseline_uplift" | "roas_adjustment" | "reach_dampening",
        "headline": "IPL 2025 — baseline revenue uplift of +8.0%",
        "magnitude_pct": 8.0,              # signed percent
        "revenue_delta": 420000.0,         # dollar impact of THIS adjustment
        "affected_channels": ["paid_search", ...],  # empty list = baseline-level
        "affected_months": ["2025-04", "2025-05"],  # or [] for "ongoing"
        "rationale": "...",                # analyst-voice prose
        "formula": "...",                  # the actual math, for transparency
        "source_ref": "Diwali 2025 event (Oct 12)",
        "applied": True,                   # analyst can toggle to False
      }
    """
    adjustments: List[Dict[str, Any]] = []
    has_events = bool(events_result and events_result.get("events"))
    has_trends = bool(trends_result and trends_result.get("cost_adjustments"))
    has_comp = bool(competitive_result and competitive_result.get("share_of_voice"))
    has_market_data = has_events or has_trends or has_comp

    baseline_delta = sum(float(m.get("revenue_delta", 0) or 0) for m in plan_moves)

    # ── 1. Event-driven adjustments ───────────────────────────────────
    # Upcoming events trigger baseline uplift (a raising tide) plus a
    # "prepare" signal on affected channels. Magnitude comes from the
    # event's own magnitude classification (low/med/high → 5/15/30%)
    # or an explicit impact_pct override from the CSV.
    if has_events:
        for evt in events_result.get("events", []):
            if not evt.get("is_upcoming"):
                continue  # only future events affect the plan
            magnitude = str(evt.get("magnitude", "medium")).lower()
            impact_pct = evt.get("impact_pct")
            if impact_pct is not None:
                uplift_pct = float(impact_pct)
            else:
                uplift_pct = {"low": 5.0, "medium": 15.0, "high": 30.0}.get(magnitude, 15.0)

            direction = str(evt.get("direction", "positive")).lower()
            if direction == "negative":
                uplift_pct = -abs(uplift_pct)

            affected = evt.get("affected_channels") or []
            # Impact: uplift_pct of the baseline revenue delta for one or
            # two months of the planning window. We're applying a BASELINE
            # uplift (not a per-channel one) so the "revenue_delta" on the
            # adjustment is a slice of baseline, not the full plan_delta.
            # Formula: uplift_pct * (baseline_delta / 12) — treating the
            # plan_delta as annualized and attributing 1 month of uplift.
            rev_impact = (uplift_pct / 100.0) * (baseline_delta / 12.0)

            evt_date = evt.get("date", "")
            evt_end = evt.get("end_date", evt_date)
            months = []
            try:
                months.append(evt_date[:7])
                if evt_end[:7] != evt_date[:7]:
                    months.append(evt_end[:7])
            except Exception:
                pass

            adjustments.append({
                "id": f"evt_{evt.get('name', 'unknown').lower().replace(' ', '_')}_{evt_date}",
                "source": "events",
                "kind": "baseline_uplift",
                "headline": f"{evt.get('name', 'Event')} — baseline revenue {_signed_pct(uplift_pct)}",
                "magnitude_pct": round(uplift_pct, 1),
                "revenue_delta": round(rev_impact, 0),
                "affected_channels": affected,
                "affected_months": months,
                "rationale": (
                    f"{evt.get('name')} is scheduled for {evt_date}"
                    + (f" through {evt_end}" if evt_end != evt_date else "")
                    + f". Historical seasonal lift of {magnitude} magnitude implies a "
                    + f"{_signed_pct(uplift_pct)} baseline revenue adjustment for that window."
                    + (f" Focus on {', '.join(affected)}." if affected else "")
                ),
                "formula": f"{uplift_pct:+.1f}% × (annualized baseline / 12 months)",
                "source_ref": f"Events CSV · {evt.get('name')} ({evt_date})",
                "applied": True,
            })

    # ── 2. Cost-trend adjustments (CPC/CPM inflation) ─────────────────
    # When CPCs are rising, the optimizer's recommendation to "increase
    # paid_search by X" will deliver LESS revenue than the curve
    # predicts because each dollar buys fewer clicks. We dampen the
    # revenue_delta on affected channels by the inflation factor.
    if has_trends:
        cost_adj = trends_result.get("cost_adjustments", {})
        for channel, adj in cost_adj.items():
            yoy = float(adj.get("yoy_change_pct", 0) or 0)
            # Only adjust for meaningful inflation — below ±5% is noise
            if abs(yoy) < 5.0:
                continue
            inflation = float(adj.get("inflation_factor", 1.0) or 1.0)

            # Find the move for this channel, if any
            move = next((m for m in plan_moves if m.get("channel") == channel), None)
            if not move:
                continue
            base_rev_delta = float(move.get("revenue_delta", 0) or 0)
            if abs(base_rev_delta) < 1e4:
                continue  # channel is being held; no adjustment needed

            # Dampening: if CPCs are up 12% YoY, expected revenue on this
            # channel's move is reduced by ~12%. Symmetric for deflation.
            # This is a first-order approximation — a true joint-optimization
            # would re-run with new cost curves, but that's outside scope.
            dampening_pct = -yoy  # if CPC +12, revenue impact -12
            rev_impact = base_rev_delta * (dampening_pct / 100.0)

            metric_name = "CPC" if "cpc" in adj.get("metric", "") else "CPM"
            # Headline magnitude = actual revenue impact direction, not the
            # dampening factor alone. A decrease move with CPC inflation
            # actually has a POSITIVE adjustment (cut hurts less).
            headline_pct = (rev_impact / max(abs(base_rev_delta), 1)) * 100
            adjustments.append({
                "id": f"cost_{channel}_{adj.get('metric')}",
                "source": "cost_trends",
                "kind": "roas_adjustment",
                "headline": (
                    f"{channel.replace('_', ' ').title()} — "
                    f"{metric_name} {_signed_pct(yoy)} YoY, revenue impact {_signed_pct(headline_pct)}"
                ),
                "magnitude_pct": round(headline_pct, 1),
                "revenue_delta": round(rev_impact, 0),
                "affected_channels": [channel],
                "affected_months": [],
                "rationale": (
                    f"{metric_name} for {channel.replace('_', ' ')} is trending {_signed_pct(yoy)} "
                    f"year-over-year (current: {adj.get('current_value')}). "
                    f"Each dollar of planned change buys {abs(dampening_pct):.1f}% "
                    f"{'fewer' if dampening_pct < 0 else 'more'} impressions, shifting the "
                    f"expected revenue impact of this move by {_signed_pct(headline_pct)}."
                ),
                "formula": f"baseline_revenue_delta × ({dampening_pct:+.1f}%)",
                "source_ref": f"Market trends CSV · {channel} {metric_name}",
                "applied": True,
            })

    # ── 3. Competitive SOV adjustments (reach channels only) ──────────
    # When competitors are gaining share of voice, OUR reach-based
    # channels become less efficient (audience attention is saturating).
    # We dampen reach-channel revenue_delta by the SOV shift.
    if has_comp:
        sov_map = competitive_result.get("share_of_voice", {})
        for channel, sov_data in sov_map.items():
            if channel not in REACH_CHANNELS:
                continue  # skip digital channels — SOV less relevant
            our_sov = float(sov_data.get("share_of_voice", 0.5) or 0.5)
            # A "fair share" baseline is 0.5 (we and competitor equal).
            # SOV below 0.4 → we're losing the reach battle, dampen.
            # SOV above 0.6 → we're winning, no dampening.
            if our_sov >= 0.4:
                continue
            # Dampening scales linearly: 0.4 sov → 0%, 0.2 sov → -20%
            dampening_pct = (our_sov - 0.4) * 100  # negative number

            move = next((m for m in plan_moves if m.get("channel") == channel), None)
            if not move:
                continue
            base_rev_delta = float(move.get("revenue_delta", 0) or 0)
            if abs(base_rev_delta) < 1e4:
                continue
            rev_impact = base_rev_delta * (dampening_pct / 100.0)

            adjustments.append({
                "id": f"comp_{channel}_sov",
                "source": "competitive",
                "kind": "reach_dampening",
                "headline": (
                    f"{channel.replace('_', ' ').title()} — SOV {our_sov*100:.0f}%, "
                    f"revenue impact {_signed_pct((rev_impact / max(abs(base_rev_delta), 1)) * 100)}"
                ),
                "magnitude_pct": round(dampening_pct, 1),
                "revenue_delta": round(rev_impact, 0),
                "affected_channels": [channel],
                "affected_months": [],
                "rationale": (
                    f"Our share of voice on {channel.replace('_', ' ')} is {our_sov*100:.0f}% "
                    f"— below the 40% threshold where reach-based channels start losing "
                    f"efficiency to competitor saturation. Reach efficiency dampened by "
                    f"{abs(dampening_pct):.1f}%, yielding a "
                    f"{_signed_pct((rev_impact / max(abs(base_rev_delta), 1)) * 100)} "
                    f"adjustment to the baseline revenue impact."
                ),
                "formula": f"baseline_revenue_delta × (SOV − 0.4) × 100 = {dampening_pct:+.1f}%",
                "source_ref": f"Competitive CSV · {channel} SOV",
                "applied": True,
            })

    # ── Summary ──────────────────────────────────────────────────────
    # Filter out adjustments whose dollar impact is below display threshold.
    # These happen when a channel has a small or zero plan move — the
    # dampening percentage is mathematically correct but the actual
    # dollar delta rounds to near-zero, which looks broken in the UI.
    # We keep them only if they represent a meaningful signal magnitude
    # (even if the plan move is small, the adjustment's relevance exists).
    DISPLAY_THRESHOLD = 10_000  # $10K minimum dollar impact to display
    adjustments = [
        a for a in adjustments
        if abs(float(a.get("revenue_delta", 0) or 0)) >= DISPLAY_THRESHOLD
    ]

    applied_delta = sum(
        float(a.get("revenue_delta", 0) or 0)
        for a in adjustments
        if a.get("applied", True)
    )
    adjusted_total = baseline_delta + applied_delta

    return {
        "adjustments": adjustments,
        "baseline_total_revenue_delta": round(baseline_delta, 0),
        "adjusted_total_revenue_delta": round(adjusted_total, 0),
        "summary": {
            "adjustment_count": len(adjustments),
            "net_delta": round(applied_delta, 0),
            "has_market_data": has_market_data,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def apply_overrides(
    adjustments_payload: Dict[str, Any],
    overrides: Dict[str, bool],
) -> Dict[str, Any]:
    """
    Apply analyst overrides to the adjustments payload.

    `overrides` is a dict mapping adjustment_id → applied (bool). Any
    adjustment not in the dict keeps its default `applied: True`.
    Updates `applied` field on each adjustment and recomputes the summary.
    """
    if not overrides:
        return adjustments_payload

    baseline_delta = float(adjustments_payload.get("baseline_total_revenue_delta", 0) or 0)
    new_adjustments = []
    for adj in adjustments_payload.get("adjustments", []):
        adj_copy = dict(adj)
        adj_id = adj_copy.get("id")
        if adj_id in overrides:
            adj_copy["applied"] = bool(overrides[adj_id])
            adj_copy["override_reason"] = (
                "Analyst toggled off" if not overrides[adj_id] else None
            )
        new_adjustments.append(adj_copy)

    applied_delta = sum(
        float(a.get("revenue_delta", 0) or 0)
        for a in new_adjustments
        if a.get("applied", True)
    )
    return {
        **adjustments_payload,
        "adjustments": new_adjustments,
        "adjusted_total_revenue_delta": round(baseline_delta + applied_delta, 0),
        "summary": {
            **adjustments_payload.get("summary", {}),
            "adjustment_count": len(new_adjustments),
            "net_delta": round(applied_delta, 0),
        },
    }


def generate_diagnosis_market_snippet(
    findings: List[Dict],
    events_result: Optional[Dict],
    trends_result: Optional[Dict],
    competitive_result: Optional[Dict],
) -> Optional[Dict[str, Any]]:
    """
    Produce an interpretive market-context snippet for the Diagnosis
    screen. This is NOT a list of raw events/trends — it's a
    cross-reference against the findings, so the CMO reads how current
    market conditions affect the priority of each issue.

    Returns None if there's no market data to surface — UI should hide.

    Output shape:
      {
        "headline": "Current market conditions: <short summary>",
        "signal_count": N,          # total market signals detected
        "interpretations": [
          {
            "kind": "event" | "cost_trend" | "competitive",
            "signal": "Search CPCs up 22% YoY",
            "implication": "Makes Finding #2 more urgent because ...",
            "related_finding_key": "finding:paid_search_under" | None,
            "urgency": "high" | "medium" | "low",
          },
          ...
        ],
        "summary_paragraph": "...",  # prose version for the snippet card
      }
    """
    has_events = bool(events_result and events_result.get("events"))
    has_trends = bool(trends_result and trends_result.get("cost_adjustments"))
    has_comp = bool(competitive_result and competitive_result.get("share_of_voice"))
    if not (has_events or has_trends or has_comp):
        return None

    interpretations: List[Dict[str, Any]] = []

    # Index findings by channel for quick lookup. Findings carry keys
    # in the pattern "finding:<channel>:<type>" (e.g. "finding:email:opportunity").
    # We extract the channel segment for lookup.
    finding_by_channel: Dict[str, Dict] = {}
    for f in findings or []:
        key = str(f.get("key", ""))
        # Try extracting from key pattern first
        if key.startswith("finding:"):
            parts = key.split(":")
            if len(parts) >= 2:
                finding_by_channel[parts[1]] = f
        # Fallback: explicit channel field if present
        ch = f.get("entity_channel") or f.get("channel")
        if ch and ch not in finding_by_channel:
            finding_by_channel[ch] = f

    # ── Events interpretation ──
    if has_events:
        upcoming = [e for e in events_result["events"] if e.get("is_upcoming")]
        pos_events = [e for e in upcoming if e.get("direction") == "positive"]
        neg_events = [e for e in upcoming if e.get("direction") == "negative"]

        for evt in pos_events[:2]:  # top 2 by chronology
            affected = evt.get("affected_channels") or []
            related_finding = None
            implication_extra = ""
            for ch in affected:
                if ch in finding_by_channel:
                    f = finding_by_channel[ch]
                    related_finding = f.get("key")
                    # If the finding is an opportunity/underinvestment, the
                    # event makes it MORE urgent (window closing).
                    f_type = str(f.get("type", "")).lower()
                    if "opportunity" in f_type or "under" in f_type:
                        implication_extra = (
                            f" Makes '{f.get('headline', f.get('title', 'this finding'))}' more urgent — "
                            f"the execution window closes in {evt.get('days_away')} days."
                        )
                    break
            interpretations.append({
                "kind": "event",
                "signal": f"{evt.get('name')} in {evt.get('days_away')} days "
                          f"({evt.get('magnitude')} magnitude)",
                "implication": (
                    f"Expected seasonal lift of {evt.get('impact_pct') or 15}% "
                    f"across {', '.join(affected) if affected else 'marketing overall'}."
                    + implication_extra
                ),
                "related_finding_key": related_finding,
                "urgency": "high" if evt.get("days_away", 999) < 30 else "medium",
            })

        for evt in neg_events[:1]:
            interpretations.append({
                "kind": "event",
                "signal": f"{evt.get('name')} in {evt.get('days_away')} days",
                "implication": (
                    f"Competitor action expected to dampen {', '.join(evt.get('affected_channels') or ['affected channels'])} "
                    f"by {abs(evt.get('impact_pct') or 8):.0f}%. Consider whether to maintain "
                    f"current TV/OOH spend through this window or reallocate."
                ),
                "related_finding_key": None,
                "urgency": "high" if evt.get("days_away", 999) < 30 else "medium",
            })

    # ── Cost trend interpretations ──
    if has_trends:
        cost_adj = trends_result.get("cost_adjustments", {})
        # Surface the most aggressive rising cost trend
        rising = sorted(
            [(ch, a) for ch, a in cost_adj.items() if float(a.get("yoy_change_pct", 0)) > 10],
            key=lambda x: -float(x[1].get("yoy_change_pct", 0)),
        )
        if rising:
            ch, adj = rising[0]
            yoy = float(adj.get("yoy_change_pct", 0))
            metric_name = "CPCs" if "cpc" in adj.get("metric", "") else "CPMs"
            related_finding = None
            implication_extra = ""
            if ch in finding_by_channel:
                f = finding_by_channel[ch]
                related_finding = f.get("key")
                f_type = str(f.get("type", "")).lower()
                if "under" in f_type or "opportunity" in f_type:
                    implication_extra = (
                        f" Makes '{f.get('headline', f.get('title', 'this finding'))}' more urgent — "
                        f"acting later costs more per dollar of reach."
                    )
                elif "over" in f_type or "cut" in f_type:
                    implication_extra = (
                        f" Reinforces '{f.get('headline', f.get('title', 'this finding'))}' — "
                        f"the cost environment is worsening, reducing is defensible."
                    )
            interpretations.append({
                "kind": "cost_trend",
                "signal": f"{ch.replace('_', ' ').title()} {metric_name} up {yoy:.0f}% YoY",
                "implication": (
                    f"Each dollar of {ch.replace('_', ' ')} spend buys {yoy:.0f}% fewer impressions "
                    f"than a year ago." + implication_extra
                ),
                "related_finding_key": related_finding,
                "urgency": "high" if yoy > 20 else "medium",
            })

        # Surface a declining cost if present (opportunity)
        declining = sorted(
            [(ch, a) for ch, a in cost_adj.items() if float(a.get("yoy_change_pct", 0)) < -10],
            key=lambda x: float(x[1].get("yoy_change_pct", 0)),
        )
        if declining:
            ch, adj = declining[0]
            yoy = float(adj.get("yoy_change_pct", 0))
            metric_name = "CPCs" if "cpc" in adj.get("metric", "") else "CPMs"
            interpretations.append({
                "kind": "cost_trend",
                "signal": f"{ch.replace('_', ' ').title()} {metric_name} down {abs(yoy):.0f}% YoY",
                "implication": (
                    f"Cheaper to buy {ch.replace('_', ' ')} inventory — worth revisiting "
                    f"whether the current plan's position on this channel should flex up."
                ),
                "related_finding_key": finding_by_channel.get(ch, {}).get("key"),
                "urgency": "low",
            })

    # ── Competitive interpretations ──
    if has_comp:
        sov_map = competitive_result.get("share_of_voice", {})
        # Find channels where we're losing reach — focus on REACH channels
        at_risk = sorted(
            [(ch, d) for ch, d in sov_map.items()
             if ch in REACH_CHANNELS and float(d.get("share_of_voice", 1)) < 0.3],
            key=lambda x: float(x[1].get("share_of_voice", 1)),
        )
        if at_risk:
            ch, d = at_risk[0]
            sov_pct = float(d.get("share_of_voice", 0)) * 100
            related_finding = finding_by_channel.get(ch, {}).get("key")
            interpretations.append({
                "kind": "competitive",
                "signal": f"{ch.replace('_', ' ').title()} SOV at {sov_pct:.0f}%",
                "implication": (
                    f"Competitors are spending {(1/max(d.get('share_of_voice', 0.5), 0.01)) - 1:.1f}x "
                    f"what we spend on {ch.replace('_', ' ')}. Reach-based channel "
                    f"efficiency suffers when competitors dominate the inventory."
                ),
                "related_finding_key": related_finding,
                "urgency": "medium",
            })

    if not interpretations:
        return None

    # Build summary paragraph
    high_urgency = [i for i in interpretations if i["urgency"] == "high"]
    summary_parts = []
    if high_urgency:
        summary_parts.append(
            f"{len(high_urgency)} high-urgency market signal{'s' if len(high_urgency) > 1 else ''} "
            f"affect the priority of the findings below."
        )
    else:
        summary_parts.append(
            f"{len(interpretations)} market signal{'s' if len(interpretations) > 1 else ''} "
            f"to consider alongside the findings below."
        )
    summary_parts.append(
        "These reflect current conditions (events calendar, cost trends, competitive SOV) "
        "and are layered on top of the historical baseline."
    )

    return {
        "headline": (
            f"Current market conditions: "
            f"{len(interpretations)} signal{'s' if len(interpretations) > 1 else ''} cross-referenced against findings"
        ),
        "signal_count": len(interpretations),
        "interpretations": interpretations,
        "summary_paragraph": " ".join(summary_parts),
    }
