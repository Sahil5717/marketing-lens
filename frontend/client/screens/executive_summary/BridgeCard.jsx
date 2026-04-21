/**
 * BridgeCard — the purple-bordered transition card at the bottom of
 * each screen that narrates the handoff to the next screen.
 *
 * Props:
 *   - toScreenNum: string ("02")
 *   - text: short headline that sets up the next screen
 *   - onClick: navigate to next screen
 */
import React from "react";
import { tok } from "../../design/tokens.js";

export default function BridgeCard({ toScreenNum, text, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        marginTop: 8,
        padding: "22px 28px",
        background: `linear-gradient(135deg, #fff, #FAFBFE)`,
        border: `1px solid ${tok.border}`,
        borderLeft: `3px solid ${tok.accent}`,
        borderRadius: 10,
        display: "flex", alignItems: "center", justifyContent: "space-between",
        gap: 24, cursor: "pointer", transition: "all .25s",
        fontFamily: tok.fontUi,
      }}
      onMouseEnter={e => {
        e.currentTarget.style.borderLeftColor = tok.accentDeep;
        e.currentTarget.style.boxShadow = "0 8px 20px rgba(124,92,255,.08)";
        e.currentTarget.style.transform = "translateX(2px)";
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderLeftColor = tok.accent;
        e.currentTarget.style.boxShadow = "none";
        e.currentTarget.style.transform = "none";
      }}
    >
      <div>
        <div style={{
          fontSize: 10, color: tok.accent,
          textTransform: "uppercase", letterSpacing: "0.2em",
          fontWeight: 700, marginBottom: 6,
        }}>Continue · Screen {toScreenNum}</div>
        <div style={{
          fontFamily: tok.fontDisplay, fontSize: 17, fontWeight: 500,
          letterSpacing: "-.01em", lineHeight: 1.3, maxWidth: 560,
          color: tok.text,
        }}>{text}</div>
      </div>
      <div style={{
        fontFamily: tok.fontDisplay, fontSize: 28, color: tok.accent,
        fontStyle: "italic", fontWeight: 500,
      }}>→</div>
    </div>
  );
}
