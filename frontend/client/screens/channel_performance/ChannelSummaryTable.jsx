/**
 * ChannelSummaryTable — the per-channel KPI breakdown table.
 *
 * Columns: Channel · Spend · Revenue · ROI · Conversions · Trend
 * Data: /api/channel-performance .summary
 */
import React from "react";
import { tok } from "../../design/tokens.js";

function TrendChip({ direction, pct }) {
  if (!pct) {
    return <span style={{ color: tok.text3 }}>—</span>;
  }
  const isUp = direction === "up";
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      fontSize: 11, fontWeight: 600,
      color: isUp ? tok.green : tok.red,
    }}>
      {isUp ? "↗" : "↘"} {Math.abs(pct).toFixed(1)}%
    </span>
  );
}

export default function ChannelSummaryTable({ rows = [] }) {
  return (
    <div style={{
      background: tok.card, border: `1px solid ${tok.border}`,
      borderRadius: 12, padding: "18px 20px",
      fontFamily: tok.fontUi,
    }}>
      <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4 }}>Channel Summary</div>
      <div style={{
        fontSize: 10, color: tok.text3, fontWeight: 500,
        textTransform: "uppercase", letterSpacing: "0.05em",
        marginBottom: 14,
      }}>Per-channel performance</div>

      {rows.length === 0 ? (
        <div style={{
          padding: "24px 0", textAlign: "center",
          color: tok.text3, fontSize: 12, fontStyle: "italic",
        }}>
          Upload performance data to see per-channel KPIs.
        </div>
      ) : (
        <table style={{
          width: "100%", borderCollapse: "collapse", fontSize: 12,
        }}>
          <thead>
            <tr style={{
              textAlign: "left",
              color: tok.text3, fontWeight: 600,
              fontSize: 10, textTransform: "uppercase", letterSpacing: "0.05em",
            }}>
              <th style={{ padding: "10px 8px", fontWeight: 600 }}>Channel</th>
              <th style={{ padding: "10px 8px", textAlign: "right", fontWeight: 600 }}>Spend</th>
              <th style={{ padding: "10px 8px", textAlign: "right", fontWeight: 600 }}>Revenue</th>
              <th style={{ padding: "10px 8px", textAlign: "right", fontWeight: 600 }}>ROI</th>
              <th style={{ padding: "10px 8px", textAlign: "right", fontWeight: 600 }}>Conversions</th>
              <th style={{ padding: "10px 8px", textAlign: "right", fontWeight: 600 }}>Trend</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} style={{ borderTop: `1px solid ${tok.border}` }}>
                <td style={{ padding: "12px 8px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{
                      width: 8, height: 8, borderRadius: 2,
                      background: row.color, flexShrink: 0,
                    }}/>
                    <span style={{ fontWeight: 500 }}>{row.channel}</span>
                  </div>
                </td>
                <td style={{ padding: "12px 8px", textAlign: "right" }}>{row.spend_display}</td>
                <td style={{ padding: "12px 8px", textAlign: "right", fontWeight: 600 }}>
                  {row.revenue_display}
                </td>
                <td style={{ padding: "12px 8px", textAlign: "right" }}>
                  <span style={{
                    fontFamily: tok.fontDisplay, fontStyle: "italic", fontWeight: 600,
                    color: row.roi >= 3 ? tok.greenDeep : row.roi >= 1.5 ? tok.text : tok.red,
                  }}>{row.roi_display}</span>
                </td>
                <td style={{ padding: "12px 8px", textAlign: "right" }}>
                  {row.conversions_display}
                </td>
                <td style={{ padding: "12px 8px", textAlign: "right" }}>
                  <TrendChip direction={row.trend_direction} pct={row.trend_pct}/>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
