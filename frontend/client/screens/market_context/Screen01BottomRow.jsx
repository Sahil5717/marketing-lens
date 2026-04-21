/**
 * Screen 01 bottom row — Market Context + Upcoming Peak Windows.
 *
 * Single drop-in component for the Screen 01 rebuild. Pass the same
 * context (category, regions) you use elsewhere on the screen; both
 * panels render from one /api/market-context call.
 *
 * Layout mirrors the HTML reference:
 *   grid-template-columns: 1.4fr 1fr; gap: 14px;
 *
 * Usage:
 *   <Screen01BottomRow
 *     asOf="2024-08-01"
 *     category="FMCG"
 *     regions={["Mumbai", "Delhi"]}
 *   />
 */
import React from "react";
import MarketContextPanel from "./MarketContextPanel.jsx";
import UpcomingPeakWindowsPanel from "./UpcomingPeakWindowsPanel.jsx";
import { useMarketContext } from "./useMarketContext.js";

export default function Screen01BottomRow({
  asOf,
  category,
  regions,
  lookaheadDays,
  lookbackMonths,
  peakLimit,
  apiBase,
}) {
  const state = useMarketContext({
    asOf, category, regions,
    lookaheadDays, lookbackMonths, peakLimit, apiBase,
  });

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "1.4fr 1fr",
      gap: 14,
      marginBottom: 18,
    }}>
      <MarketContextPanel {...state} />
      <UpcomingPeakWindowsPanel {...state} />
    </div>
  );
}
