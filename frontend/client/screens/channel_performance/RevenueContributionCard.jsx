/**
 * RevenueContributionCard — right-column card on Screen 03.
 *
 *   Revenue Contribution donut (center label = total)
 *   Legend: channel · pct · revenue
 *   Top Insight callout (purple-soft, highlights concentration)
 *
 * Data: /api/channel-performance .contribution and .top_insight
 */
import React from "react";
import { tok } from "../../design/tokens.js";
import Donut from "../budget_optimization/Donut.jsx";

export default function RevenueContributionCard({ contribution, topInsight }) {
  const slices = contribution?.slices || [];

  return (
    <div style={{
      background: tok.card, border: `1px solid ${tok.border}`,
      borderRadius: 12, padding: "18px 20px",
      fontFamily: tok.fontUi,
      display: "flex", flexDirection: "column", gap: 16,
    }}>
      <div>
        <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4 }}>Revenue Contribution</div>
        <div style={{
          fontSize: 10, color: tok.text3, fontWeight: 500,
          textTransform: "uppercase", letterSpacing: "0.05em",
        }}>By channel · this period</div>
      </div>

      {slices.length === 0 ? (
        <div style={{
          padding: "24px 0", textAlign: "center",
          color: tok.text3, fontSize: 12, fontStyle: "italic",
        }}>
          Revenue breakdown populates once performance data is loaded.
        </div>
      ) : (
        <>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <Donut
              slices={slices}
              centerLabel={contribution.total_display}
              centerSub="Total revenue"
              size={140}
            />
            <div style={{ flex: 1 }}>
              {slices.map((s, i) => (
                <div key={i} style={{
                  display: "flex", alignItems: "center", gap: 10,
                  padding: "5px 0", fontSize: 12,
                }}>
                  <span style={{
                    width: 8, height: 8, borderRadius: 2,
                    background: s.color, flexShrink: 0,
                  }}/>
                  <span style={{ flex: 1 }}>{s.channel}</span>
                  <span style={{
                    display: "flex", flexDirection: "column", alignItems: "flex-end",
                  }}>
                    <strong style={{ fontWeight: 700 }}>{s.percentage}%</strong>
                    <span style={{ color: tok.text3, fontSize: 11 }}>{s.revenue_display}</span>
                  </span>
                </div>
              ))}
            </div>
          </div>

          {topInsight && (
            <div style={{
              background: tok.accentSoft,
              borderLeft: `3px solid ${tok.accent}`,
              borderRadius: 6, padding: "12px 16px",
              marginTop: 4,
            }}>
              <div style={{
                fontSize: 10, color: tok.accentDeep,
                textTransform: "uppercase", letterSpacing: "0.12em",
                fontWeight: 700, marginBottom: 4,
              }}>Top Insight</div>
              <div style={{ fontSize: 12.5, fontWeight: 600, color: tok.text, lineHeight: 1.4 }}>
                {topInsight.headline}
              </div>
              {topInsight.detail && (
                <div style={{ fontSize: 11, color: tok.text2, marginTop: 6, lineHeight: 1.5 }}>
                  {topInsight.detail}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
