/**
 * TopBar — sits at the top of every screen's main column.
 *
 * Left:  big muted screen number, then title + subtitle
 * Right: date range pill and share pill (slots for custom pills)
 */
import React from "react";
import { tok } from "./tokens.js";

export function Pill({ children, primary, onClick }) {
  const style = {
    display: "inline-flex", alignItems: "center", gap: 8,
    padding: "8px 14px",
    background: primary ? tok.accent : tok.card,
    border: `1px solid ${primary ? tok.accent : tok.border}`,
    borderRadius: 8,
    fontSize: 12, fontWeight: 500,
    color: primary ? "#fff" : tok.text,
    cursor: onClick ? "pointer" : "default",
    fontFamily: tok.fontUi,
  };
  return <div style={style} onClick={onClick}>{children}</div>;
}

export default function TopBar({ number, title, subtitle, right }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "space-between",
      marginBottom: 24,
    }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 14 }}>
        <div style={{ fontSize: 20, fontWeight: 800, color: tok.text3 }}>{number}</div>
        <div>
          <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-.015em" }}>{title}</div>
          {subtitle && (
            <div style={{ fontSize: 12, color: tok.text2, marginTop: 2 }}>{subtitle}</div>
          )}
        </div>
      </div>
      {right && (
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {right}
        </div>
      )}
    </div>
  );
}
