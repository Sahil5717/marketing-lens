/**
 * BudgetOptimizationScreen — Screen 06 root composer.
 *
 * Layout (top → bottom):
 *   TopBar
 *   MintHeroInsight       (mint gradient — "same budget, more out")
 *   AtlasInlineCallout    (when rail is collapsed)
 *   AllocationComparison  (current + recommended donuts, earned reveal, edit mode)
 *   ImpactStrip           (4-cell, greys until allocation revealed)
 *   FourMoves             (prioritised moves with inline Why)
 *   NetSummary
 *   BridgeCard            (→ Screen 07)
 *
 * Data:
 *   /api/budget-optimization + /api/budget-optimization/override
 *   via useBudgetOptimization hook
 */
import React, { useState, useCallback } from "react";
import TopBar, { Pill } from "../../design/TopBar.jsx";
import { AtlasInlineCallout } from "../../design/AtlasRail.jsx";
import MintHeroInsight from "./MintHeroInsight.jsx";
import AllocationComparison from "./AllocationComparison.jsx";
import ImpactStrip from "./ImpactStrip.jsx";
import FourMoves from "./FourMoves.jsx";
import NetSummary from "./NetSummary.jsx";
import BridgeCard from "../executive_summary/BridgeCard.jsx";
import { useBudgetOptimization } from "./useBudgetOptimization.js";
import { tok } from "../../design/tokens.js";

const LoadingState = () => (
  <div style={{
    padding: "80px 0", textAlign: "center",
    color: tok.text3, fontSize: 13, fontFamily: tok.fontUi,
  }}>Loading budget optimization…</div>
);

const ErrorState = ({ error }) => (
  <div style={{
    padding: "40px 32px", background: tok.card,
    border: `1px solid ${tok.border}`, borderLeft: `3px solid ${tok.red}`,
    borderRadius: 10, fontFamily: tok.fontUi, color: tok.text,
  }}>
    <div style={{ fontWeight: 700, marginBottom: 6 }}>Couldn't load the budget optimization.</div>
    <div style={{ fontSize: 12, color: tok.text2 }}>{error}</div>
  </div>
);

export function BudgetOptimizationBody({
  data,
  onScoreOverride,
  atlasInline = false,
  onNavigateToScreen,
}) {
  const [revealed, setRevealed] = useState(false);

  if (!data) return <LoadingState/>;

  return (
    <>
      <TopBar
        number="06"
        title="Budget Optimization"
        subtitle="AI-driven budget allocation for maximum ROI"
        right={
          <>
            <Pill>Total Budget: <strong style={{marginLeft:4}}>{data.allocation?.total_budget_display}</strong></Pill>
            <Pill>Constraints ▾</Pill>
            <Pill primary>Edit</Pill>
          </>
        }
      />

      <MintHeroInsight
        eyebrow={data.hero.eyebrow}
        headline={data.hero.headline}
        sub={data.hero.sub}
        cta={data.hero.cta}
        onCtaClick={() => setRevealed(true)}
      />

      {atlasInline && <AtlasInlineCallout narration={data.atlas}/>}

      <AllocationComparison
        allocation={data.allocation}
        onScoreOverride={onScoreOverride}
        revealed={revealed}
        onReveal={() => setRevealed(true)}
      />

      <ImpactStrip impact={data.impact} revealed={revealed}/>

      <FourMoves moves={data.moves}/>

      <NetSummary
        budgetDisplay={data.allocation?.total_budget_display}
        upliftDisplay={data.impact?.incremental_revenue?.value}
        impact={data.impact}
      />

      <BridgeCard
        toScreenNum="07"
        text="Want to stress-test this against a downturn, a competitor surge, or a 20% budget cut?"
        onClick={() => onNavigateToScreen && onNavigateToScreen(7)}
      />
    </>
  );
}

export default function BudgetOptimizationScreen({
  apiBase = "",
  atlasInline = false,
  onNavigateToScreen,
}) {
  const { data, loading, error, scoreOverride } = useBudgetOptimization({ apiBase });

  if (loading) return <LoadingState/>;
  if (error) return <ErrorState error={error}/>;
  return (
    <BudgetOptimizationBody
      data={data}
      onScoreOverride={scoreOverride}
      atlasInline={atlasInline}
      onNavigateToScreen={onNavigateToScreen}
    />
  );
}
