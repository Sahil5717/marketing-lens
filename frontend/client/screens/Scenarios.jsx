import { useState, useCallback, useEffect, useMemo } from "react";
import styled, { css } from "styled-components";
import { t } from "../tokens.js";
import {
  fetchScenarioPresets,
  fetchScenario,
  fetchScenarioMarketAdjustments,
  overrideMarketAdjustment,
} from "../api.js";
import { Callout } from "../ui/Callout.jsx";
import { MoveCard } from "../ui/MoveCard.jsx";
import { TwoColumn, MainColumn, Sidebar } from "../ui/PageShell.jsx";
import { MarketOverlay } from "./Plan.jsx";

/**
 * Scenarios — redesigned per UX handoff + mockup Image 4.
 *
 * Different shape from Diagnosis/Plan: this is a control-first surface,
 * not a narrative one. The hero is the interactive controls (preset
 * row + custom input), and the narrative elements (Scenario Note) are
 * demoted to the sidebar.
 *
 * Structure:
 *   Zone 1 (controls):
 *     Eyebrow · Serif h1 with italic accent on "total budget"
 *     Paragraph
 *     Preset row (4 cards — Baseline / Conservative / Optimized / Aggressive),
 *       one preset uses dark-inverted treatment as the "Recommended" anchor
 *     Custom budget input: $ prefix, numeric input, "million / year" suffix,
 *       Run scenario button
 *
 *   Zone 2 (comparison):
 *     Three-column card: Current Plan → Selected Scenario = Delta
 *     Serif arrow separators between columns
 *
 *   Zone 3 (allocation + sidebar):
 *     Main: "Allocation under this scenario" heading + stacked MoveCards
 *     Sidebar: Scenario Note callout (serif italic pull-quote)
 *
 * Client-vs-editor boundary (per user decision, not the designer's
 * original handoff):
 *   - Clients CAN use the preset row and custom input (run scenarios)
 *   - Clients CANNOT save scenarios
 *   - Editor mode adds a "Save current scenario" button to the sidebar
 *     (rendered here, but the persistence API is an editor-only
 *      endpoint that clients cannot reach by construction)
 *
 * The designer's saved-scenarios sidebar (showing a list of named
 * scenarios) is NOT in v1 — it's queued for post-v1. For now, the
 * Save button is a placeholder hook.
 */
export function Scenarios({ data: initialData, view = "client" }) {
  // Initial payload from the shell's ensureScenarioReady() call — this
  // is the baseline (current-spend) scenario. User interactions trigger
  // fresh fetches that replace this.
  const [data, setData] = useState(initialData);
  const [presets, setPresets] = useState(null);
  const [activePreset, setActivePreset] = useState("baseline");
  const [customBudget, setCustomBudget] = useState("");
  const [loading, setLoading] = useState(false);
  const [runError, setRunError] = useState(null);
  // Market adjustments for the currently-displayed scenario. Recomputed
  // whenever the scenario's total_budget changes (preset change or
  // custom budget run). null = loading or not-yet-fetched.
  const [marketAdj, setMarketAdj] = useState(null);

  // Load presets once on mount
  useEffect(() => {
    let cancelled = false;
    fetchScenarioPresets().then(({ data: p, error }) => {
      if (!cancelled && p) {
        setPresets(p);
        // Initialize custom budget field to current spend (in $M)
        const currentM = (p.current_spend || 0) / 1e6;
        setCustomBudget(currentM.toFixed(1));
      }
    });
    return () => { cancelled = true; };
  }, []);

  const runScenario = useCallback(async ({ totalBudget, presetKey }) => {
    setLoading(true);
    setRunError(null);
    const { data: d, error } = await fetchScenario({
      totalBudget,
      view,
    });
    setLoading(false);
    if (d) {
      setData(d);
      setActivePreset(presetKey || "custom");
      // Also fetch market adjustments for this specific scenario budget.
      // Non-blocking — UI can render the comparison without waiting.
      setMarketAdj(null);  // clear stale view
      fetchScenarioMarketAdjustments({ totalBudget }).then(({ data: m }) => {
        if (m) setMarketAdj(m);
      });
    } else if (error) {
      setRunError(
        error.message || "Failed to run scenario. Check connection and try again."
      );
    }
  }, [view]);

  // Load market adjustments for the initial scenario on mount.
  useEffect(() => {
    if (!data) return;
    const budget = data?.scenario?.total_budget;
    if (budget == null) return;
    fetchScenarioMarketAdjustments({ totalBudget: budget }).then(({ data: m }) => {
      if (m) setMarketAdj(m);
    });
    // Run once on mount; subsequent changes handled by runScenario.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Handler for analyst override toggle — same optimistic update pattern
  // Plan uses. Updates in-memory state immediately, fires server sync.
  const handleAdjustmentToggle = useCallback(async (adjustmentId, newApplied) => {
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
    await overrideMarketAdjustment(adjustmentId, newApplied);
  }, []);

  const handlePresetClick = useCallback((preset) => {
    runScenario({
      totalBudget: preset.total_budget,
      presetKey: preset.key,
    });
    // Sync the custom input to show the preset's value
    setCustomBudget((preset.total_budget / 1e6).toFixed(1));
  }, [runScenario]);

  const handleCustomRun = useCallback(() => {
    const n = parseFloat(customBudget);
    if (Number.isNaN(n) || n <= 0) {
      setRunError("Enter a positive number for total budget.");
      return;
    }
    runScenario({
      totalBudget: n * 1e6,
      presetKey: "custom",
    });
  }, [customBudget, runScenario]);

  const handleSaveScenario = useCallback(() => {
    // Placeholder — wire to /api/scenarios/save in a later session
    alert("Save — wired to /api/scenarios/save in a later session");
  }, []);

  // Derived data
  const comparison = data?.comparison;
  const moves = (data?.moves || []).filter((m) => !m.suppressed);
  const scenarioNote = useMemo(() => {
    // Use the first warning-severity tradeoff if present; else first tradeoff
    const trs = data?.tradeoffs || [];
    return trs.find((tr) => tr.severity === "warning") || trs[0] || null;
  }, [data]);

  if (!data && !presets) return null;

  return (
    <Main>
      {/* ─── Zone 1: Controls ─── */}
      <ControlsShell>
        <Eyebrow>
          <EyebrowDot /> Scenarios · What-if explorer
        </Eyebrow>

        <Headline>
          What happens if we change the <em>total budget</em>?
        </Headline>
        <Lede>
          Pick a preset or set a custom total spend. The optimizer re-runs the
          allocation and shows projected outcomes compared to the current plan.
        </Lede>

        {/* Preset row */}
        {presets && (
          <PresetRow>
            {presets.presets?.map((p) => (
              <PresetCard
                key={p.key}
                preset={p}
                active={activePreset === p.key}
                recommended={p.key === "recommended"}
                onClick={() => handlePresetClick(p)}
                disabled={loading}
              />
            ))}
          </PresetRow>
        )}

        {/* Custom input */}
        <CustomRow>
          <CustomLabel>Custom budget</CustomLabel>
          <CustomInputWrap>
            <DollarPrefix>$</DollarPrefix>
            <CustomInput
              type="number"
              inputMode="decimal"
              step="0.1"
              min="0"
              value={customBudget}
              onChange={(e) => setCustomBudget(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleCustomRun(); }}
              disabled={loading}
              placeholder="48.7"
            />
            <CustomSuffix>million / year</CustomSuffix>
          </CustomInputWrap>
          <RunButton onClick={handleCustomRun} disabled={loading}>
            {loading ? "Running…" : "Run scenario"}
          </RunButton>
        </CustomRow>

        {runError && <ErrorBanner>{runError}</ErrorBanner>}
      </ControlsShell>

      {/* ─── Zone 2: Comparison card ─── */}
      {comparison && (
        <ComparisonShell>
          <ComparisonCard comparison={comparison} />
        </ComparisonShell>
      )}

      {/* ─── Zone 3: Allocation + sidebar ─── */}
      <BodyShell>
        <TwoColumn>
          <MainColumn>
            <AllocationHead>
              <AllocationTitle>Allocation under this scenario</AllocationTitle>
              <AllocationMeta>
                {activePreset === "custom"
                  ? "Custom budget"
                  : presets?.presets?.find((p) => p.key === activePreset)?.label || "Baseline"}
                {moves.length > 0 ? ` · ${moves.length} channels affected` : ""}
              </AllocationMeta>
            </AllocationHead>

            {/* Market overlay — scenario-specific adjustments layered on top
                of the scenario's moves. Only visible when external data is
                loaded AND the scenario actually produced moves (i.e. not
                baseline). Hidden cleanly when the scenario is the
                do-nothing baseline since there's nothing to adjust. */}
            {marketAdj &&
              marketAdj.summary?.has_market_data &&
              marketAdj.adjustments?.length > 0 &&
              moves.length > 0 && (
                <MarketOverlay
                  data={marketAdj}
                  editorMode={view === "editor"}
                  onToggle={handleAdjustmentToggle}
                  title="SCENARIOS · MARKET OVERLAY"
                />
              )}

            {moves.length === 0 && (
              <EmptyState>
                No reallocation under this scenario — the allocation is the same as the current plan.
              </EmptyState>
            )}

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
              />
            ))}
          </MainColumn>

          <Sidebar>
            {scenarioNote && (
              <Callout label="Scenario note" byline={`${data?.analyst?.name || "Sarah Rahman"}, reviewing analyst`}>
                {scenarioNote.narrative || scenarioNote.headline}
              </Callout>
            )}
            {view === "editor" && (
              <SaveScenarioCard onSave={handleSaveScenario} />
            )}
          </Sidebar>
        </TwoColumn>
      </BodyShell>
    </Main>
  );
}

// ─── Sub-components ───

/**
 * PresetCard — one of the four preset buttons in the preset row.
 * The "Recommended" preset gets the dark-inverted treatment shown
 * in the mockup (parallel to the primary KpiHero variant). Other
 * presets are light. Active state on any preset adds an accent border.
 */
function PresetCard({ preset, active, recommended, onClick, disabled }) {
  // The "Recommended" preset uses the inverted (dark) treatment when
  // it's the ACTIVE preset, matching the mockup's "PRESET · OPTIMIZED"
  // card which is dark when selected. Non-active recommended is still
  // highlighted but less aggressively.
  const inverted = active && recommended;

  return (
    <PresetButton
      onClick={onClick}
      disabled={disabled}
      $active={active}
      $inverted={inverted}
      $recommended={recommended}
    >
      <PresetEyebrow $inverted={inverted}>
        Preset · {preset.label.toUpperCase()}
      </PresetEyebrow>
      <PresetName $inverted={inverted}>
        {presetNameFor(preset)}
      </PresetName>
      <PresetValue $inverted={inverted}>
        ${(preset.total_budget / 1e6).toFixed(1)}M
      </PresetValue>
      {recommended && (
        <PresetHint $inverted={inverted}>
          {active ? "Recommended — matches Plan screen" : "Recommended"}
        </PresetHint>
      )}
      {!recommended && preset.description && (
        <PresetHint $inverted={inverted}>
          {shortDescription(preset)}
        </PresetHint>
      )}
    </PresetButton>
  );
}

/**
 * ComparisonCard — the three-column "Current Plan → Scenario = Delta" card.
 * Serif arrow characters between columns. Shows the comparison at a
 * glance. Per handoff: "the killer element of this screen — answers
 * 'what would change?' at a glance."
 */
function ComparisonCard({ comparison }) {
  const baseline = comparison.baseline || {};
  const scenario = comparison.scenario || {};
  const deltas = comparison.deltas || {};

  const revenueDelta = deltas.revenue_delta || 0;
  const roiDelta = deltas.roi_delta || 0;
  const budgetDelta = deltas.budget_delta || 0;

  const deltaHeading = describeDelta(budgetDelta, revenueDelta);

  return (
    <CompCard>
      <CompCol>
        <CompLabel>Current Plan</CompLabel>
        <CompValue className="tabular">{formatMoneyDisplay(baseline.total_budget)}</CompValue>
        <CompSub>
          Revenue: {formatMoneyDisplay(baseline.projected_revenue)} · ROAS: {baseline.projected_roi?.toFixed(2)}×
        </CompSub>
      </CompCol>

      <CompArrow aria-hidden="true">→</CompArrow>

      <CompCol>
        <CompLabel>Selected Scenario</CompLabel>
        <CompValue className="tabular">{formatMoneyDisplay(scenario.total_budget)}</CompValue>
        <CompSub>
          Revenue: {formatMoneyDisplay(scenario.projected_revenue)} · ROAS: {scenario.projected_roi?.toFixed(2)}×
        </CompSub>
      </CompCol>

      <CompArrowEquals aria-hidden="true">=</CompArrowEquals>

      <CompCol $isDelta>
        <CompLabel>Delta</CompLabel>
        <CompValue className="tabular" $direction={revenueDelta >= 0 ? "up" : "down"}>
          {formatSignedMoney(revenueDelta)}
        </CompValue>
        <CompSub $direction={revenueDelta >= 0 ? "up" : "down"}>
          {deltaHeading}
        </CompSub>
      </CompCol>
    </CompCard>
  );
}

function SaveScenarioCard({ onSave }) {
  return (
    <SidebarCard>
      <SidebarLabel>Saved scenarios (editor)</SidebarLabel>
      <SidebarCopy>
        Save the current scenario to share with the client for later review.
      </SidebarCopy>
      <SaveButton onClick={onSave}>Save current scenario</SaveButton>
    </SidebarCard>
  );
}

// ─── Helpers ───

function presetNameFor(preset) {
  // Match the mockup's preset names which are more evocative than the
  // backend's terse labels. Backend sends "Cut 20%" — we show
  // "Cut total spend". Backend sends "Optimizer recommended" — we show
  // "Hold total, reallocate".
  const map = {
    baseline: "Current plan",
    conservative: "Cut total spend",
    growth: "Increase budget",
    recommended: "Hold total, reallocate",
  };
  return map[preset.key] || preset.label;
}

function shortDescription(preset) {
  const map = {
    baseline: "Today's allocation, no changes",
    conservative: "Tighten spend; preserve highest-ROI channels",
    growth: "Test headroom at higher spend",
    recommended: "Recommended — matches Plan screen",
  };
  return map[preset.key] || "";
}

function reliabilityToTier(r) {
  const l = String(r || "").toLowerCase();
  // Match the Plan.jsx mapping: "reliable" is the backend's normal-case
  // value for solid fits, treated as high-confidence in the UI.
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

function formatMoneyDisplay(n) {
  // Comparison card uses slightly longer formatting for clarity — the
  // card has room and "$48.7M" reads better than "$48.7M" at this size
  if (n == null) return "—";
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${Math.round(n)}`;
}

function formatSignedMoney(n) {
  const sign = n >= 0 ? "+" : "-";
  const abs = Math.abs(n);
  if (abs === 0) return "$0";
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${sign}$${Math.round(abs / 1e3)}K`;
  return `${sign}$${Math.round(abs)}`;
}

function signed(n) {
  if (n == null) return "";
  return n >= 0 ? `+${n.toFixed(1)}` : n.toFixed(1);
}

function describeDelta(budgetDelta, revenueDelta) {
  // Short phrase describing what kind of trade this scenario represents
  if (Math.abs(revenueDelta) < 1e5) return "Same spend, same revenue";
  if (budgetDelta === 0 && revenueDelta > 0) return "Same spend, more revenue";
  if (budgetDelta === 0 && revenueDelta < 0) return "Same spend, less revenue";
  if (budgetDelta > 0 && revenueDelta > 0) return "More spend, more revenue";
  if (budgetDelta > 0 && revenueDelta < 0) return "More spend, less revenue";
  if (budgetDelta < 0 && revenueDelta > 0) return "Less spend, more revenue";
  if (budgetDelta < 0 && revenueDelta < 0) return "Less spend, less revenue";
  return "";
}

function makeActionHtml(m) {
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
  // Same sentence-boundary regex as Plan.jsx — don't split on decimals.
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

// ─── Styled ───

const Main = styled.main`
  min-height: 100vh;
  background: ${t.color.canvas};
  animation: mlFadeIn ${t.motion.slow} ${t.motion.ease};
`;

const ControlsShell = styled.section`
  max-width: ${t.layout.maxWidth};
  margin: 0 auto;
  padding: ${t.space[10]} ${t.layout.pad.wide} ${t.space[8]};
  display: flex;
  flex-direction: column;
  gap: ${t.space[4]};

  @media (max-width: ${t.layout.bp.wide}) {
    padding-left: ${t.layout.pad.narrow};
    padding-right: ${t.layout.pad.narrow};
  }
`;

const Eyebrow = styled.div`
  display: inline-flex;
  align-items: center;
  gap: ${t.space[2]};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  color: ${t.color.accentInk};
`;

const EyebrowDot = styled.span`
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: ${t.color.accent};
`;

const Headline = styled.h1`
  font-family: ${t.font.serif};
  font-size: clamp(32px, 4vw, 48px);
  font-weight: ${t.weight.regular};
  line-height: ${t.leading.snug};
  letter-spacing: ${t.tracking.tight};
  color: ${t.color.ink};
  margin: ${t.space[2]} 0 0 0;
  max-width: 820px;

  em, i {
    font-style: italic;
    color: ${t.color.accent};
    font-weight: ${t.weight.regular};
  }
`;

const Lede = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.md};
  color: ${t.color.ink2};
  line-height: ${t.leading.relaxed};
  margin: 0;
  max-width: 680px;
`;

const PresetRow = styled.div`
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: ${t.space[3]};
  margin-top: ${t.space[4]};

  @media (max-width: 900px) {
    grid-template-columns: repeat(2, 1fr);
  }
`;

const PresetButton = styled.button`
  display: flex;
  flex-direction: column;
  gap: ${t.space[2]};
  padding: ${t.space[5]} ${t.space[5]};
  border-radius: ${t.radius.lg};
  background: ${({ $inverted }) => ($inverted ? t.color.dark : t.color.surface)};
  border: 1px solid ${({ $active, $inverted }) =>
    $inverted ? "transparent" :
    $active ? t.color.accent :
    t.color.border};
  box-shadow: ${({ $inverted }) => ($inverted ? "none" : t.shadow.card)};
  text-align: left;
  cursor: pointer;
  transition: transform ${t.motion.base} ${t.motion.ease},
              box-shadow ${t.motion.base} ${t.motion.ease},
              border-color ${t.motion.base} ${t.motion.ease};

  &:hover:not(:disabled) {
    ${({ $inverted }) => !$inverted && css`
      box-shadow: ${t.shadow.raised};
      border-color: ${t.color.borderStrong};
    `}
  }

  &:disabled {
    opacity: 0.65;
    cursor: wait;
  }
`;

const PresetEyebrow = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  letter-spacing: ${t.tracking.wider};
  color: ${({ $inverted }) => ($inverted ? t.color.ink4 : t.color.ink3)};
`;

const PresetName = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.md};
  font-weight: ${t.weight.semibold};
  color: ${({ $inverted }) => ($inverted ? t.color.inkInverse : t.color.ink)};
`;

const PresetValue = styled.span`
  font-family: ${t.font.serif};
  font-size: ${t.size.xl};
  font-weight: ${t.weight.regular};
  letter-spacing: ${t.tracking.tight};
  line-height: 1;
  color: ${({ $inverted }) => ($inverted ? t.color.inkInverse : t.color.ink)};
`;

const PresetHint = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${({ $inverted }) => ($inverted ? t.color.ink4 : t.color.ink3)};
  line-height: ${t.leading.normal};
`;

const CustomRow = styled.div`
  display: flex;
  align-items: center;
  gap: ${t.space[4]};
  padding: ${t.space[5]} ${t.space[6]};
  background: ${t.color.surface};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.md};
  box-shadow: ${t.shadow.card};

  @media (max-width: 700px) {
    flex-wrap: wrap;
  }
`;

const CustomLabel = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  color: ${t.color.ink3};
  min-width: 130px;
`;

const CustomInputWrap = styled.div`
  display: flex;
  align-items: center;
  gap: ${t.space[2]};
  flex: 1;
`;

const DollarPrefix = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.md};
  color: ${t.color.ink3};
`;

const CustomInput = styled.input`
  width: 120px;
  padding: ${t.space[2]} ${t.space[3]};
  background: ${t.color.canvas};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.serif};
  font-size: ${t.size.lg};
  font-weight: ${t.weight.regular};
  color: ${t.color.ink};
  letter-spacing: ${t.tracking.tight};

  &:focus {
    border-color: ${t.color.accent};
    outline: none;
  }
`;

const CustomSuffix = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink3};
`;

const RunButton = styled.button`
  padding: ${t.space[3]} ${t.space[5]};
  background: ${t.color.dark};
  color: ${t.color.inkInverse};
  border: none;
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.semibold};
  cursor: pointer;
  transition: background ${t.motion.base} ${t.motion.ease};

  &:hover:not(:disabled) {
    background: ${t.color.darkSurface};
  }

  &:disabled {
    opacity: 0.6;
    cursor: wait;
  }
`;

const ErrorBanner = styled.div`
  padding: ${t.space[3]} ${t.space[4]};
  background: ${t.color.negativeBg};
  border: 1px solid ${t.color.negative}33;
  border-radius: ${t.radius.sm};
  color: ${t.color.negative};
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
`;

const ComparisonShell = styled.section`
  max-width: ${t.layout.maxWidth};
  margin: 0 auto;
  padding: 0 ${t.layout.pad.wide};

  @media (max-width: ${t.layout.bp.wide}) {
    padding-left: ${t.layout.pad.narrow};
    padding-right: ${t.layout.pad.narrow};
  }
`;

const CompCard = styled.div`
  display: grid;
  grid-template-columns: 1fr auto 1fr auto 1fr;
  align-items: center;
  gap: ${t.space[4]};
  padding: ${t.space[6]} ${t.space[8]};
  background: ${t.color.surface};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.lg};
  box-shadow: ${t.shadow.card};

  @media (max-width: 900px) {
    grid-template-columns: 1fr;
    text-align: center;
  }
`;

const CompCol = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${t.space[1]};
  min-width: 0;
`;

const CompLabel = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  color: ${t.color.ink3};
`;

const CompValue = styled.span`
  font-family: ${t.font.serif};
  font-size: clamp(28px, 3vw, 40px);
  font-weight: ${t.weight.regular};
  letter-spacing: ${t.tracking.tightest};
  line-height: 1;
  color: ${({ $direction }) =>
    $direction === "up" ? t.color.positive :
    $direction === "down" ? t.color.negative :
    t.color.ink};
`;

const CompSub = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${({ $direction }) =>
    $direction === "up" ? t.color.positive :
    $direction === "down" ? t.color.negative :
    t.color.ink3};
`;

const CompArrow = styled.span`
  font-family: ${t.font.serif};
  font-size: ${t.size["3xl"]};
  color: ${t.color.ink3};
  line-height: 1;

  @media (max-width: 900px) {
    display: none;
  }
`;

const CompArrowEquals = styled(CompArrow)``;

const BodyShell = styled.div`
  max-width: ${t.layout.maxWidth};
  margin: 0 auto;
  padding: ${t.space[8]} ${t.layout.pad.wide} ${t.space[16]};

  @media (max-width: ${t.layout.bp.wide}) {
    padding-left: ${t.layout.pad.narrow};
    padding-right: ${t.layout.pad.narrow};
  }
`;

const AllocationHead = styled.div`
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: ${t.space[3]};
  margin-bottom: ${t.space[4]};
`;

const AllocationTitle = styled.h2`
  font-family: ${t.font.serif};
  font-size: ${t.size.xl};
  font-weight: ${t.weight.regular};
  color: ${t.color.ink};
  letter-spacing: ${t.tracking.tight};
  margin: 0;
`;

const AllocationMeta = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink3};
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
  padding: ${t.space[5]};
  box-shadow: ${t.shadow.card};
  display: flex;
  flex-direction: column;
  gap: ${t.space[3]};
`;

const SidebarLabel = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink3};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
`;

const SidebarCopy = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink2};
  line-height: ${t.leading.relaxed};
  margin: 0;
`;

const SaveButton = styled.button`
  padding: ${t.space[2]} ${t.space[3]};
  background: ${t.color.surface};
  color: ${t.color.ink};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.medium};
  cursor: pointer;
  align-self: flex-start;
  transition: background ${t.motion.base} ${t.motion.ease}, border-color ${t.motion.base} ${t.motion.ease};

  &:hover {
    background: ${t.color.sunken};
    border-color: ${t.color.borderStrong};
  }
`;
