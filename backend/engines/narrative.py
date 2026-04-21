"""
Narrative Engine — Templated Prose Generation
==============================================

Produces the structured content that backs the Diagnosis screen:
- A diagnosis paragraph synthesizing portfolio state in 2-3 sentences
- 3-5 findings, each with a headline, supporting prose, confidence tier,
  impact estimate, and a pointer to the evidence chart
- Top-level KPIs (ROAS, Value at Risk, Plan Confidence tier)

This is a TEMPLATE-BASED engine (no LLM). The output quality ceiling is
"correct, grammatical, uses real numbers from the engines." It will not
pass as consultant-authored prose — by design. EY analysts can override
the narrative text through the commentary/rewrite layer (see CHANGES v16
for the product framing).

The module takes outputs from:
- engines/insights.py (executive_headlines, channel_stories, risk/opportunity)
- engines/leakage.py (three pillars)
- engines/diagnostics.py (recommendations list)
- engines/response_curves.py (per-channel curves)
- engines/optimizer.py (optimization summary)
- campaign_data (pandas DataFrame of campaign performance)

And returns a single dict in the shape the Diagnosis screen consumes.
"""

from typing import Dict, List, Optional
import pandas as pd

# Confidence tier mapping from internal engine confidence strings to the
# client-facing tier set. Only three tiers — High, Directional, Inconclusive —
# because more granularity than that is not actionable for a CMO reader.
#
# Internal terms that map to each:
#   High          → High, significant fit, converged
#   Directional   → Medium, marginally-significant, moderate fit
#   Inconclusive  → Low, non-significant, bad fit, near-linear, not_run
_CONFIDENCE_MAP = {
    "High": "High",
    "high": "High",
    "Medium": "Directional",
    "medium": "Directional",
    "Low": "Inconclusive",
    "low": "Inconclusive",
}


def _confidence_tier(raw: str) -> str:
    """Map an internal confidence string to the client-facing tier."""
    return _CONFIDENCE_MAP.get(raw, "Directional")


def _format_dollars(amount: float) -> str:
    """Format a dollar amount in compact form ($14.2M, $820K, $450)."""
    if amount is None or amount != amount:  # NaN check
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


def _format_pct(value: float, sign: bool = False) -> str:
    """Format a number as a percentage (signed or unsigned)."""
    if value is None or value != value:
        return "—"
    if sign:
        return f"{value:+.1f}%"
    return f"{value:.1f}%"


def _plain_channel_name(ch: str) -> str:
    """Humanize an internal channel ID to display form."""
    return ch.replace("_", " ").title() if ch else ""


def generate_hero_headline(
    total_revenue: float,
    roas: float,
    value_at_risk: float,
    recs: List[Dict],
    plan_delta: Optional[float] = None,
) -> Dict:
    """
    Build the structured answer-first headline for the Diagnosis hero.

    Per UX redesign (v18h): the hero needs to deliver the takeaway in one
    glance, not set up context across a paragraph. The mockup shows
    headlines like:

        "Portfolio ROAS is 3.2× — above benchmark. But $6.4M is
         recoverable through reallocation."

    with "3.2×" and "$6.4M" rendered as italic accent-colored fragments.

    We return a structured payload with `segments` so the frontend can
    apply the italic/accent treatment without regex-parsing a string.
    Each segment is either plain text or `emphasis=True` (for the
    key figures the mockup italicizes).

    Decisions this function makes (they're real editorial choices, so
    worth naming):

      - Anchor on ROAS + recoverable value. Not on revenue, not on
        spend — executives care about efficiency (ROAS) and opportunity
        (recoverable).
      - Two-clause structure: "X is [assessment]. But [contrasting
        opportunity]." This matches the mockup exactly and gives the
        reader both the state and the action in one sentence.
      - Tonal flip only when ROAS is genuinely strong (>=2.5x). If
        ROAS is poor, lead with the concern, not with "above benchmark."
      - Honest bridging: value_at_risk (from the pillars engine) and
        plan_delta (from the optimizer) measure different things. VaR
        is total leakage across the portfolio; plan_delta is what the
        current-budget reallocation can actually recover. When plan_delta
        is meaningfully smaller than VaR, we use plan_delta as the
        "recoverable" figure and add a secondary sentence about the
        remaining at-risk value.
    """
    var_pct = value_at_risk / max(total_revenue, 1) * 100
    roas_display = f"{roas:.1f}×"
    var_display = _format_dollars(value_at_risk)

    # Bridging logic: if optimizer's plan_delta is meaningfully smaller
    # than VaR, the honest "recoverable" number is plan_delta, not VaR.
    # Threshold: plan_delta must be at least 10% smaller to trigger bridging
    # (small differences are just measurement noise).
    use_bridged = (
        plan_delta is not None
        and plan_delta > 0
        and value_at_risk > plan_delta * 1.1
    )
    recoverable_value = plan_delta if use_bridged else value_at_risk
    recoverable_display = _format_dollars(recoverable_value) if use_bridged else var_display
    remaining_at_risk = value_at_risk - recoverable_value if use_bridged else 0

    # Segments: (text, emphasis) — emphasis maps to italic+accent in UI.
    # Benchmarks — retail CPG is ~2.5-3.0x, B2B SaaS is ~3.0-4.0x. We use
    # 2.8x as a generic "above benchmark" threshold. Real benchmarks
    # will come from industry_benchmarks if supplied.
    if roas >= 2.8 and var_pct > 3:
        # Strong ROAS but material recoverable — the most common case
        # and the flagship example in the mockup.
        segments = [
            {"text": "Portfolio ROAS is "},
            {"text": roas_display, "emphasis": True},
            {"text": " — above benchmark. But "},
            {"text": recoverable_display, "emphasis": True},
            {"text": " is recoverable through reallocation."},
        ]
        if remaining_at_risk > 0:
            segments.append({
                "text": f" An additional {_format_dollars(remaining_at_risk)} "
                        f"is at risk but requires operational changes beyond budget shifts."
            })
        tone = "positive_with_opportunity"
    elif roas >= 2.8:
        # Strong ROAS, minimal recoverable — congratulations phrasing
        segments = [
            {"text": "Portfolio ROAS is "},
            {"text": roas_display, "emphasis": True},
            {"text": " — above benchmark. The plan is largely about "
             "maintaining the current allocation."},
        ]
        tone = "positive"
    elif roas >= 1.5:
        # Middle ground — emphasize the opportunity
        segments = [
            {"text": "Portfolio ROAS of "},
            {"text": roas_display, "emphasis": True},
            {"text": " leaves "},
            {"text": recoverable_display, "emphasis": True},
            {"text": " on the table through under-allocated channels."},
        ]
        if remaining_at_risk > 0:
            segments.append({
                "text": f" Additional {_format_dollars(remaining_at_risk)} "
                        f"requires operational changes beyond reallocation."
            })
        tone = "mixed"
    else:
        # Poor ROAS — lead with the concern, not with benchmark comparison
        segments = [
            {"text": "Portfolio ROAS of "},
            {"text": roas_display, "emphasis": True},
            {"text": " signals structural over-spend. "},
            {"text": recoverable_display, "emphasis": True},
            {"text": " is recoverable through disciplined reallocation."},
        ]
        if remaining_at_risk > 0:
            segments.append({
                "text": f" {_format_dollars(remaining_at_risk)} additional "
                        f"requires operational improvements."
            })
        tone = "negative"

    # Lede paragraph — provides the "why" in two short sentences. This
    # supports the headline, doesn't try to be the headline. The mockup
    # shows this as a ~2-sentence bridge between headline and KPIs.
    top_rec = _find_top_actionable_recommendation(recs)
    if top_rec:
        ch_name = _plain_channel_name(top_rec.get("channel", ""))
        rec_type = top_rec.get("type", "")
        # Count distinct channels with significant recommendations to
        # give the lede a "how many channels" anchor
        sig_recs = [r for r in recs if abs(r.get("impact", 0)) > 100_000]
        n_channels = len({r.get("channel") for r in sig_recs if r.get("channel")})

        if rec_type == "SCALE":
            lede = (
                f"{ch_name} carries unused headroom relative to its response "
                f"curve. The plan reallocates across {n_channels} channels "
                f"without raising total spend."
            )
        elif rec_type == "REDUCE":
            lede = (
                f"{ch_name} is past saturation; marginal returns have "
                f"compressed. The plan reallocates across {n_channels} "
                f"channels to capture the recoverable value."
            )
        elif rec_type == "RETARGET":
            lede = (
                f"{ch_name} is acquiring customers at a premium to peer "
                f"channels. Targeting adjustments plus reallocation across "
                f"{n_channels} channels closes the gap."
            )
        else:
            lede = (
                f"{n_channels} channels carry meaningful opportunity. "
                f"The plan rebalances without requiring a spend increase."
            )
    else:
        lede = "The portfolio is operating within expected ranges."

    return {
        "segments": segments,
        "lede": lede,
        "tone": tone,
    }


def generate_diagnosis_paragraph(
    total_spend: float, total_revenue: float, overall_roi: float,
    value_at_risk: float, findings: List[Dict],
    recs: List[Dict], curves: Dict,
) -> str:
    """
    Build the 2-3 sentence paragraph that opens the Diagnosis screen.

    Rather than splicing finding headlines into sentences (which produced
    awkward results like "The dominant signal: scale paid search: $3.8m
    uplift available"), we generate the prose from the underlying
    structured data directly. Each sentence is a proper English sentence
    built around nouns and verbs chosen for this context.

    Structure:
        Sentence 1: State of play — ROAS, scale, context qualifier
        Sentence 2: The leading opportunity or concern, phrased as diagnosis
        Sentence 3 (optional): Value-at-risk summary with directional framing

    Reads like a consultant's opening paragraph, not a dashboard summary.
    """
    roas = total_revenue / max(total_spend, 1)
    var_pct = value_at_risk / max(total_revenue, 1) * 100

    # Sentence 1: current-state framing
    if overall_roi > 2.5:
        s1 = (
            f"Marketing is delivering {roas:.1f}x portfolio ROAS on "
            f"{_format_dollars(total_spend)} of annual spend, generating "
            f"{_format_dollars(total_revenue)} in attributable revenue."
        )
    elif overall_roi > 1:
        s1 = (
            f"Marketing is producing {roas:.1f}x portfolio ROAS on "
            f"{_format_dollars(total_spend)} of annual spend — positive "
            f"but with meaningful room to improve through reallocation."
        )
    else:
        s1 = (
            f"Portfolio ROAS of {roas:.1f}x on {_format_dollars(total_spend)} "
            f"of annual spend falls below sustainable return levels; "
            f"attributable revenue of {_format_dollars(total_revenue)} does "
            f"not cover the spend base with adequate margin."
        )

    # Sentence 2: lead finding — generated from recommendations directly
    # rather than spliced from finding headlines. We pick the highest-
    # impact actionable finding and describe what the data shows, then
    # (optionally) what can be done about it.
    top_rec = _find_top_actionable_recommendation(recs)
    if top_rec:
        ch_name = _plain_channel_name(top_rec.get("channel", ""))
        rec_type = top_rec.get("type", "")
        impact = abs(top_rec.get("impact", 0))

        if rec_type == "SCALE":
            s2 = (
                f"The strongest signal is {ch_name.lower()}: the response "
                f"curve indicates it is operating below saturation, with "
                f"approximately {_format_dollars(impact)} of annual uplift "
                f"available from a measured increase in spend."
            )
        elif rec_type == "REDUCE":
            s2 = (
                f"The strongest signal is {ch_name.lower()}: it is "
                f"approaching saturation, with marginal returns falling "
                f"below acceptable thresholds and roughly "
                f"{_format_dollars(impact)} recoverable from reallocation."
            )
        elif rec_type == "RETARGET":
            s2 = (
                f"The most significant concern is {ch_name.lower()}: "
                f"customer-acquisition cost runs substantially above peer "
                f"channels, with around {_format_dollars(impact)} of "
                f"potential savings from tighter audience targeting."
            )
        elif rec_type == "FIX":
            s2 = (
                f"The largest efficiency gap appears at the campaign level: "
                f"conversion rates lag benchmarks despite strong upstream "
                f"traffic, with roughly {_format_dollars(impact)} in "
                f"recoverable revenue from landing-page and form fixes."
            )
        else:
            s2 = (
                f"The leading actionable finding centers on {ch_name.lower()}, "
                f"with an estimated impact of {_format_dollars(impact)} "
                f"available from targeted adjustments."
            )
    else:
        # No high-impact recommendations; lead with a portfolio-level insight instead
        insight_finding = next(
            (f for f in findings if f.get("type") == "insight"),
            None
        )
        if insight_finding:
            s2 = _portfolio_insight_sentence(insight_finding)
        else:
            s2 = "The portfolio is performing within expected ranges across major metrics."

    # Sentence 3 (conditional): value-at-risk framing if meaningful
    if var_pct > 2:
        s3 = (
            f" Across the analysis, {_format_dollars(value_at_risk)} of "
            f"recoverable value ({var_pct:.1f}% of revenue) is identified, "
            f"concentrated in channel reallocation and campaign-level "
            f"inefficiencies."
        )
    else:
        s3 = ""

    return s1 + " " + s2 + s3


def _find_top_actionable_recommendation(recs: List[Dict]) -> Optional[Dict]:
    """Pick the highest-impact non-INVESTIGATE recommendation, or None."""
    candidates = [
        r for r in recs
        if r.get("type") != "INVESTIGATE" and abs(r.get("impact", 0)) > 1_000_000
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda r: abs(r.get("impact", 0)))


def _portfolio_insight_sentence(finding: Dict) -> str:
    """
    Build a contextual sentence from a portfolio-level insight finding,
    avoiding the awkward "The dominant signal: <headline>" pattern.

    Reads the finding's metric type and generates a purpose-built sentence
    rather than splicing the pre-written headline.
    """
    metric = (finding.get("evidence_metric") or {}).get("metric", "")
    if metric == "channel_gap":
        return (
            "Online channels meaningfully outperform offline channels on "
            "ROI, suggesting budget reallocation warrants consideration "
            "where offline does not carry specific strategic value."
        )
    if metric in ("concentration", "concentration_top2"):
        return finding.get("narrative") or finding.get("headline", "")
    if metric == "momentum":
        return finding.get("narrative") or finding.get("headline", "")
    # Fallback: use the detail text if available
    return finding.get("narrative") or finding.get("headline", "")


def _finding_key(finding: Dict) -> str:
    """
    Produce a stable identifier for a finding, used to key EY editor
    overrides (commentary, suppressions, rewrites).

    The key is derived from the finding's SEMANTIC content — channel (if
    any), type, and metric — rather than its array position. This way,
    when the backend re-runs analysis on fresh data and findings reorder,
    existing overrides stay pinned to the correct finding.

    Format: "finding:<channel_or_metric>:<type>"

    Examples:
      "finding:paid_search:opportunity"  — a SCALE-type rec for paid search
      "finding:display:warning"          — a REDUCE or RETARGET warning
      "finding:channel_gap:insight"      — portfolio-level online/offline gap
      "finding:roi:neutral"              — portfolio ROI state
    """
    em = finding.get("evidence_metric") or {}
    channel = em.get("channel")
    metric = em.get("metric")
    subject = channel or metric or "unknown"
    # Normalize: strip spaces, lowercase. Channel IDs are already
    # snake_case from the engines; metrics are single words.
    subject = str(subject).strip().lower().replace(" ", "_")
    finding_type = str(finding.get("type", "insight")).strip().lower()
    return f"finding:{subject}:{finding_type}"


def build_findings(
    insights: Dict, recs: List[Dict], curves: Dict,
    pillars: Dict, campaign_df: pd.DataFrame,
) -> List[Dict]:
    """
    Assemble the Diagnosis screen's ranked finding list from multiple engine
    outputs.

    A "finding" is a self-contained insight with:
        - headline: one line, diagnosis-phrased (e.g. "Paid search is
          underspent relative to its response curve"), NOT prescription-
          phrased ("Scale paid search"). The prescription lives in the
          separate prescribed_action field so the UI can render it with
          appropriate framing (a CMO reading a finding should be told what
          the data says first, then what to do about it).
        - type: positive / warning / insight / opportunity / risk
        - confidence: High / Directional / Inconclusive
        - impact_dollars: if quantifiable
        - prescribed_action: the recommended follow-up action (verb-first)
        - narrative: 1-2 sentence paragraph explaining the diagnosis
        - evidence_chart, evidence_metric, source_engines: metadata

    Ranking: by impact dollars if available, else by priority field.
    Returns top 5.
    """
    findings = []

    # Pull from executive_headlines — these are portfolio-level diagnostic
    # claims ("Concentration risk: Paid Search drives 33% of revenue").
    # They are already diagnosis-phrased, so we pass them through.
    for h in insights.get("executive_headlines", []):
        findings.append({
            "headline": h.get("headline", ""),
            "type": h.get("type", "insight"),
            "confidence": _confidence_tier("High"),
            "impact_dollars": None,
            "prescribed_action": None,  # portfolio-level findings don't prescribe
            "narrative": h.get("detail", ""),
            "evidence_chart": _chart_for_metric(h.get("metric", "")),
            "evidence_metric": {"metric": h.get("metric"), "value": h.get("value")},
            "source_engines": ["insights"],
            "priority": h.get("priority", 5),
            "_rank_key": -h.get("priority", 5) * 1000,  # headlines first
        })

    # Pull high-impact recommendations, rewriting their headlines from
    # prescription-form to diagnosis-form. The action verb moves from the
    # headline into prescribed_action.
    for r in recs[:5]:
        if r.get("type") == "INVESTIGATE":
            # Near-linear fit: the channel needs an incrementality test
            # before we can say anything definitive about its scaling
            # headroom. This IS a finding about the data quality, not a
            # recommendation in the same sense as SCALE/REDUCE.
            ch_name = _plain_channel_name(r.get("channel", ""))
            findings.append({
                "headline": f"{ch_name} response curve is inconclusive",
                "type": "warning",
                "confidence": _confidence_tier(r.get("confidence", "Low")),
                "impact_dollars": None,
                "prescribed_action": f"Run a geo-lift or holdout test on {ch_name.lower()} before reallocating budget",
                "narrative": r.get("rationale", ""),
                "evidence_chart": "response_curve",
                "evidence_metric": {"channel": r.get("channel")},
                "source_engines": ["diagnostics", "response_curves"],
                "priority": 4,
                "_rank_key": -100,
            })
        elif abs(r.get("impact", 0)) > 1_000_000:
            findings.append(_recommendation_as_finding(r))

    # Dedupe by channel+type (avoid same channel showing up twice from
    # different angles). We identify duplicates by the first two words
    # of the headline plus the finding type.
    seen_keys = set()
    deduped = []
    for f in sorted(findings, key=lambda x: x["_rank_key"]):
        dedupe_key = _finding_dedupe_key(f)
        if dedupe_key not in seen_keys:
            seen_keys.add(dedupe_key)
            deduped.append(f)

    # Return top 5, strip internal rank key, and populate the stable
    # finding_key that the editor overlay uses to pin overrides.
    top = deduped[:5]
    for f in top:
        f.pop("_rank_key", None)
        f["key"] = _finding_key(f)
    return top


def _finding_dedupe_key(f: Dict) -> str:
    """Build a dedupe key that catches same-channel duplicate findings."""
    headline = f.get("headline", "").lower()
    # First three words usually identifies the subject (e.g. "paid search is")
    first_words = " ".join(headline.split()[:3])
    return f"{f.get('type','')}::{first_words}"


def _recommendation_as_finding(r: Dict) -> Dict:
    """
    Convert a recommendation from the diagnostics engine into a
    diagnosis-phrased finding.

    The key insight: a recommendation has TWO pieces of information — what
    the data shows about the channel, and what action to take. The headline
    should capture the first, the prescribed_action the second.

    Example transformation:
      recommendation: {
        type: "SCALE", channel: "paid_search",
        rationale: "ROI 2.8x (median 2.2x), 63% headroom, marginal ROI 1.8x.",
        action: "Increase spend by 32%", impact: 3883544,
      }
      ↓
      finding: {
        headline: "Paid Search is underspent relative to its response curve",
        prescribed_action: "Increase spend by 32% for an estimated $3.9M uplift",
        narrative: "...",
      }
    """
    ch_name = _plain_channel_name(r.get("channel", ""))
    rec_type = r.get("type", "")
    impact = r.get("impact", 0)
    action_verb = r.get("action", "")
    confidence = _confidence_tier(r.get("confidence", "Medium"))

    # Diagnosis-phrased headline per recommendation type. These describe
    # what the analysis observed, not what to do about it.
    if rec_type == "SCALE":
        headline = f"{ch_name} is underinvested relative to its response curve"
        finding_type = "opportunity"
        chart = "response_curve"
    elif rec_type == "REDUCE":
        headline = f"{ch_name} is near saturation — marginal returns are falling"
        finding_type = "warning"
        chart = "response_curve"
    elif rec_type == "RETARGET":
        # The rationale string from the diagnostics engine has the shape
        # "CAC $X is Y.Yx the portfolio median $Z." Extract the Y.Y to
        # surface the multiple in the finding headline.
        ratio = _extract_ratio_from_rationale(r.get("rationale", ""))
        headline = f"{ch_name} customer-acquisition cost is {_plain_multiple(ratio)} higher than peers"
        finding_type = "warning"
        chart = "cac_by_channel"
    elif rec_type == "FIX":
        camp = r.get("campaign", "")
        headline = f"{camp or ch_name}: traffic is arriving but not converting"
        finding_type = "warning"
        chart = "campaign_funnel"
    elif rec_type == "MAINTAIN":
        headline = f"{ch_name} is stronger than last-touch attribution suggests"
        finding_type = "insight"
        chart = "attribution_comparison"
    else:
        headline = f"{ch_name}: {r.get('rationale', '')[:60]}"
        finding_type = "insight"
        chart = "portfolio_overview"

    # Prescribed action — this is what the client surface shows as a
    # secondary line after the headline. Combines the raw action string
    # with the impact estimate so it's actionable in-context.
    if impact > 0:
        prescribed = f"{action_verb} — estimated {_format_dollars(abs(impact))} annual uplift"
    elif impact < 0:
        prescribed = f"{action_verb} — estimated {_format_dollars(abs(impact))} annual saving"
    else:
        prescribed = action_verb

    return {
        "headline": headline,
        "type": finding_type,
        "confidence": confidence,
        "impact_dollars": impact,
        "prescribed_action": prescribed,
        "narrative": r.get("rationale", ""),
        "evidence_chart": chart,
        "evidence_metric": {"channel": r.get("channel"), "action": action_verb},
        "source_engines": ["diagnostics", "response_curves"],
        "priority": 2,
        "_rank_key": -abs(impact),
    }


def _plain_multiple(ratio: float) -> str:
    """Format a multiple like 2.3 as "2.3x" or fallback to "substantially" if missing."""
    if ratio is None or ratio == 0:
        return "substantially"
    return f"{ratio:.1f}x"


def _extract_ratio_from_rationale(rationale: str) -> Optional[float]:
    """
    Extract a ratio value from a diagnostics rationale string.

    The diagnostics engine produces rationales like "CAC $X is 2.5x the
    portfolio median $Y" or "ROI 5.2x (median 2.2x), 63% headroom...".
    This helper pulls out the first number followed by 'x' that appears
    in the expected position ("is N.Nx") so the narrative layer can
    surface the ratio as a structured value.

    Returns None if no ratio is found (caller falls back to "substantially").
    """
    import re
    # Match patterns like "is 2.5x" or "is 18.6x"
    m = re.search(r"is\s+(\d+\.?\d*)x", rationale or "")
    if m:
        try:
            return float(m.group(1))
        except (ValueError, TypeError):
            return None
    return None


def _chart_for_metric(metric: str) -> str:
    """Map a metric name to the evidence chart type to show."""
    mapping = {
        "roi": "portfolio_roi_over_time",
        "concentration": "channel_revenue_share",
        "concentration_top2": "channel_revenue_share",
        "channel_gap": "online_offline_comparison",
        "momentum": "revenue_monthly_trend",
        "saturation_share": "headroom_by_channel",
        "growth_share": "headroom_by_channel",
        "cac_spread": "cac_by_channel",
    }
    return mapping.get(metric, "portfolio_overview")


def compute_plan_confidence(
    curves: Dict, mmm_result: Optional[Dict], opt_result: Dict,
) -> str:
    """
    Compute the top-level 'Plan Confidence' tier shown at the top of the
    Diagnosis screen. This is an aggregate of the underlying engines'
    diagnostics.

    Tier rules:
    - High: Most response curves have R² > 0.7, MMM converged (if run),
            optimizer converged without capacity warnings
    - Directional: Medium curves, some engine warnings, but core findings hold
    - Inconclusive: Bad fits dominate, MMM didn't converge, optimizer
            couldn't find improvement
    """
    signals = []

    # Response curve fit quality
    if curves:
        fits = [v for v in curves.values() if "error" not in v]
        if fits:
            good_fits = sum(1 for v in fits
                            if v.get("diagnostics", {}).get("r_squared", 0) > 0.7)
            share = good_fits / len(fits)
            if share > 0.7:
                signals.append("High")
            elif share > 0.4:
                signals.append("Directional")
            else:
                signals.append("Inconclusive")

    # MMM convergence (only if MMM was run)
    if mmm_result and mmm_result.get("method") not in (None, "not_run"):
        if mmm_result.get("model_diagnostics", {}).get("converged"):
            signals.append("High")
        else:
            signals.append("Directional")

    # Optimizer convergence
    if opt_result:
        info = opt_result.get("optimizer_info", {})
        warnings = info.get("warnings", [])
        capacity_warning = any("exceeds what the fitted curves" in w for w in warnings)
        if info.get("converged") and not capacity_warning:
            signals.append("High")
        elif info.get("converged"):
            signals.append("Directional")
        else:
            signals.append("Inconclusive")

    # Aggregate: take the weakest signal (most conservative). If any part
    # is Inconclusive, the whole is; if any is Directional, aggregate is
    # at most Directional.
    if not signals:
        return "Inconclusive"
    if "Inconclusive" in signals:
        return "Inconclusive"
    if "Directional" in signals:
        return "Directional"
    return "High"


def generate_diagnosis(
    campaign_df: pd.DataFrame,
    response_curves: Dict,
    optimization: Dict,
    pillars: Dict,
    insights: Dict,
    recommendations: List[Dict],
    mmm_result: Optional[Dict] = None,
    industry_benchmarks: Optional[Dict] = None,
    engagement_id: str = "default",
    view: str = "client",
) -> Dict:
    """
    Top-level assembly. Produces the full Diagnosis screen payload.

    Parameters
    ----------
    engagement_id : str
        Keyspace for EY editor overrides. Defaults to "default" for the
        single-tenant pitch tool; becomes the real engagement FK when
        multi-tenancy arrives.
    view : str
        Either "client" or "editor".
        - "client": suppressed findings are filtered out before returning,
          commentary is layered in, rewrites replace generated text.
        - "editor": ALL findings returned (including suppressed ones,
          flagged with suppression metadata for the editor UI).
          Commentary and rewrites attached as metadata but generated
          text is preserved so the editor can see both.

    Returns a dict with:
        headline_paragraph: str (the diagnosis sentence)
        kpis: {portfolio_roas, value_at_risk, plan_confidence}
        findings: list of 3-5 finding cards, each with a stable `key`
                  and optional `ey_commentary`, `suppressed`, `rewrites` fields
        industry_context: optional benchmarks overlay
        methodology: list of engine names that contributed
        ey_overrides: metadata summary (counts + mode) for the editor UI

    The result is flat, serializable, and designed to be wired directly
    into a React component via one fetch call to GET /api/diagnosis.
    """
    total_spend = float(campaign_df["spend"].sum())
    total_revenue = float(campaign_df["revenue"].sum())
    overall_roi = (total_revenue - total_spend) / max(total_spend, 1)
    roas = total_revenue / max(total_spend, 1)
    value_at_risk = float(pillars.get("total_value_at_risk", 0))

    # Build findings first — they feed the headline paragraph
    findings = build_findings(insights, recommendations, response_curves, pillars, campaign_df)

    headline = generate_diagnosis_paragraph(
        total_spend, total_revenue, overall_roi, value_at_risk, findings,
        recommendations, response_curves,
    )

    # Structured hero payload for the answer-first v1 design (mockup:
    # Image 2). The existing headline_paragraph stays as a fallback
    # for anything still wired to the old shape.
    # Extract plan_delta from optimization summary — this is the actual
    # revenue the reallocation can recover (distinct from value_at_risk
    # which counts total leakage). When they diverge, the hero honestly
    # bridges the two numbers.
    plan_delta = None
    if optimization:
        opt_summary = optimization.get("summary", {}) or {}
        plan_delta = opt_summary.get("revenue_uplift")
    hero = generate_hero_headline(
        total_revenue, roas, value_at_risk, recommendations,
        plan_delta=plan_delta,
    )

    # ── Layer EY editor overrides onto findings ──
    # Loaded lazily (import inside function) because narrative.py is imported
    # at module load time by the engines package, and persistence.py does
    # its init_db() on import which we don't want triggered in contexts
    # where sqlite isn't needed.
    overrides = _load_overrides_safely(engagement_id)
    commentary_map = overrides["commentary"]
    suppressions_map = overrides["suppressions"]
    rewrites_map = overrides["rewrites"]

    processed_findings = []
    for f in findings:
        key = f["key"]
        is_suppressed = key in suppressions_map

        # In client view, drop suppressed findings entirely before the
        # client ever sees them.
        if is_suppressed and view == "client":
            continue

        # Layer commentary (both views get this — client sees "EY's Take",
        # editor sees the existing text for possible editing).
        if key in commentary_map:
            f["ey_commentary"] = commentary_map[key]

        # Layer rewrites. In client view, rewritten text replaces generated
        # text. In editor view, we keep both so the UI can show a "rewritten"
        # indicator with option to revert.
        if key in rewrites_map:
            rw = rewrites_map[key]
            if view == "client":
                for field, new_text in rw.items():
                    f[field] = new_text
            else:
                f["rewrites"] = rw  # editor inspects original vs rewritten

        # Flag suppression only in editor view
        if is_suppressed and view == "editor":
            f["suppressed"] = True
            f["suppression_reason"] = suppressions_map[key]["reason"]

        processed_findings.append(f)

    plan_confidence = compute_plan_confidence(response_curves, mmm_result, optimization)

    # KPI pills shown at the top of the Diagnosis screen
    kpis = {
        "portfolio_roas": {
            "value": round(roas, 2),
            "display": f"{roas:.1f}x",
            "label": "Portfolio ROAS",
            "tone": "positive" if roas > 3 else ("neutral" if roas > 1.5 else "negative"),
            "benchmark": (industry_benchmarks or {}).get("portfolio_roas"),
        },
        "value_at_risk": {
            "value": round(value_at_risk, 0),
            "display": _format_dollars(value_at_risk),
            "label": "Value at Risk",
            "tone": "warning" if value_at_risk > total_revenue * 0.05 else "neutral",
            "pct_of_revenue": round(value_at_risk / max(total_revenue, 1) * 100, 1),
        },
        "plan_confidence": {
            "value": plan_confidence,
            "display": plan_confidence,
            "label": "Plan Confidence",
            "tone": {"High": "positive", "Directional": "neutral", "Inconclusive": "warning"}.get(plan_confidence, "neutral"),
        },
    }

    # Methodology: which engines produced the numbers
    methodology = []
    if response_curves:
        methodology.append({
            "engine": "Response Curves",
            "method": "Power-law regression with LOO cross-validation",
            "channels_fitted": sum(1 for v in response_curves.values() if "error" not in v),
        })
    if mmm_result and mmm_result.get("method") not in (None, "not_run"):
        methodology.append({
            "engine": "Marketing Mix Model",
            "method": mmm_result.get("method", "MLE"),
            "converged": mmm_result.get("model_diagnostics", {}).get("converged", False),
            "r_squared": mmm_result.get("model_diagnostics", {}).get("r_squared"),
        })
    if optimization:
        methodology.append({
            "engine": "Budget Optimizer",
            "method": "Scipy SLSQP with multi-start",
            "converged": optimization.get("optimizer_info", {}).get("converged", False),
        })
    if pillars:
        methodology.append({
            "engine": "Value-at-Risk Pillars",
            "method": "Leakage / CX suppression / avoidable cost decomposition",
            "total_var": round(value_at_risk, 0),
        })

    return {
        "hero": hero,
        "headline_paragraph": headline,
        "kpis": kpis,
        "findings": processed_findings,
        "industry_context": industry_benchmarks or {},
        "methodology": methodology,
        "data_coverage": {
            "total_spend": round(total_spend, 0),
            "total_revenue": round(total_revenue, 0),
            "n_channels": int(campaign_df["channel"].nunique()),
            "n_campaigns": int(
                campaign_df["campaign" if "campaign" in campaign_df.columns else "camp"].nunique()
            ),
            "period_rows": int(len(campaign_df)),
        },
        # Editor overlay metadata. The editor UI uses these counts to show
        # "3 suppressed · 5 comments" in the header and to confirm state
        # before publishing.
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


def _load_overrides_safely(engagement_id: str) -> Dict:
    """
    Load overrides from persistence. Isolated into its own function so that
    a failure here (missing sqlite, schema mismatch) degrades gracefully
    to "no overrides" rather than breaking diagnosis generation entirely.
    """
    try:
        from persistence import get_all_overrides
        return get_all_overrides(engagement_id)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            "Could not load editor overrides for engagement '%s': %s. "
            "Returning empty override set.",
            engagement_id, e,
        )
        return {"commentary": {}, "suppressions": {}, "rewrites": {}}
