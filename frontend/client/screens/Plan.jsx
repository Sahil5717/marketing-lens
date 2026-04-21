import { useMemo, useState, useEffect } from "react";
import styled from "styled-components";
import { t } from "../tokens.js";
import { fetchMarketAdjustments, overrideMarketAdjustment } from "../api.js";
import {
  HeroRow,
  HeroLeft,
  HeroRight,
  Eyebrow,
  HeroHeadline,
  HeroLede,
} from "../ui/HeroRow.jsx";
import { KpiHero } from "../ui/KpiHero.jsx";
import { Byline } from "../ui/Byline.jsx";
import { Callout } from "../ui/Callout.jsx";
import { MoveCard } from "../ui/MoveCard.jsx";
import { SubNav, SubNavTab } from "../ui/SubNav.jsx";
import { TwoColumn, MainColumn, Sidebar } from "../ui/PageShell.jsx";

/**
 * Plan — redesigned per UX handoff + mockup Image 3.
 *
 * Structurally parallel to Diagnosis (same hero + subnav + two-column
 * body shape) but with prescriptive voice instead of diagnostic voice.
 *
 * Key differences from Diagnosis:
 *   - Hero headline answers "what do we do?" not "what's wrong?"
 *   - KPIs: Reallocation Size (primary/dark), Expected Revenue Lift
 *          (green delta), Plan Confidence (ConfidenceBar)
 *   - SubNav tabs: Moves / Tradeoffs / Phased Rollout
 *   - Body: Moves grouped by direction (Increase / Reduce / Hold) with
 *          section headers showing count + dollar total. Within a
 *          group, moves are in impact order.
 *   - Sidebar: "What could go wrong" callout (warning-toned, derives
 *             from tradeoffs[]) + Phasing card (month-by-month rollout)
 *
 * The MoveCard component doesn't expand — per handoff: "moves are
 * already the summary; for more detail the user clicks the channel
 * name to open Channel Detail." (Channel Detail ships Session 5.)
 */
export function Plan({
  data,
  editorMode = false,
  // Note: onCommentaryEdit / onSuppressToggle props are NOT wired on
  // Plan in v18h. Move-level editor annotations and suppression would
  // require extending MoveCard with an editor footer; finding-level
  // editing on Diagnosis is the primary v1 editor flow. Move-level
  // editing is queued for a future iteration.
}) {
  const [activeTab, setActiveTab] = useState("moves");
  // Market adjustments overlay — fetched separately so Plan doesn't block
  // on it. null = loading, object = loaded (may have has_market_data:false).
  const [marketAdj, setMarketAdj] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetchMarketAdjustments().then(({ data }) => {
      if (!cancelled && data) setMarketAdj(data);
    });
    return () => { cancelled = true; };
  }, []);

  // Handler for analyst override toggle (editor mode only)
  const handleAdjustmentToggle = async (adjustmentId, newApplied) => {
    // Optimistic update first so the UI feels snappy
    setMarketAdj((prev) => {
      if (!prev) return prev;
      const adjustments = prev.adjustments.map((a) =>
        a.id === adjustmentId ? { ...a, applied: newApplied } : a
      );
      const net_delta = adjustments
        .filter((a) => a.applied)
        .reduce((s, a) => s + (a.revenue_delta || 0), 0);
      return {
        ...prev,
        adjustments,
        adjusted_total_revenue_delta: prev.baseline_total_revenue_delta + net_delta,
        summary: { ...prev.summary, net_delta },
      };
    });
    // Fire-and-forget server sync; re-fetch on error if ever hit one
    await overrideMarketAdjustment(adjustmentId, newApplied);
  };

  if (!data) return null;

  const hero = data.hero || {};
  const kpis = data.kpis || {};
  const moves = data.moves || [];
  const tradeoffs = data.tradeoffs || [];

  // Filter suppressed moves in client view, show them dimmed in editor view
  const visibleMoves = editorMode ? moves : moves.filter((m) => !m.suppressed);

  // Group moves by action — matches the mockup's "Increase / Reduce / Hold" layout
  const grouped = useMemo(() => {
    const buckets = { increase: [], decrease: [], hold: [] };
    for (const m of visibleMoves) {
      const bucket = buckets[m.action] ? m.action : "hold";
      buckets[bucket].push(m);
    }
    // Within each bucket, sort by absolute revenue_delta descending
    for (const k of Object.keys(buckets)) {
      buckets[k].sort(
        (a, b) => Math.abs(b.revenue_delta || 0) - Math.abs(a.revenue_delta || 0)
      );
    }
    return buckets;
  }, [visibleMoves]);

  const headlineElements = useMemo(() => {
    const segments = hero.segments || [];
    return segments.map((seg, i) =>
      seg.emphasis ? <em key={i}>{seg.text}</em> : <span key={i}>{seg.text}</span>
    );
  }, [hero.segments]);

  const reallocationKpi = kpis.reallocation_size;
  const upliftKpi = kpis.expected_uplift;
  const confKpi = kpis.plan_confidence;

  return (
    <Main>
      {/* ── Hero ── */}
      <HeroRow>
        <HeroLeft>
          <Eyebrow>Plan · Recommended action</Eyebrow>

          <HeroHeadline>
            {headlineElements.length > 0 ? headlineElements : data.headline_paragraph}
          </HeroHeadline>

          {hero.lede && <HeroLede>{hero.lede}</HeroLede>}

          <Byline
            initials={(data.analyst?.initials) || "SR"}
            name={(data.analyst?.name) || "Sarah Rahman"}
            role={(data.analyst?.role) || "Senior Manager"}
            verb="Recommended by"
            meta={planMethodologyMeta(data.methodology)}
          />
        </HeroLeft>

        <HeroRight>
          {reallocationKpi && (
            <KpiHero
              primary
              label={reallocationKpi.label}
              value={reallocationKpi.display.replace(/^\$|M$/g, "")}
              unit={reallocationKpi.display.endsWith("M") ? "M" : ""}
              context={reallocationKpi.context}
            />
          )}
          {upliftKpi && (
            <KpiHero
              label={upliftKpi.label}
              value={upliftKpi.display.replace(/^\+?\$|M$/g, "")}
              unit={upliftKpi.display.endsWith("M") ? "M" : ""}
              context={upliftKpi.context}
              deltaText={
                data.summary?.uplift_pct != null
                  ? `+${data.summary.uplift_pct.toFixed(1)}% vs current plan`
                  : undefined
              }
              deltaDirection="up"
            />
          )}
          {confKpi && (
            <KpiHero
              label={confKpi.label}
              value={confKpi.display}
              context={confKpi.context}
              confidence={confKpi.display?.toLowerCase()}
            />
          )}
        </HeroRight>
      </HeroRow>

      {/* ── Market overlay — sits above SubNav when external data present ── */}
      {marketAdj && marketAdj.summary?.has_market_data && marketAdj.adjustments?.length > 0 && (
        <MarketOverlay
          data={marketAdj}
          editorMode={editorMode}
          onToggle={handleAdjustmentToggle}
        />
      )}

      {/* ── SubNav ── */}
      <SubNav>
        <SubNavTab
          label="Moves"
          count={visibleMoves.length}
          active={activeTab === "moves"}
          onClick={() => setActiveTab("moves")}
        />
        <SubNavTab
          label="Tradeoffs"
          count={tradeoffs.length || undefined}
          active={activeTab === "tradeoffs"}
          onClick={() => setActiveTab("tradeoffs")}
        />
        <SubNavTab
          label="Roadmap"
          active={activeTab === "roadmap"}
          onClick={() => setActiveTab("roadmap")}
        />
        <SubNavTab
          label="Compare models"
          active={activeTab === "compare"}
          onClick={() => setActiveTab("compare")}
        />
      </SubNav>

      {/* ── Body ── */}
      <BodyShell>
        {activeTab === "moves" && (
          <TwoColumn>
            <MainColumn>
              {grouped.increase.length > 0 && (
                <MoveGroup
                  title="Increase"
                  moves={grouped.increase}
                  totalLabel={sumRevenueDelta(grouped.increase)}
                  direction="up"
                />
              )}
              {grouped.decrease.length > 0 && (
                <MoveGroup
                  title="Reduce"
                  moves={grouped.decrease}
                  totalLabel={sumRevenueDelta(grouped.decrease)}
                  direction="down"
                />
              )}
              {grouped.hold.length > 0 && (
                <MoveGroup
                  title="Hold"
                  moves={grouped.hold}
                  totalLabel={null}
                  direction="neutral"
                />
              )}
              {visibleMoves.length === 0 && (
                <EmptyState>No moves surfaced by this plan.</EmptyState>
              )}
            </MainColumn>

            <Sidebar>
              <WhatCouldGoWrongCard tradeoffs={tradeoffs} analyst={data.analyst} />
              <PhasingCard moves={visibleMoves} />
            </Sidebar>
          </TwoColumn>
        )}

        {activeTab === "tradeoffs" && <TradeoffsPane tradeoffs={tradeoffs} />}
        {activeTab === "roadmap" && <RoadmapPane moves={visibleMoves} />}
        {activeTab === "compare" && <ComparePane moves={visibleMoves} />}
      </BodyShell>
    </Main>
  );
}

// ─── Sub-components ───

/**
 * MarketOverlay — the "Market adjustments applied" section.
 *
 * Visible between the Plan hero and SubNav when external market data
 * (events / trends / competitive) has been processed. Shows:
 *   - Honest attribution header: "Plan uses Bayesian MMM for baseline
 *     ROAS + market overlay for current conditions"
 *   - Summary: baseline delta → adjusted delta, with net market impact
 *   - List of adjustment cards, grouped by source (events / trends /
 *     competitive), each with source badge, magnitude, rationale, and
 *     an override toggle (editor mode only)
 *
 * Design choice: NOT collapsed by default. The Partner specifically asked
 * for market changes to be visible on Plan, so hiding them behind a
 * disclosure would miss the point.
 */
/**
 * MarketOverlay — shared component used by Plan AND Scenarios screens.
 * Exported so Scenarios can render its own scenario-specific overlay
 * without duplicating the 170+ lines of component + styling.
 *
 * Props:
 *   data: the /market-adjustments or /market-adjustments/scenario payload
 *   editorMode: show toggle switches on adjustments
 *   onToggle: (adjustmentId, newApplied) => Promise — editor toggle handler
 *   title: override the "PLAN · MARKET OVERLAY" eyebrow. Pass
 *          "SCENARIOS · MARKET OVERLAY" etc.
 */
export function MarketOverlay({ data, editorMode, onToggle, title }) {
  const { adjustments = [], summary = {}, baseline_total_revenue_delta = 0, adjusted_total_revenue_delta = 0 } = data;
  const [expanded, setExpanded] = useState(true);

  // Group adjustments by source for visual sectioning
  const grouped = useMemo(() => {
    const g = { events: [], cost_trends: [], competitive: [] };
    for (const a of adjustments) {
      if (g[a.source]) g[a.source].push(a);
    }
    return g;
  }, [adjustments]);

  const netDelta = summary.net_delta || 0;
  const hasActiveAdjustments = adjustments.some((a) => a.applied);
  const appliedCount = adjustments.filter((a) => a.applied).length;

  return (
    <OverlayWrap>
      <OverlayHead>
        <OverlayEyebrow>
          <EyebrowDot />
          {title || "PLAN · MARKET OVERLAY"}
        </OverlayEyebrow>
        <OverlayHeadlineRow>
          <OverlayHeadline>
            Plan uses Bayesian MMM for baseline ROAS + market overlay for current conditions
          </OverlayHeadline>
          <OverlayToggleBtn
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
          >
            {expanded ? "Collapse" : "Expand"}
            <ChevronSpan $expanded={expanded}>▾</ChevronSpan>
          </OverlayToggleBtn>
        </OverlayHeadlineRow>
        <OverlaySub>
          {hasActiveAdjustments ? (
            <>
              <strong>{appliedCount}</strong> of <strong>{adjustments.length}</strong> market
              adjustment{adjustments.length === 1 ? "" : "s"} applied to the plan.{" "}
              {Math.abs(netDelta) >= 1e4 && (
                <>Net revenue impact: <DeltaInline $positive={netDelta >= 0}>
                  {formatSignedMoney(netDelta)}
                </DeltaInline> vs. baseline.</>
              )}
            </>
          ) : (
            <>All {adjustments.length} market adjustment{adjustments.length === 1 ? "" : "s"} disabled. Plan reflects baseline only.</>
          )}
        </OverlaySub>
      </OverlayHead>

      {expanded && (
        <OverlayBody>
          <OverlaySummaryRow>
            <OverlaySummaryCard>
              <OverlaySummaryLabel>Baseline plan impact</OverlaySummaryLabel>
              <OverlaySummaryValue>
                {formatSignedMoney(baseline_total_revenue_delta)}
              </OverlaySummaryValue>
              <OverlaySummarySub>from optimizer + Bayesian MMM</OverlaySummarySub>
            </OverlaySummaryCard>

            <OverlaySummaryArrow>→</OverlaySummaryArrow>

            <OverlaySummaryCard $accent>
              <OverlaySummaryLabel>Market-adjusted impact</OverlaySummaryLabel>
              <OverlaySummaryValue>
                {formatSignedMoney(adjusted_total_revenue_delta)}
              </OverlaySummaryValue>
              <OverlaySummarySub>
                {netDelta >= 0 ? "Market tailwind" : "Market headwind"}:{" "}
                <DeltaInline $positive={netDelta >= 0}>
                  {formatSignedMoney(netDelta)}
                </DeltaInline>
              </OverlaySummarySub>
            </OverlaySummaryCard>
          </OverlaySummaryRow>

          {Object.entries(grouped).map(([source, items]) =>
            items.length > 0 ? (
              <AdjustmentGroup key={source}>
                <AdjustmentGroupHead>
                  <AdjustmentSourceBadge $source={source}>
                    {sourceLabel(source)}
                  </AdjustmentSourceBadge>
                  <AdjustmentGroupCount>
                    {items.length} signal{items.length === 1 ? "" : "s"}
                  </AdjustmentGroupCount>
                </AdjustmentGroupHead>
                <AdjustmentGrid>
                  {items.map((adj) => (
                    <AdjustmentCard
                      key={adj.id}
                      adjustment={adj}
                      editorMode={editorMode}
                      onToggle={onToggle}
                    />
                  ))}
                </AdjustmentGrid>
              </AdjustmentGroup>
            ) : null
          )}

          {editorMode && data._is_mock_data && (
            <MockDisclaimer>
              ⓘ These signals are derived from sample market data loaded with
              demo. Upload client-specific events, cost trends, or competitive
              intelligence via Workspace to replace — same engine, real numbers.
            </MockDisclaimer>
          )}
        </OverlayBody>
      )}
    </OverlayWrap>
  );
}

/**
 * Single adjustment card — source chip, headline, rationale, formula,
 * override toggle (editor mode only).
 */
function AdjustmentCard({ adjustment, editorMode, onToggle }) {
  const applied = adjustment.applied !== false;
  const positive = (adjustment.revenue_delta || 0) >= 0;
  return (
    <AdjCardWrap $applied={applied}>
      <AdjCardHead>
        <AdjCardHeadline>{adjustment.headline}</AdjCardHeadline>
        {editorMode && (
          <AdjToggleLabel>
            <AdjToggleInput
              type="checkbox"
              checked={applied}
              onChange={(e) => onToggle(adjustment.id, e.target.checked)}
            />
            <AdjToggleTrack $checked={applied}>
              <AdjToggleKnob $checked={applied} />
            </AdjToggleTrack>
            <AdjToggleText>{applied ? "Applied" : "Disabled"}</AdjToggleText>
          </AdjToggleLabel>
        )}
      </AdjCardHead>

      <AdjCardRationale>{adjustment.rationale}</AdjCardRationale>

      <AdjCardFooter>
        <AdjCardStat>
          <AdjCardStatLabel>Revenue impact</AdjCardStatLabel>
          <AdjCardStatValue $positive={positive}>
            {formatSignedMoney(adjustment.revenue_delta || 0)}
          </AdjCardStatValue>
        </AdjCardStat>
        <AdjCardFormula title={adjustment.formula}>
          <AdjCardFormulaLabel>Formula</AdjCardFormulaLabel>
          <AdjCardFormulaValue>{adjustment.formula}</AdjCardFormulaValue>
        </AdjCardFormula>
        <AdjCardSource title={adjustment.source_ref}>
          {adjustment.source_ref}
        </AdjCardSource>
      </AdjCardFooter>
    </AdjCardWrap>
  );
}

function sourceLabel(source) {
  if (source === "events") return "Events calendar";
  if (source === "cost_trends") return "Cost trends";
  if (source === "competitive") return "Competitive SOV";
  return source;
}

function formatSignedMoney(n) {
  if (n == null || n === 0) return "$0";
  const sign = n < 0 ? "-" : "+";
  const abs = Math.abs(n);
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(0)}K`;
  return `${sign}$${Math.round(abs)}`;
}

function MoveGroup({ title, moves, totalLabel, direction }) {
  return (
    <GroupWrap>
      <GroupHead>
        <GroupTitle>{title}</GroupTitle>
        <GroupCount>{moves.length} channel{moves.length === 1 ? "" : "s"}</GroupCount>
        {totalLabel && (
          <GroupTotal $direction={direction}>{totalLabel}</GroupTotal>
        )}
      </GroupHead>
      <GroupList>
        {moves.map((m) => (
          <MoveCard
            key={m.key}
            tier={reliabilityToTier(m.reliability)}
            channel={formatChannel(m.channel)}
            action={makeActionHtml(m)}
            deltaValue={m.revenue_delta_display || m.spend_delta_display}
            deltaPct={m.change_pct != null ? `${signed(m.change_pct)}%` : undefined}
            deltaDirection={m.action === "increase" ? "up" : m.action === "decrease" ? "down" : "neutral"}
            beforeSpend={formatMoneyShort(m.current_spend)}
            afterSpend={formatMoneyShort(m.optimized_spend)}
            constraints={m.constraints}
            bayesDeltaHdi={m.bayes_delta_hdi_90}
          />
        ))}
      </GroupList>
    </GroupWrap>
  );
}

/**
 * WhatCouldGoWrongCard — sidebar callout derived from tradeoffs[].
 * Takes the first warning-severity tradeoff and renders it as a
 * pull-quote. If there are no warnings, shows a confidence-boosting
 * message instead (don't leave the sidebar empty).
 */
function WhatCouldGoWrongCard({ tradeoffs, analyst }) {
  const warning = tradeoffs.find((tr) => tr.severity === "warning") || tradeoffs[0];
  const name = analyst?.name || "Sarah Rahman";
  if (!warning) {
    return (
      <Callout label="What could go wrong" byline={`${name}, reviewing analyst`}>
        No significant downside risks identified in this plan. The moves are within
        historically-observed spend ranges and carry high-confidence fits.
      </Callout>
    );
  }
  return (
    <Callout label="What could go wrong" byline={`${name}, reviewing analyst`}>
      {warning.narrative || warning.headline}
    </Callout>
  );
}

/**
 * PhasingCard — sidebar rollout timeline. For v1 we derive this from
 * the moves themselves: high-confidence moves go in Month 1, everything
 * else spans Month 2-3, inconclusive moves get an extra validation
 * phase in Month 4+.
 */
function PhasingCard({ moves }) {
  // Same classifier as RoadmapPane — values are "reliable" / "inconclusive".
  const executable = moves.filter((m) => m.action !== "hold");
  const phase1 = executable.filter((m) => m.reliability === "reliable");
  const phase3 = executable.filter((m) => m.reliability === "inconclusive");
  const phase2 = executable.filter(
    (m) => m.reliability !== "reliable" && m.reliability !== "inconclusive"
  );

  return (
    <SidebarCard>
      <SidebarLabel>Phasing</SidebarLabel>
      <PhaseList>
        {phase1.length > 0 && (
          <PhaseRow>
            <PhaseName>Month 1</PhaseName>
            <PhaseCopy>
              {phase1.slice(0, 2).map((m) => actionShort(m)).join(". ")}
              {phase1.length > 2 ? ` + ${phase1.length - 2} more` : ""}.
            </PhaseCopy>
          </PhaseRow>
        )}
        {phase2.length > 0 && (
          <PhaseRow>
            <PhaseName>Month 2–3</PhaseName>
            <PhaseCopy>
              Monitor impact of Month 1 moves, then phase in:{" "}
              {phase2.slice(0, 2).map((m) => actionShort(m)).join(", ")}.
            </PhaseCopy>
          </PhaseRow>
        )}
        {phase3.length > 0 && (
          <PhaseRow>
            <PhaseName>Month 4+</PhaseName>
            <PhaseCopy>
              Run incrementality validation on {phase3.slice(0, 2).map((m) => formatChannel(m.channel)).join(", ")}
              {phase3.length > 2 ? ` + ${phase3.length - 2} more` : ""}. Adjust if uplift lags projections.
            </PhaseCopy>
          </PhaseRow>
        )}
        {phase1.length + phase2.length + phase3.length === 0 && (
          <PhaseCopy>Rollout plan available once moves are finalized.</PhaseCopy>
        )}
      </PhaseList>
    </SidebarCard>
  );
}

function TradeoffsPane({ tradeoffs }) {
  if (!tradeoffs.length) {
    return <EmptyState>No tradeoffs identified for this plan.</EmptyState>;
  }
  return (
    <PaneWrap>
      {tradeoffs.map((tr, i) => (
        <TradeoffRow key={tr.key || `tr-${i}`} $severity={tr.severity}>
          <TradeoffHead>{tr.headline}</TradeoffHead>
          <TradeoffBody>{tr.narrative}</TradeoffBody>
        </TradeoffRow>
      ))}
    </PaneWrap>
  );
}

/**
 * RoadmapPane — Gantt-style timeline of the full plan.
 *
 * Why Gantt vs the old text-block approach:
 *   - Lead time is a physical reality for offline channels (TV: 8 weeks
 *     from decision to first airing). A stacked list can't express this
 *     honestly.
 *   - CMOs think in calendar terms, not phase labels.
 *   - Pairs with the "N week lead time" chips we surface on MoveCard
 *     in Week 2 — this screen is where those lead times become a
 *     calendar rather than a note.
 *
 * The positioning algorithm is simple and deliberately read-only:
 *   - Phase 1 (reliable, action ≠ hold): starts at week 0.
 *     Bar width = max(lead_time_weeks, 4) so it's visible.
 *   - Phase 2 (directional): starts after any Month 1 bars close.
 *     Stacks behind Phase 1 so monitoring overlap is visible.
 *   - Phase 3 (inconclusive, needs validation): starts at Month 4
 *     (week 16), with a validation period before execution.
 *
 * Drag-edit is deferred — saving custom roadmaps requires a
 * `roadmap_overrides` SQLite table and per-user auth. The static
 * Gantt is the pitch deliverable.
 */
function RoadmapPane({ moves }) {
  // Phase classification. NOTE: reliability from backend is
  // "reliable" or "inconclusive" — the old "high" filter never matched
  // (that's why Month 1 was always empty on v18h). Fixing here:
  // reliable moves go to Month 1, inconclusive go to Month 4+,
  // everything else (hold) gets filtered out.
  const executable = moves.filter((m) => m.action !== "hold");
  const phase1 = executable.filter((m) => m.reliability === "reliable");
  const phase3 = executable.filter((m) => m.reliability === "inconclusive");
  const phase2 = executable.filter(
    (m) => m.reliability !== "reliable" && m.reliability !== "inconclusive"
  );

  if (executable.length === 0) {
    return <EmptyState>No executable moves to phase in yet.</EmptyState>;
  }

  // Build lane data: one lane per move. Weeks are [0, 52].
  // Bar: [start_week, end_week] with a phase color.
  const lanes = [];
  phase1.forEach((m) => {
    const lead = m.constraints?.lead_time_weeks || 1;
    lanes.push({
      move: m,
      phase: "phase1",
      startWeek: 0,
      endWeek: Math.max(lead, 4),
      label: "Execute",
    });
  });
  phase2.forEach((m) => {
    const lead = m.constraints?.lead_time_weeks || 1;
    // Phase 2 starts after a short observation window (4 weeks) so we
    // can validate Month 1 impact before phasing in more.
    const start = 4;
    lanes.push({
      move: m,
      phase: "phase2",
      startWeek: start,
      endWeek: start + Math.max(lead, 4),
      label: "Execute (after Month 1 review)",
    });
  });
  phase3.forEach((m) => {
    const lead = m.constraints?.lead_time_weeks || 1;
    // Phase 3: validation window (4 weeks) + execution with lead time
    lanes.push({
      move: m,
      phase: "phase3-validate",
      startWeek: 16,
      endWeek: 20,
      label: "Incrementality validation",
    });
    lanes.push({
      move: m,
      phase: "phase3-execute",
      startWeek: 20,
      endWeek: 20 + Math.max(lead, 4),
      label: "Execute (if validation passes)",
    });
  });

  return (
    <PaneWrap>
      {/* Legend */}
      <RoadmapLegend>
        <RoadmapLegendItem>
          <RoadmapLegendSwatch $color={t.color.dark} />
          <span>Month 1 — Execute now</span>
        </RoadmapLegendItem>
        <RoadmapLegendItem>
          <RoadmapLegendSwatch $color={t.color.accent} />
          <span>Month 2–3 — Phase in after review</span>
        </RoadmapLegendItem>
        <RoadmapLegendItem>
          <RoadmapLegendSwatch $color={t.color.ink3} $patterned />
          <span>Month 4+ — Validation required</span>
        </RoadmapLegendItem>
        <RoadmapLegendSep>·</RoadmapLegendSep>
        <RoadmapLegendMeta>
          Bar length reflects the channel's lead time. {phase1.length + phase2.length + phase3.length} moves, {lanes.length} scheduled blocks.
        </RoadmapLegendMeta>
      </RoadmapLegend>

      {/* Gantt */}
      <GanttCard>
        <GanttScroll>
          <GanttHead>
            <GanttLaneLabel />
            <GanttWeeks>
              {Array.from({ length: 12 }, (_, i) => (
                <GanttMonth key={i}>M{i + 1}</GanttMonth>
              ))}
            </GanttWeeks>
          </GanttHead>

          {lanes.map((lane, i) => (
            <GanttLane key={`${lane.move.key}-${lane.phase}`}>
              <GanttLaneLabel>
                <GanttLaneChannel>{formatChannel(lane.move.channel)}</GanttLaneChannel>
                <GanttLaneAction>
                  {lane.move.action === "increase" ? "↑ " : lane.move.action === "decrease" ? "↓ " : ""}
                  {signed(lane.move.change_pct)}%
                </GanttLaneAction>
              </GanttLaneLabel>
              <GanttTrack>
                <GanttBar
                  $startPct={(lane.startWeek / 52) * 100}
                  $widthPct={((lane.endWeek - lane.startWeek) / 52) * 100}
                  $phase={lane.phase}
                  title={`${formatChannel(lane.move.channel)} · ${lane.label} · Week ${lane.startWeek}–${lane.endWeek}${
                    lane.move.constraints?.lead_time_weeks > 1
                      ? ` · ${lane.move.constraints.lead_time_weeks}wk lead time`
                      : ""
                  }`}
                >
                  <GanttBarLabel>{lane.label}</GanttBarLabel>
                </GanttBar>
              </GanttTrack>
            </GanttLane>
          ))}
        </GanttScroll>
      </GanttCard>

      {/* Execution note */}
      <RoadmapFooter>
        <RoadmapFooterTitle>How to read this</RoadmapFooterTitle>
        <RoadmapFooterCopy>
          Each bar marks the execution window for one move. Bar length is
          driven by the channel's lead time: TV and events need 8–12 weeks
          between decision and first delivery, while digital channels flex
          within a week. Validation-required moves (Month 4+) carry a
          4-week incrementality window before the execution block starts.
        </RoadmapFooterCopy>
      </RoadmapFooter>
    </PaneWrap>
  );
}

/**
 * ComparePane — side-by-side frequentist vs Bayesian read per channel.
 *
 * Pitch story: "Here are both models. When they agree, high confidence.
 * When they disagree, here's why."
 *
 * Agreement logic (quiet — no alarm bells):
 *   aligned: frequentist point estimate falls inside Bayesian HDI range
 *   directional: both agree on direction (both positive or both negative)
 *                but magnitudes differ meaningfully
 *   diverge: sign disagreement or point outside HDI by wide margin
 *   no_bayes: channel isn't in the Bayesian subset, comparison n/a
 *
 * Rendered as a sortable table with a small agreement chip per row.
 * The analyst's eye is drawn to "diverge" rows because those are where
 * the models are telling different stories.
 */
function ComparePane({ moves }) {
  if (!moves || moves.length === 0) {
    return <EmptyState>No moves to compare.</EmptyState>;
  }

  // Derive comparison rows. One row per executable move.
  const rows = moves
    .filter((m) => m.action !== "hold")
    .map((m) => {
      const freqRoas = m.marginal_roi;  // marginal ROI from optimizer
      const bayesRoasPoint = m.bayes_roas_point;
      const bayesRoasHdi = m.bayes_roas_hdi_90;
      const freqDelta = m.revenue_delta;
      const bayesDeltaPoint = m.bayes_delta_point;
      const bayesDeltaHdi = m.bayes_delta_hdi_90;

      // Compute agreement. A few subtle cases to handle:
      let agreement = "no_bayes";
      let agreementText = "Not in Bayesian subset";

      if (bayesDeltaHdi && Array.isArray(bayesDeltaHdi)) {
        const [lo, hi] = bayesDeltaHdi;
        const freqIn = freqDelta >= lo && freqDelta <= hi;
        const sameSign = Math.sign(freqDelta) === Math.sign(bayesDeltaPoint || 0)
                      || Math.abs(freqDelta) < 1e4;  // tiny deltas don't count

        if (freqIn) {
          agreement = "aligned";
          agreementText = "Both models agree";
        } else if (sameSign) {
          agreement = "directional";
          agreementText = "Direction agrees, magnitude differs";
        } else {
          agreement = "diverge";
          agreementText = "Models disagree on impact";
        }
      }

      return {
        move: m,
        freqRoas,
        bayesRoasPoint,
        bayesRoasHdi,
        freqDelta,
        bayesDeltaPoint,
        bayesDeltaHdi,
        agreement,
        agreementText,
      };
    })
    // Sort: diverge first (draw eye), then directional, then aligned, then no_bayes
    .sort((a, b) => {
      const order = { diverge: 0, directional: 1, aligned: 2, no_bayes: 3 };
      return (order[a.agreement] ?? 3) - (order[b.agreement] ?? 3);
    });

  const bayesCount = rows.filter((r) => r.agreement !== "no_bayes").length;
  const divergeCount = rows.filter((r) => r.agreement === "diverge").length;

  return (
    <PaneWrap>
      {/* Summary strip */}
      <CompareSummary>
        <CompareSummaryCopy>
          Comparing <strong>{bayesCount}</strong> channels across both models.
          {divergeCount > 0 ? (
            <>
              {" "}<strong>{divergeCount}</strong> showing divergent estimates —
              worth a second look.
            </>
          ) : (
            <> No material divergence — both models tell the same story.</>
          )}
        </CompareSummaryCopy>
      </CompareSummary>

      <CompareTable>
        <thead>
          <tr>
            <CompareTh>Channel</CompareTh>
            <CompareTh $align="center">Frequentist</CompareTh>
            <CompareTh $align="center">Bayesian</CompareTh>
            <CompareTh $align="center">Agreement</CompareTh>
            <CompareTh>Read</CompareTh>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <CompareRow key={r.move.key || i} $agreement={r.agreement}>
              <CompareTd>
                <CompareChannelName>{formatChannel(r.move.channel)}</CompareChannelName>
                <CompareActionLine>
                  {r.move.action === "increase" ? "↑" : r.move.action === "decrease" ? "↓" : "—"}{" "}
                  {signed(r.move.change_pct)}% ·{" "}
                  {formatMoneyShort(r.move.current_spend)} →{" "}
                  {formatMoneyShort(r.move.optimized_spend)}
                </CompareActionLine>
              </CompareTd>

              <CompareTd $align="center">
                <CompareNumValue>{freqRoasDisplay(r.freqRoas)}</CompareNumValue>
                <CompareNumSub className="tabular">
                  {signedMoney(r.freqDelta)}
                </CompareNumSub>
              </CompareTd>

              <CompareTd $align="center">
                {r.bayesRoasPoint != null && Array.isArray(r.bayesRoasHdi) && r.bayesRoasHdi.length === 2 ? (
                  <>
                    <CompareNumValue>{r.bayesRoasPoint.toFixed(2)}×</CompareNumValue>
                    <CompareNumSub className="tabular">
                      HDI {r.bayesRoasHdi[0].toFixed(2)}–{r.bayesRoasHdi[1].toFixed(2)}×
                    </CompareNumSub>
                  </>
                ) : (
                  <CompareNumEmpty>—</CompareNumEmpty>
                )}
              </CompareTd>

              <CompareTd $align="center">
                <AgreementChip $agreement={r.agreement}>
                  {agreementLabel(r.agreement)}
                </AgreementChip>
              </CompareTd>

              <CompareTd>
                <CompareReadCopy>{agreementReadCopy(r)}</CompareReadCopy>
              </CompareTd>
            </CompareRow>
          ))}
        </tbody>
      </CompareTable>

      {/* Methodology footer */}
      <CompareFooter>
        <CompareFooterTitle>Why the models differ</CompareFooterTitle>
        <CompareFooterCopy>
          The frequentist response curve fits each channel's revenue vs spend
          independently using Levenberg-Marquardt power-law or Hill
          regression. The Bayesian MMM (PyMC NUTS) fits a joint time-series
          model with geometric adstock, Hill saturation, and seasonal
          covariates — 300 draws × 2 chains. When the two estimates agree,
          the channel's response is well-characterized by both lenses. When
          they diverge, the Bayesian typically reflects more uncertainty
          from limited data or carryover complexity the frequentist model
          smooths over.
        </CompareFooterCopy>
      </CompareFooter>
    </PaneWrap>
  );
}

function freqRoasDisplay(r) {
  if (r == null) return "—";
  return `${Number(r).toFixed(2)}×`;
}

function signedMoney(n) {
  if (n == null) return "—";
  const sign = n < 0 ? "-" : "+";
  const abs = Math.abs(n);
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(0)}K`;
  return `${sign}$${Math.round(abs)}`;
}

function agreementLabel(a) {
  if (a === "aligned") return "Aligned";
  if (a === "directional") return "Directional";
  if (a === "diverge") return "Diverge";
  return "N/A";
}

function agreementReadCopy(r) {
  if (r.agreement === "no_bayes") {
    return "Bayesian fit is limited to 6 priority channels; this channel relies on frequentist analysis alone.";
  }
  if (r.agreement === "aligned") {
    return "Both models converge on this move. High confidence — execute as planned.";
  }
  if (r.agreement === "directional") {
    return "Both models agree you should move this channel in the same direction, but the Bayesian HDI suggests the magnitude is uncertain. Reasonable to proceed but smaller steps advisable.";
  }
  if (r.agreement === "diverge") {
    return "The Bayesian model's 80% credible region does not contain the frequentist point estimate. Worth investigating before committing to this magnitude.";
  }
  return "";
}

// ─── Helpers ───

function reliabilityToTier(r) {
  const l = String(r || "").toLowerCase();
  // "high" and "reliable" both map to the confident tier. The backend
  // uses "reliable" for moves where the response curve fit is solid;
  // "high" is a UI-convention synonym we also accept.
  if (l === "high" || l === "reliable") return "high";
  if (l === "inconclusive" || l === "low") return "inconclusive";
  return "directional";
}

function formatChannel(ch) {
  if (!ch) return "";
  return ch.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatMoneyShort(n) {
  if (n == null) return null;
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `$${Math.round(n / 1e3)}K`;
  return `$${Math.round(n)}`;
}

function signed(n) {
  if (n == null) return "";
  return n >= 0 ? `+${n.toFixed(1)}` : n.toFixed(1);
}

function sumRevenueDelta(moves) {
  const total = moves.reduce((s, m) => s + (m.revenue_delta || 0), 0);
  if (total === 0) return null;
  const sign = total > 0 ? "+" : "-";
  const abs = Math.abs(total);
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(1)}M`;
  return `${sign}$${Math.round(abs / 1e3)}K`;
}

function actionShort(m) {
  const ch = formatChannel(m.channel);
  if (m.action === "increase") return `Scale ${ch}`;
  if (m.action === "decrease") return `Pull back on ${ch}`;
  return `Hold ${ch}`;
}

function actionSentence(m) {
  const ch = formatChannel(m.channel);
  const before = formatMoneyShort(m.current_spend);
  const after = formatMoneyShort(m.optimized_spend);
  if (m.action === "increase") return `Increase ${ch} from ${before} to ${after} (+${m.change_pct?.toFixed(0)}%).`;
  if (m.action === "decrease") return `Reduce ${ch} from ${before} to ${after} (${m.change_pct?.toFixed(0)}%).`;
  return `Hold ${ch} at ${before}.`;
}

function makeActionHtml(m) {
  // Generates the action sentence with bolded key figures (the mockup
  // bolds dollar amounts and phase-in qualifiers). Returned as a raw
  // HTML string because MoveCard supports dangerouslySetInnerHTML for
  // this inline bolding pattern.
  const ch = formatChannel(m.channel);
  const before = escapeHtml(formatMoneyShort(m.current_spend) || "");
  const after = escapeHtml(formatMoneyShort(m.optimized_spend) || "");
  if (m.action === "increase") {
    return `Increase spend from <strong>${before}</strong> to <strong>${after}</strong>. ${descriptor(m)}`;
  }
  if (m.action === "decrease") {
    return `Pull back from <strong>${before}</strong> to <strong>${after}</strong>. ${descriptor(m)}`;
  }
  return `Hold at <strong>${before}</strong>. ${descriptor(m)}`;
}

function descriptor(m) {
  const n = m.narrative || "";
  // Take the first full sentence. The previous regex /[.!?]/ split on
  // ANY period — including decimals like "1.52x" — producing truncated
  // sentences like "operates at 1." The fix: only split on sentence
  // terminators that are followed by whitespace + capital letter OR are
  // at end-of-string. This preserves decimals inside the sentence.
  const match = n.match(/^(.+?[.!?])(?:\s+[A-Z]|\s*$)/);
  const firstSentence = match ? match[1] : n;
  return escapeHtml(firstSentence);
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function planMethodologyMeta(methodology) {
  if (!methodology || methodology.length === 0) return null;
  const engines = methodology.map((m) => m.engine).slice(0, 3);
  return `Based on ${engines.join(" · ")}`;
}

// ─── Styled ───

const Main = styled.main`
  min-height: 100vh;
  background: ${t.color.canvas};
  animation: mlFadeIn ${t.motion.slow} ${t.motion.ease};
`;

const BodyShell = styled.div`
  max-width: ${t.layout.maxWidth};
  margin: 0 auto;
  padding: ${t.space[8]} ${t.layout.pad.wide} ${t.space[16]};

  @media (max-width: ${t.layout.bp.wide}) {
    padding-left: ${t.layout.pad.narrow};
    padding-right: ${t.layout.pad.narrow};
  }
`;

const GroupWrap = styled.section`
  display: flex;
  flex-direction: column;
  gap: ${t.space[3]};
  margin-bottom: ${t.space[8]};

  &:last-child {
    margin-bottom: 0;
  }
`;

const GroupHead = styled.header`
  display: flex;
  align-items: baseline;
  gap: ${t.space[3]};
  padding: 0 ${t.space[1]};
`;

const GroupTitle = styled.h3`
  font-family: ${t.font.body};
  font-size: ${t.size.md};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink};
  letter-spacing: ${t.tracking.snug};
  margin: 0;
`;

const GroupCount = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink3};
  font-weight: ${t.weight.regular};
`;

const GroupTotal = styled.span`
  margin-left: auto;
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.semibold};
  color: ${({ $direction }) =>
    $direction === "up" ? t.color.positive :
    $direction === "down" ? t.color.negative :
    t.color.ink3};
`;

const GroupList = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${t.space[3]};
`;

const EmptyState = styled.div`
  padding: ${t.space[10]} ${t.space[6]};
  background: ${t.color.surface};
  border: 1px dashed ${t.color.border};
  border-radius: ${t.radius.md};
  text-align: center;
  color: ${t.color.ink3};
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
`;

const SidebarCard = styled.aside`
  background: ${t.color.surface};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.md};
  padding: ${t.space[5]} ${t.space[5]};
  box-shadow: ${t.shadow.card};
`;

const SidebarLabel = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink3};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  margin-bottom: ${t.space[4]};
`;

const PhaseList = styled.ul`
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: ${t.space[4]};
`;

const PhaseRow = styled.li`
  display: flex;
  flex-direction: column;
  gap: 2px;
`;

const PhaseName = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink};
`;

const PhaseCopy = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink2};
  line-height: ${t.leading.normal};
`;

const PaneWrap = styled.div`
  max-width: ${t.layout.readingWidth};
  display: flex;
  flex-direction: column;
  gap: ${t.space[4]};
`;

const TradeoffRow = styled.article`
  padding: ${t.space[5]} ${t.space[6]};
  background: ${t.color.surface};
  border: 1px solid ${t.color.border};
  border-left: 3px solid ${({ $severity }) =>
    $severity === "warning" ? t.color.warning :
    $severity === "critical" ? t.color.negative :
    t.color.accent};
  border-radius: ${t.radius.md};
  box-shadow: ${t.shadow.card};
`;

const TradeoffHead = styled.h4`
  font-family: ${t.font.body};
  font-size: ${t.size.md};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink};
  margin: 0 0 ${t.space[2]} 0;
`;

const TradeoffBody = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink2};
  line-height: ${t.leading.relaxed};
  margin: 0;
`;

const PhaseBlock = styled.section`
  padding: ${t.space[5]} ${t.space[6]};
  background: ${t.color.surface};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.md};
  box-shadow: ${t.shadow.card};
`;

const PhaseBlockHead = styled.h4`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${t.color.accent};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  margin: 0 0 ${t.space[3]} 0;
`;

const PhaseBlockCopy = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink};
  line-height: ${t.leading.relaxed};

  ul {
    list-style: disc;
    padding-left: ${t.space[5]};
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: ${t.space[2]};
  }
`;

// ─── Roadmap Gantt styled components ───

const RoadmapLegend = styled.div`
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: ${t.space[4]};
  padding: ${t.space[3]} ${t.space[5]};
  background: ${t.color.surface};
  border: 1px solid ${t.color.borderFaint};
  border-radius: ${t.radius.sm};
  margin-bottom: ${t.space[5]};
`;

const RoadmapLegendItem = styled.span`
  display: inline-flex;
  align-items: center;
  gap: ${t.space[2]};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink2};
`;

const RoadmapLegendSwatch = styled.span`
  display: inline-block;
  width: 14px;
  height: 14px;
  border-radius: 2px;
  background: ${({ $color }) => $color};
  ${({ $patterned, $color }) =>
    $patterned
      ? `background: repeating-linear-gradient(
          45deg,
          ${$color},
          ${$color} 3px,
          transparent 3px,
          transparent 6px
        ), ${$color}33;`
      : ""}
`;

const RoadmapLegendSep = styled.span`
  color: ${t.color.ink4};
`;

const RoadmapLegendMeta = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
  margin-left: auto;
`;

const GanttCard = styled.div`
  background: ${t.color.surface};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.md};
  box-shadow: ${t.shadow.card};
  padding: ${t.space[4]};
  overflow: hidden;
`;

const GanttScroll = styled.div`
  overflow-x: auto;
`;

const GanttHead = styled.div`
  display: flex;
  padding-bottom: ${t.space[3]};
  border-bottom: 1px solid ${t.color.borderFaint};
  margin-bottom: ${t.space[2]};
`;

const GanttLaneLabel = styled.div`
  flex: 0 0 180px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-right: ${t.space[4]};
  min-width: 180px;
`;

const GanttLaneChannel = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink};
`;

const GanttLaneAction = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
  font-variant-numeric: tabular-nums;
`;

const GanttWeeks = styled.div`
  flex: 1;
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  min-width: 600px;
`;

const GanttMonth = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink3};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  text-align: center;
  border-left: 1px solid ${t.color.borderFaint};
  padding: 0 ${t.space[1]};

  &:first-child {
    border-left: none;
  }
`;

const GanttLane = styled.div`
  display: flex;
  align-items: center;
  padding: ${t.space[2]} 0;
  border-bottom: 1px solid ${t.color.borderFaint};

  &:last-child {
    border-bottom: none;
  }
`;

const GanttTrack = styled.div`
  flex: 1;
  position: relative;
  height: 28px;
  min-width: 600px;
  background: ${t.color.sunken};
  border-radius: ${t.radius.sm};
  /* Month dividers — visible behind bars */
  background-image: repeating-linear-gradient(
    to right,
    transparent,
    transparent calc(100% / 12 - 1px),
    ${t.color.borderFaint} calc(100% / 12 - 1px),
    ${t.color.borderFaint} calc(100% / 12)
  );
`;

const GanttBar = styled.div`
  position: absolute;
  top: 3px;
  bottom: 3px;
  left: ${({ $startPct }) => `${$startPct}%`};
  width: ${({ $widthPct }) => `${Math.max($widthPct, 2)}%`};
  min-width: 40px;
  border-radius: ${t.radius.sm};
  display: flex;
  align-items: center;
  padding: 0 ${t.space[2]};
  overflow: hidden;
  cursor: help;

  ${({ $phase }) => {
    if ($phase === "phase1") {
      return `
        background: ${t.color.dark};
        color: ${t.color.inkInverse};
      `;
    }
    if ($phase === "phase2") {
      return `
        background: ${t.color.accent};
        color: ${t.color.inkInverse};
      `;
    }
    if ($phase === "phase3-validate") {
      return `
        background: repeating-linear-gradient(
          45deg,
          ${t.color.ink3},
          ${t.color.ink3} 4px,
          ${t.color.ink4} 4px,
          ${t.color.ink4} 8px
        );
        color: ${t.color.inkInverse};
        border: 1px dashed ${t.color.ink2};
      `;
    }
    if ($phase === "phase3-execute") {
      return `
        background: ${t.color.ink3};
        color: ${t.color.inkInverse};
      `;
    }
    return `background: ${t.color.ink4}; color: ${t.color.inkInverse};`;
  }}

  &:hover {
    filter: brightness(1.08);
  }
`;

const GanttBarLabel = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
`;

const RoadmapFooter = styled.div`
  margin-top: ${t.space[5]};
  padding: ${t.space[4]} ${t.space[5]};
  background: ${t.color.sunken};
  border-left: 3px solid ${t.color.ink4};
  border-radius: 0 ${t.radius.sm} ${t.radius.sm} 0;
`;

const RoadmapFooterTitle = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink2};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  margin-bottom: ${t.space[2]};
`;

const RoadmapFooterCopy = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink2};
  line-height: ${t.leading.relaxed};
  margin: 0;
`;

// ─── Compare Pane styled components ───

const CompareSummary = styled.div`
  padding: ${t.space[4]} ${t.space[5]};
  background: ${t.color.surface};
  border: 1px solid ${t.color.borderFaint};
  border-radius: ${t.radius.sm};
  margin-bottom: ${t.space[5]};
`;

const CompareSummaryCopy = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink2};
  line-height: ${t.leading.relaxed};
  margin: 0;

  strong {
    color: ${t.color.ink};
    font-variant-numeric: tabular-nums;
  }
`;

const CompareTable = styled.table`
  width: 100%;
  border-collapse: collapse;
  background: ${t.color.surface};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.md};
  overflow: hidden;
  box-shadow: ${t.shadow.card};
`;

const CompareTh = styled.th`
  padding: ${t.space[4]} ${t.space[4]};
  text-align: ${({ $align }) => $align || "left"};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink3};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  border-bottom: 1px solid ${t.color.border};
  background: ${t.color.sunken};
`;

const CompareRow = styled.tr`
  border-bottom: 1px solid ${t.color.borderFaint};
  transition: background ${t.motion.base} ${t.motion.ease};

  &:last-child {
    border-bottom: none;
  }

  &:hover {
    background: ${t.color.sunken};
  }

  /* Subtle emphasis on diverge rows — a thin left border only */
  ${({ $agreement }) =>
    $agreement === "diverge" &&
    `
    border-left: 3px solid ${t.color.accent};
  `}
`;

const CompareTd = styled.td`
  padding: ${t.space[4]};
  vertical-align: top;
  text-align: ${({ $align }) => $align || "left"};
  font-family: ${t.font.body};
`;

const CompareChannelName = styled.div`
  font-size: ${t.size.sm};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink};
  margin-bottom: 2px;
`;

const CompareActionLine = styled.div`
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
  font-variant-numeric: tabular-nums;
`;

const CompareNumValue = styled.div`
  font-size: ${t.size.md};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink};
  font-variant-numeric: tabular-nums;
`;

const CompareNumSub = styled.div`
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
  margin-top: 2px;
`;

const CompareNumEmpty = styled.span`
  color: ${t.color.ink4};
  font-size: ${t.size.lg};
`;

const AgreementChip = styled.span`
  display: inline-flex;
  align-items: center;
  padding: 2px ${t.space[3]};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  letter-spacing: ${t.tracking.wider};
  text-transform: uppercase;
  white-space: nowrap;

  ${({ $agreement }) => {
    if ($agreement === "aligned") {
      return `
        background: ${t.color.positiveBg};
        color: ${t.color.positive};
      `;
    }
    if ($agreement === "directional") {
      return `
        background: ${t.color.sunken};
        color: ${t.color.ink2};
      `;
    }
    if ($agreement === "diverge") {
      return `
        background: ${t.color.accentSub};
        color: ${t.color.accentInk};
      `;
    }
    return `
      background: ${t.color.sunken};
      color: ${t.color.ink4};
    `;
  }}
`;

const CompareReadCopy = styled.div`
  font-size: ${t.size.sm};
  color: ${t.color.ink2};
  line-height: ${t.leading.relaxed};
  max-width: 360px;
`;

const CompareFooter = styled.div`
  margin-top: ${t.space[5]};
  padding: ${t.space[4]} ${t.space[5]};
  background: ${t.color.sunken};
  border-left: 3px solid ${t.color.ink4};
  border-radius: 0 ${t.radius.sm} ${t.radius.sm} 0;
`;

const CompareFooterTitle = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink2};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  margin-bottom: ${t.space[2]};
`;

const CompareFooterCopy = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink2};
  line-height: ${t.leading.relaxed};
  margin: 0;
`;

// ─── Market overlay styled components ───

const OverlayWrap = styled.section`
  margin: ${t.space[6]} 0 ${t.space[8]};
  background: ${t.color.surface};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.md};
  box-shadow: ${t.shadow.card};
  overflow: hidden;
`;

const OverlayHead = styled.div`
  padding: ${t.space[5]} ${t.space[6]};
  border-bottom: 1px solid ${t.color.borderFaint};
  background: linear-gradient(
    to bottom,
    ${t.color.sunken},
    ${t.color.surface}
  );
`;

const OverlayEyebrow = styled.div`
  display: flex;
  align-items: center;
  gap: ${t.space[2]};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${t.color.accent};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  margin-bottom: ${t.space[2]};
`;

const EyebrowDot = styled.span`
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: ${t.color.accent};
`;

const OverlayHeadlineRow = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: ${t.space[4]};
  margin-bottom: ${t.space[2]};
`;

const OverlayHeadline = styled.h2`
  font-family: ${t.font.serif};
  font-size: ${t.size.xl};
  font-weight: ${t.weight.medium};
  color: ${t.color.ink};
  line-height: ${t.leading.tight};
  margin: 0;
  flex: 1;
`;

const OverlayToggleBtn = styled.button`
  display: inline-flex;
  align-items: center;
  gap: ${t.space[2]};
  padding: ${t.space[2]} ${t.space[3]};
  border: 1px solid ${t.color.border};
  background: ${t.color.surface};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink2};
  cursor: pointer;
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  transition: background ${t.motion.base} ${t.motion.ease};
  flex-shrink: 0;

  &:hover { background: ${t.color.sunken}; }
`;

const ChevronSpan = styled.span`
  display: inline-block;
  transform: ${({ $expanded }) => ($expanded ? "rotate(0deg)" : "rotate(-90deg)")};
  transition: transform ${t.motion.base} ${t.motion.ease};
`;

const OverlaySub = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink3};
  line-height: ${t.leading.relaxed};
  margin: 0;

  strong {
    color: ${t.color.ink2};
    font-variant-numeric: tabular-nums;
  }
`;

const DeltaInline = styled.span`
  color: ${({ $positive }) => ($positive ? t.color.positive : t.color.negative)};
  font-weight: ${t.weight.semibold};
  font-variant-numeric: tabular-nums;
`;

const OverlayBody = styled.div`
  padding: ${t.space[6]};
`;

const OverlaySummaryRow = styled.div`
  display: flex;
  align-items: stretch;
  gap: ${t.space[4]};
  margin-bottom: ${t.space[6]};

  @media (max-width: 720px) {
    flex-direction: column;
  }
`;

const OverlaySummaryCard = styled.div`
  flex: 1;
  padding: ${t.space[4]} ${t.space[5]};
  background: ${({ $accent }) => ($accent ? t.color.accentSub : t.color.sunken)};
  border: 1px solid ${({ $accent }) => ($accent ? t.color.accent : t.color.borderFaint)};
  border-radius: ${t.radius.sm};
`;

const OverlaySummaryArrow = styled.div`
  display: flex;
  align-items: center;
  font-size: ${t.size.xl};
  color: ${t.color.ink3};

  @media (max-width: 720px) {
    justify-content: center;
    transform: rotate(90deg);
  }
`;

const OverlaySummaryLabel = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink3};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  margin-bottom: ${t.space[2]};
`;

const OverlaySummaryValue = styled.div`
  font-family: ${t.font.serif};
  font-size: ${t.size.xl};
  font-weight: ${t.weight.medium};
  color: ${t.color.ink};
  font-variant-numeric: tabular-nums;
  margin-bottom: ${t.space[1]};
`;

const OverlaySummarySub = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
`;

const AdjustmentGroup = styled.div`
  margin-bottom: ${t.space[6]};

  &:last-child { margin-bottom: 0; }
`;

const AdjustmentGroupHead = styled.div`
  display: flex;
  align-items: center;
  gap: ${t.space[3]};
  margin-bottom: ${t.space[4]};
  padding-bottom: ${t.space[2]};
  border-bottom: 1px solid ${t.color.borderFaint};
`;

const AdjustmentSourceBadge = styled.span`
  display: inline-flex;
  align-items: center;
  padding: 3px ${t.space[3]};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  border-radius: ${t.radius.sm};
  ${({ $source }) => {
    if ($source === "events") {
      return `background: ${t.color.accentSub}; color: ${t.color.accentInk};`;
    }
    if ($source === "cost_trends") {
      return `background: ${t.color.sunken}; color: ${t.color.ink2};`;
    }
    if ($source === "competitive") {
      return `background: ${t.color.positiveBg}; color: ${t.color.positive};`;
    }
    return `background: ${t.color.sunken}; color: ${t.color.ink3};`;
  }}
`;

const AdjustmentGroupCount = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
  font-variant-numeric: tabular-nums;
`;

const AdjustmentGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: ${t.space[4]};
`;

const AdjCardWrap = styled.div`
  padding: ${t.space[4]};
  background: ${t.color.surface};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.sm};
  opacity: ${({ $applied }) => ($applied ? 1 : 0.55)};
  transition: opacity ${t.motion.base} ${t.motion.ease};
`;

const AdjCardHead = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: ${t.space[3]};
  margin-bottom: ${t.space[2]};
`;

const AdjCardHeadline = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink};
  line-height: ${t.leading.tight};
  flex: 1;
`;

const AdjToggleLabel = styled.label`
  display: inline-flex;
  align-items: center;
  gap: ${t.space[2]};
  cursor: pointer;
  flex-shrink: 0;
`;

const AdjToggleInput = styled.input`
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
`;

const AdjToggleTrack = styled.span`
  position: relative;
  width: 32px;
  height: 18px;
  border-radius: 9px;
  background: ${({ $checked }) => ($checked ? t.color.accent : t.color.borderFaint)};
  transition: background ${t.motion.base} ${t.motion.ease};
`;

const AdjToggleKnob = styled.span`
  position: absolute;
  top: 2px;
  left: ${({ $checked }) => ($checked ? "16px" : "2px")};
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: ${t.color.surface};
  transition: left ${t.motion.base} ${t.motion.ease};
  box-shadow: 0 1px 2px rgba(0,0,0,0.2);
`;

const AdjToggleText = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.medium};
  color: ${t.color.ink3};
  min-width: 50px;
`;

const AdjCardRationale = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink2};
  line-height: ${t.leading.relaxed};
  margin: 0 0 ${t.space[4]};
`;

const AdjCardFooter = styled.div`
  display: grid;
  grid-template-columns: auto 1fr;
  grid-template-rows: auto auto;
  gap: ${t.space[2]} ${t.space[4]};
  padding-top: ${t.space[3]};
  border-top: 1px dashed ${t.color.borderFaint};
`;

const AdjCardStat = styled.div`
  grid-row: 1;
  grid-column: 1;
`;

const AdjCardStatLabel = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  margin-bottom: 2px;
`;

const AdjCardStatValue = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.md};
  font-weight: ${t.weight.semibold};
  color: ${({ $positive }) => ($positive ? t.color.positive : t.color.negative)};
  font-variant-numeric: tabular-nums;
`;

const AdjCardFormula = styled.div`
  grid-row: 1;
  grid-column: 2;
  text-align: right;
`;

const AdjCardFormulaLabel = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  margin-bottom: 2px;
`;

const AdjCardFormulaValue = styled.div`
  font-family: ${t.font.mono};
  font-size: ${t.size.xs};
  color: ${t.color.ink2};
  font-variant-numeric: tabular-nums;
`;

const AdjCardSource = styled.div`
  grid-row: 2;
  grid-column: 1 / -1;
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink4};
  font-style: italic;
`;

const MockDisclaimer = styled.div`
  margin-top: ${t.space[5]};
  padding: ${t.space[3]} ${t.space[4]};
  background: ${t.color.sunken};
  border: 1px dashed ${t.color.border};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
  font-style: italic;
  line-height: ${t.leading.relaxed};
`;
