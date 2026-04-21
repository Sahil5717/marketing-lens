/**
 * ImpactStrip — 4-cell summary metrics row sitting below the allocation
 * comparison. Greys out when the allocation hasn't been revealed yet, to
 * preserve the earned-reveal narrative.
 *
 * Data: from /api/budget-optimization .impact
 */
import React from "react";
import { tok } from "../../design/tokens.js";

function Cell({ label, value, sub, subColor, muted }) {
  return (
    <div style={{
      padding: "16px 18px",
      opacity: muted ? 0.45 : 1,
      transition: "opacity .25s",
    }}>
      <div style={{
        fontSize: 11, color: tok.text2, fontWeight: 500,
        textTransform: "uppercase", letterSpacing: "0.04em",
        marginBottom: 8,
      }}>{label}</div>
      <div style={{
        fontSize: 22, fontWeight: 800, letterSpacing: "-.02em",
        lineHeight: 1.1, marginBottom: 6,
        color: /^\+|gain/.test(value) ? tok.greenDeep : tok.text,
      }}>{value}</div>
      {sub && (
        <div style={{
          fontSize: 11, fontWeight: 600,
          color: subColor || tok.text3,
        }}>{sub}</div>
      )}
    </div>
  );
}

export default function ImpactStrip({ impact, revealed = true, onViewSimulation }) {
  if (!impact) return null;
  const muted = !revealed;

  return (
    <div style={{
      background: tok.card, border: `1px solid ${tok.border}`,
      borderRadius: 12, marginBottom: 18,
      display: "grid",
      // 4 cells × 1fr, 3 dividers × auto, 1 button × auto = 8 tracks
      gridTemplateColumns: "1fr auto 1fr auto 1fr auto 1fr auto",
      alignItems: "center",
      fontFamily: tok.fontUi,
    }}>
      <Cell
        label="Projected ROI"
        value={impact.projected_roi.value}
        sub={impact.projected_roi.delta}
        subColor={impact.projected_roi.delta?.startsWith("▲") ? tok.green : tok.text3}
        muted={muted}
      />
      <div style={{ borderLeft: `1px solid ${tok.border}`, height: 60, alignSelf: "center" }}/>
      <Cell
        label="Incremental Revenue"
        value={impact.incremental_revenue.value}
        sub={impact.incremental_revenue.delta}
        muted={muted}
      />
      <div style={{ borderLeft: `1px solid ${tok.border}`, height: 60, alignSelf: "center" }}/>
      <Cell
        label="CAC Improvement"
        value={impact.cac_improvement.value}
        sub={impact.cac_improvement.delta}
        subColor={tok.green}
        muted={muted}
      />
      <div style={{ borderLeft: `1px solid ${tok.border}`, height: 60, alignSelf: "center" }}/>
      <Cell
        label="Payback Period"
        value={impact.payback_period.value}
        sub={impact.payback_period.delta}
        muted={muted}
      />
      <button
        onClick={onViewSimulation}
        disabled={muted}
        style={{
          margin: "0 20px", padding: "10px 18px",
          background: muted ? tok.border : tok.accent,
          color: "#fff", border: "none", borderRadius: 8,
          fontFamily: "inherit", fontSize: 12, fontWeight: 600,
          cursor: muted ? "not-allowed" : "pointer",
          whiteSpace: "nowrap",
          transition: "background .2s",
        }}
      >View Simulation →</button>
    </div>
  );
}
