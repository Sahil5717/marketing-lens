/**
 * KpiStrip — row of KPI cards.
 *
 * Props:
 *   - kpis: Array<{ label, value, delta }>
 *     delta is an optional string like "▲ 12.4% vs Apr"
 *     (the component doesn't compute direction — caller formats the string).
 */
import React from "react";
import { tok } from "../../design/tokens.js";

export default function KpiStrip({ kpis = [] }) {
  if (!kpis.length) return null;
  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: `repeat(${kpis.length}, 1fr)`,
      gap: 14,
      marginBottom: 18,
    }}>
      {kpis.map((kpi, i) => (
        <div key={i} style={{
          background: tok.card,
          border: `1px solid ${tok.border}`,
          borderRadius: 12,
          padding: "16px 18px",
          fontFamily: tok.fontUi,
        }}>
          <div style={{
            fontSize: 11, color: tok.text2, fontWeight: 500,
            textTransform: "uppercase", letterSpacing: "0.04em",
            marginBottom: 8,
          }}>{kpi.label}</div>
          <div style={{
            fontSize: 22, fontWeight: 800, letterSpacing: "-.02em",
            lineHeight: 1.1, marginBottom: 6, color: tok.text,
          }}>{kpi.value}</div>
          {kpi.delta && (
            <div style={{
              fontSize: 11, fontWeight: 600,
              color: kpi.delta.startsWith("▲") ? tok.green
                   : kpi.delta.startsWith("▼") ? tok.red
                   : tok.text3,
            }}>{kpi.delta}</div>
          )}
        </div>
      ))}
    </div>
  );
}
