/**
 * ExecutiveSummaryScreen — Screen 01 root composer.
 *
 * Layout (top → bottom):
 *   TopBar
 *   HeroInsight           (dark gradient, single decisive sentence)
 *   AtlasInlineCallout    (only rendered when Atlas rail is collapsed)
 *   KpiStrip              (5 cells)
 *   PillarsPanel          (3 pillars + total)
 *   OpportunitiesAndActions
 *   Screen01BottomRow     (Market Context + Upcoming Peak Windows)
 *   BridgeCard            (→ Screen 02)
 *
 * Data:
 *   - /api/executive-summary for the top 4 blocks + Atlas rail narration
 *   - /api/market-context for the bottom row (self-fetches inside)
 */
import React from "react";
import TopBar, { Pill } from "../../design/TopBar.jsx";
import AtlasRail, { AtlasInlineCallout } from "../../design/AtlasRail.jsx";
import HeroInsight from "./HeroInsight.jsx";
import KpiStrip from "./KpiStrip.jsx";
import PillarsPanel from "./PillarsPanel.jsx";
import OpportunitiesAndActions from "./OpportunitiesAndActions.jsx";
import BridgeCard from "./BridgeCard.jsx";
import Screen01BottomRow from "../market_context/Screen01BottomRow.jsx";
import { useExecutiveSummary } from "./useExecutiveSummary.js";
import { tok } from "../../design/tokens.js";

const LoadingState = () => (
  <div style={{
    padding: "80px 0", textAlign: "center",
    color: tok.text3, fontSize: 13, fontFamily: tok.fontUi,
  }}>Loading executive summary…</div>
);

const ErrorState = ({ error, onRetry }) => (
  <div style={{
    padding: "40px 32px", background: tok.card,
    border: `1px solid ${tok.border}`, borderLeft: `3px solid ${tok.red}`,
    borderRadius: 10, fontFamily: tok.fontUi, color: tok.text,
  }}>
    <div style={{ fontWeight: 700, marginBottom: 6 }}>Couldn't load the executive summary.</div>
    <div style={{ fontSize: 12, color: tok.text2, marginBottom: 12 }}>{error}</div>
    {onRetry && (
      <button onClick={onRetry} style={{
        padding: "8px 14px", background: tok.accent, color: "#fff",
        border: "none", borderRadius: 6, fontFamily: "inherit",
        fontSize: 12, fontWeight: 600, cursor: "pointer",
      }}>Retry</button>
    )}
  </div>
);

/**
 * Pure screen body — just the main column content, no shell.
 * Use this when embedding Screen 01 inside an existing app shell.
 */
export function ExecutiveSummaryBody({
  data,
  marketContextProps = {},
  atlasInline = false,    // true when rail is collapsed
  onNavigateToScreen,
}) {
  if (!data) return <LoadingState />;

  return (
    <>
      <TopBar
        number="01"
        title="Executive Summary"
        subtitle="Decision Command Center"
        right={
          <>
            <Pill>May 1 – May 31, 2024 ▾</Pill>
            <Pill>⇪ Share</Pill>
          </>
        }
      />

      <HeroInsight
        eyebrow={data.hero.eyebrow}
        headline={data.hero.headline}
        sub={data.hero.sub}
        cta={data.hero.cta}
      />

      {atlasInline && <AtlasInlineCallout narration={data.atlas} />}

      <KpiStrip kpis={data.kpis} />

      <PillarsPanel data={data.pillars} />

      <OpportunitiesAndActions
        opportunities={data.opportunities}
        topActions={data.top_actions}
      />

      <Screen01BottomRow {...marketContextProps} />

      <BridgeCard
        toScreenNum="02"
        text="Before we tell you how — let's check whether the data underneath this is trustworthy."
        onClick={() => onNavigateToScreen && onNavigateToScreen(2)}
      />
    </>
  );
}

/**
 * Full screen — fetches its own data, renders everything including
 * loading / error states. This is the default export.
 */
export default function ExecutiveSummaryScreen({
  apiBase = "",
  marketContextProps = {},
  atlasInline = false,
  onNavigateToScreen,
}) {
  const { data, loading, error } = useExecutiveSummary({ apiBase });

  if (loading) return <LoadingState />;
  if (error) return <ErrorState error={error} />;
  return (
    <ExecutiveSummaryBody
      data={data}
      marketContextProps={{ apiBase, ...marketContextProps }}
      atlasInline={atlasInline}
      onNavigateToScreen={onNavigateToScreen}
    />
  );
}
