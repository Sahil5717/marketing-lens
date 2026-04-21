/**
 * PillarsPanel — the three-pillar cost-of-bad-allocation panel.
 *
 * Lifts the "Cost of Bad Allocation" card from the HTML reference: a
 * header with panel title + total, then three coloured tiles
 * (red-soft / amber-soft / purple-soft) with roman numerals, amounts,
 * descriptions, and a recoverability tag.
 *
 * Data from: /api/executive-summary .pillars
 */
import React from "react";
import { tok } from "../../design/tokens.js";

const PILLAR_THEMES = {
  leak: {
    gradFrom: "#FEF1EF", gradTo: "#FEE9E9",
    border: "#FBD5D0", amount: "#C04020",
  },
  drop: {
    gradFrom: "#FEF8E7", gradTo: "#FEF3D7",
    border: "#F9E2A6", amount: "#A56A00",
  },
  avoid: {
    gradFrom: "#F4ECFF", gradTo: "#EFE2FF",
    border: "#DEC9F8", amount: "#7340C0",
  },
};

function Pillar({ pillar }) {
  const theme = PILLAR_THEMES[pillar.id] || PILLAR_THEMES.leak;
  return (
    <div style={{
      padding: "18px 20px",
      borderRadius: 10,
      background: `linear-gradient(135deg, ${theme.gradFrom}, ${theme.gradTo})`,
      border: `1px solid ${theme.border}`,
      cursor: "pointer",
      transition: "all .25s",
    }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = "translateY(-2px)";
        e.currentTarget.style.boxShadow = "0 8px 20px rgba(15,21,53,.06)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = "none";
        e.currentTarget.style.boxShadow = "none";
      }}
    >
      <div style={{
        fontFamily: tok.fontDisplay, fontSize: 11, color: tok.text3,
        fontStyle: "italic", marginBottom: 10, fontWeight: 500,
      }}>{pillar.roman}</div>
      <div style={{
        fontFamily: tok.fontDisplay, fontSize: 16, fontWeight: 600,
        letterSpacing: "-.01em", marginBottom: 8, color: tok.text,
      }}>{pillar.name}</div>
      <div style={{
        fontFamily: tok.fontDisplay, fontSize: 30, fontWeight: 600,
        letterSpacing: "-.02em", lineHeight: 1, fontStyle: "italic",
        marginBottom: 8, color: theme.amount,
      }}>{pillar.display}</div>
      <div style={{
        fontSize: 11, color: tok.text2, lineHeight: 1.5, marginBottom: 10,
      }}>{pillar.description}</div>
      <div style={{
        fontSize: 10, fontWeight: 600,
        textTransform: "uppercase", letterSpacing: "0.05em",
        color: theme.amount,
      }}>{pillar.tag}</div>
    </div>
  );
}

export default function PillarsPanel({ data }) {
  if (!data) return null;
  const { total_cost, pillars } = data;

  return (
    <div style={{
      background: tok.card, border: `1px solid ${tok.border}`,
      borderRadius: 12, padding: "22px 24px", marginBottom: 18,
      fontFamily: tok.fontUi,
    }}>
      {/* Head */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        marginBottom: 18,
      }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
          <div style={{
            fontFamily: tok.fontDisplay, fontSize: 18, fontWeight: 600,
            letterSpacing: "-.01em", color: tok.text,
          }}>The Cost of Bad Allocation</div>
          <div style={{
            fontSize: 10, color: tok.text3,
            textTransform: "uppercase", letterSpacing: "0.15em", fontWeight: 600,
          }}>Three pillars · Quantified</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{
            fontSize: 10, color: tok.text3,
            textTransform: "uppercase", letterSpacing: "0.12em",
            fontWeight: 600, marginBottom: 2,
          }}>{total_cost.label}</div>
          <div style={{
            fontFamily: tok.fontDisplay, fontSize: 24, fontWeight: 600,
            letterSpacing: "-.02em", color: tok.red, fontStyle: "italic",
          }}>{total_cost.display}</div>
        </div>
      </div>

      {/* Three pillars */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14,
      }}>
        {pillars.map(p => <Pillar key={p.id} pillar={p}/>)}
      </div>
    </div>
  );
}
