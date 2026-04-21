/**
 * ChannelPerformanceScreen — Screen 03 root composer.
 *
 * Layout:
 *   TopBar
 *   KpiStrip (reused from exec summary)
 *   Main two-column row:
 *     Left  (1.6fr):  ChannelSummaryTable
 *     Right (1fr):    RevenueContributionCard (donut + top insight)
 *   ChannelShiftPanel (full-width, plan v2 addition)
 *   BridgeCard → Screen 04
 */
import React from "react";
import TopBar, { Pill } from "../../design/TopBar.jsx";
import { AtlasInlineCallout } from "../../design/AtlasRail.jsx";
import KpiStrip from "../executive_summary/KpiStrip.jsx";
import BridgeCard from "../executive_summary/BridgeCard.jsx";
import ChannelSummaryTable from "./ChannelSummaryTable.jsx";
import RevenueContributionCard from "./RevenueContributionCard.jsx";
import ChannelShiftPanel from "./ChannelShiftPanel.jsx";
import { useChannelPerformance } from "./useChannelPerformance.js";
import { tok } from "../../design/tokens.js";

const LoadingState = () => (
  <div style={{
    padding: "80px 0", textAlign: "center",
    color: tok.text3, fontSize: 13, fontFamily: tok.fontUi,
  }}>Loading channel performance…</div>
);

const ErrorState = ({ error }) => (
  <div style={{
    padding: "40px 32px", background: tok.card,
    border: `1px solid ${tok.border}`, borderLeft: `3px solid ${tok.red}`,
    borderRadius: 10, fontFamily: tok.fontUi,
  }}>
    <div style={{ fontWeight: 700, marginBottom: 6 }}>Couldn't load channel performance.</div>
    <div style={{ fontSize: 12, color: tok.text2 }}>{error}</div>
  </div>
);

export function ChannelPerformanceBody({ data, atlasInline = false, onNavigateToScreen }) {
  if (!data) return <LoadingState/>;

  return (
    <>
      <TopBar
        number="03"
        title="Channel Performance"
        subtitle="Understand what's driving results"
        right={
          <>
            <Pill>May 1 – May 31, 2024 ▾</Pill>
            <Pill>Compare: Apr ▾</Pill>
            <Pill primary>Export</Pill>
          </>
        }
      />

      {atlasInline && <AtlasInlineCallout narration={data.atlas}/>}

      <KpiStrip kpis={data.kpis}/>

      <div style={{
        display: "grid", gridTemplateColumns: "1.6fr 1fr",
        gap: 14, marginBottom: 18,
      }}>
        <ChannelSummaryTable rows={data.summary}/>
        <RevenueContributionCard
          contribution={data.contribution}
          topInsight={data.top_insight}
        />
      </div>

      <ChannelShiftPanel shift={data.channel_shift}/>

      <BridgeCard
        toScreenNum="04"
        text="Now let's go one level deeper — which specific campaigns drove these channel numbers?"
        onClick={() => onNavigateToScreen && onNavigateToScreen(4)}
      />
    </>
  );
}

export default function ChannelPerformanceScreen({
  apiBase = "",
  engagementId = "default",
  lookbackMonths = 24,
  atlasInline = false,
  onNavigateToScreen,
}) {
  const { data, loading, error } = useChannelPerformance({
    apiBase, lookbackMonths, engagementId,
  });
  if (loading) return <LoadingState/>;
  if (error) return <ErrorState error={error}/>;
  return (
    <ChannelPerformanceBody
      data={data}
      atlasInline={atlasInline}
      onNavigateToScreen={onNavigateToScreen}
    />
  );
}
