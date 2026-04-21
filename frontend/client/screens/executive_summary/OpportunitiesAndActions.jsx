/**
 * OpportunitiesAndActions — the two-column row below the pillars panel.
 *
 *   Left:  Recovery Opportunities (3 coloured tiles)
 *   Right: Top Actions (prioritised list with inline "Why?" reveals)
 *
 * The "Why?" reveal is the reusable Atlas-reasoning pattern from the HTML
 * reference — click opens a gold-soft callout with reasoning.
 */
import React, { useState } from "react";
import { tok, atlasCalloutStyle } from "../../design/tokens.js";

function Opportunity({ opp }) {
  return (
    <div style={{
      padding: 14, borderRadius: 10,
      background: tok.greenSoft,
      cursor: "pointer", transition: "all .2s",
      border: "1px solid transparent",
    }}
      onMouseEnter={e => {
        e.currentTarget.style.borderColor = tok.green;
        e.currentTarget.style.transform = "translateY(-1px)";
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor = "transparent";
        e.currentTarget.style.transform = "none";
      }}
    >
      <div style={{
        fontFamily: "'JetBrains Mono', monospace", fontWeight: 700,
        color: tok.green, fontSize: 14, marginBottom: 8,
      }}>{opp.icon}</div>
      <div style={{
        fontFamily: tok.fontDisplay, fontSize: 20, fontWeight: 600,
        color: tok.greenDeep, fontStyle: "italic",
        marginBottom: 4, letterSpacing: "-.02em",
      }}>{opp.display}</div>
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4, color: tok.text }}>
        {opp.name}
      </div>
      <div style={{ fontSize: 10, color: tok.text2, lineHeight: 1.45 }}>
        {opp.detail}
      </div>
    </div>
  );
}

function ActionRow({ action, isOpen, onToggle }) {
  return (
    <>
      <div style={{
        display: "flex", alignItems: "center", gap: 12,
        padding: "12px 0",
        borderBottom: `1px solid ${tok.border}`,
      }}>
        <div style={{
          width: 24, height: 24, borderRadius: 6,
          background: tok.accentSoft, color: tok.accent,
          fontWeight: 700, fontSize: 11,
          display: "flex", alignItems: "center", justifyContent: "center",
          flexShrink: 0,
        }}>{action.num}</div>
        <div style={{ flex: 1, fontSize: 12, fontWeight: 500 }}>{action.text}</div>
        <div style={{
          fontSize: 11, color: tok.green, fontWeight: 700,
          fontFamily: tok.fontDisplay, fontStyle: "italic",
        }}>{action.impact}</div>
        <div
          onClick={onToggle}
          style={{
            fontSize: 10, fontWeight: 600, color: tok.atlasDeep,
            background: tok.atlasSoft,
            padding: "4px 10px", borderRadius: 5,
            cursor: "pointer", border: "1px solid #F2D89A",
            display: "flex", alignItems: "center", gap: 4,
            transition: "all .2s",
            userSelect: "none",
          }}
          onMouseEnter={e => {
            e.currentTarget.style.background = tok.atlas;
            e.currentTarget.style.color = "#fff";
            e.currentTarget.style.borderColor = tok.atlas;
          }}
          onMouseLeave={e => {
            e.currentTarget.style.background = tok.atlasSoft;
            e.currentTarget.style.color = tok.atlasDeep;
            e.currentTarget.style.borderColor = "#F2D89A";
          }}
        >
          Why? <span style={{
            display: "inline-block",
            transform: isOpen ? "rotate(180deg)" : "none",
            transition: "transform .25s",
          }}>▾</span>
        </div>
      </div>

      {/* Reveal */}
      {isOpen && (
        <div style={{ padding: "14px 0 14px 36px", borderBottom: `1px solid ${tok.border}` }}>
          <div style={atlasCalloutStyle}>
            <div style={{
              fontFamily: tok.fontDisplay, fontStyle: "italic", fontWeight: 600,
              color: tok.atlasDeep, marginBottom: 6,
              fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em",
            }}>{action.why?.who || "Atlas · Reasoning"}</div>
            {action.why?.text}
          </div>
        </div>
      )}
    </>
  );
}

export default function OpportunitiesAndActions({ opportunities = [], topActions = [] }) {
  const [openIdx, setOpenIdx] = useState(null);

  return (
    <div style={{
      display: "grid", gridTemplateColumns: "1.5fr 1fr",
      gap: 14, marginBottom: 18,
    }}>
      {/* Left: Recovery Opportunities */}
      <div style={{
        background: tok.card, border: `1px solid ${tok.border}`,
        borderRadius: 12, padding: "18px 20px",
      }}>
        <div style={{
          fontSize: 13, fontWeight: 700, marginBottom: 4,
          display: "flex", alignItems: "center", gap: 8,
        }}>Recovery Opportunities</div>
        <div style={{
          fontSize: 10, color: tok.green, fontWeight: 500,
          textTransform: "uppercase", letterSpacing: "0.05em",
          marginBottom: 14,
        }}>Potential Impact · Within this quarter</div>
        <div style={{
          display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10,
        }}>
          {opportunities.length === 0 ? (
            <div style={{
              gridColumn: "1 / -1",
              padding: "24px 0", textAlign: "center",
              color: tok.text3, fontSize: 12, fontStyle: "italic",
            }}>
              Opportunities populate once the three-pillar engine has run on uploaded data.
            </div>
          ) : opportunities.map((o, i) => <Opportunity key={i} opp={o}/>)}
        </div>
      </div>

      {/* Right: Top Actions */}
      <div style={{
        background: tok.card, border: `1px solid ${tok.border}`,
        borderRadius: 12, padding: "18px 20px",
      }}>
        <div style={{
          fontSize: 13, fontWeight: 700, marginBottom: 4,
          display: "flex", alignItems: "center", gap: 8,
        }}>
          Top Actions
          <span style={{ fontWeight: 500, color: tok.text3, fontSize: 11 }}>(Prioritized)</span>
        </div>
        <div style={{
          fontSize: 10, color: tok.text3, fontWeight: 500,
          textTransform: "uppercase", letterSpacing: "0.05em",
          marginBottom: 14,
        }}>By marginal impact</div>

        {topActions.length === 0 ? (
          <div style={{
            padding: "24px 0", color: tok.text3, fontSize: 12, fontStyle: "italic",
          }}>
            Actions populate once the optimizer has run.
          </div>
        ) : topActions.map((action, i) => (
          <ActionRow
            key={i}
            action={action}
            isOpen={openIdx === i}
            onToggle={() => setOpenIdx(openIdx === i ? null : i)}
          />
        ))}
      </div>
    </div>
  );
}
