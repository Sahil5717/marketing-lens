/**
 * AppShell — the 3-column Yield Intelligence frame.
 *
 * Layout:
 *   sidebar  (240px, dark) | main (flex) | atlas rail (360px, collapsible to 56px)
 *
 * Usage:
 *   <AppShell
 *     activeScreen={1}
 *     clientName="Acme Consumer Co."
 *     clientPeriod="Quarterly review · Q2 2024"
 *     atlas={<AtlasRail narration={...} />}
 *   >
 *     <ExecutiveSummaryScreen ... />
 *   </AppShell>
 *
 * The sidebar and atlas rail are separate components in this file so
 * each can be imported without dragging the whole shell in.
 */
import React, { useState } from "react";
import { tok } from "../design/tokens.js";

const NAV = [
  { num: "01", label: "Executive Summary" },
  { num: "02", label: "Data Foundation" },
  { num: "03", label: "Channel Performance" },
  { num: "04", label: "Campaign Deep Dive" },
  { num: "05", label: "Attribution" },
  { num: "06", label: "Optimization" },
  { num: "07", label: "Simulation" },
  { num: "08", label: "Plan Builder" },
  { num: "09", label: "Track & Monitor" },
  { num: "10", label: "Executive Report" },
];

export function Sidebar({ activeScreen = 1, clientName, clientPeriod, onNavigate }) {
  return (
    <aside style={{
      background: tok.sidebar,
      color: "#fff",
      padding: "24px 14px",
      position: "sticky",
      top: 0,
      height: "100vh",
      overflowY: "auto",
      fontFamily: tok.fontUi,
    }}>
      {/* Logo */}
      <div style={{
        display: "flex", alignItems: "center", gap: 10,
        padding: "0 10px 28px", fontWeight: 800, fontSize: 16, letterSpacing: "-.01em",
      }}>
        <div style={{
          width: 28, height: 28, borderRadius: 8,
          background: `linear-gradient(135deg, ${tok.accent}, #9D7DFF)`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 13,
        }}>YI</div>
        Yield Intelligence
      </div>

      {/* Nav items */}
      {NAV.map((item, idx) => {
        const num = idx + 1;
        const active = num === activeScreen;
        return (
          <div
            key={item.num}
            onClick={() => onNavigate && onNavigate(num)}
            style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "10px 12px", borderRadius: 8,
              color: active ? "#fff" : "#A8AEC9",
              background: active ? tok.accent : "transparent",
              cursor: "pointer", fontSize: 13,
              fontWeight: active ? 600 : 500,
              marginBottom: 2,
              transition: "all .15s",
            }}
            onMouseEnter={(e) => {
              if (!active) e.currentTarget.style.background = tok.sidebarHover;
              if (!active) e.currentTarget.style.color = "#fff";
            }}
            onMouseLeave={(e) => {
              if (!active) e.currentTarget.style.background = "transparent";
              if (!active) e.currentTarget.style.color = "#A8AEC9";
            }}
          >
            <span style={{
              display: "inline-block", width: 22, height: 22, borderRadius: 5,
              background: active ? "rgba(255,255,255,.18)" : "rgba(255,255,255,.08)",
              fontSize: 10, fontWeight: 700, textAlign: "center", lineHeight: "22px",
              flexShrink: 0,
            }}>{item.num}</span>
            {item.label}
          </div>
        );
      })}

      {/* Footer */}
      {clientName && (
        <div style={{
          marginTop: 24, padding: 12, borderRadius: 10,
          background: "rgba(255,255,255,.04)",
          fontSize: 11, color: "#A8AEC9",
        }}>
          <strong style={{ color: "#fff", display: "block", marginBottom: 2, fontSize: 12 }}>
            {clientName}
          </strong>
          {clientPeriod}
        </div>
      )}
    </aside>
  );
}

export default function AppShell({
  activeScreen,
  clientName,
  clientPeriod,
  atlas,
  onNavigate,
  children,
}) {
  const [atlasCollapsed, setAtlasCollapsed] = useState(false);

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: atlasCollapsed ? "240px 1fr 56px" : "240px 1fr 360px",
      minHeight: "100vh",
      background: tok.bg,
      color: tok.text,
      fontFamily: tok.fontUi,
      fontSize: 13,
      lineHeight: 1.5,
      transition: "grid-template-columns .35s cubic-bezier(.4,0,.2,1)",
      WebkitFontSmoothing: "antialiased",
    }}>
      <Sidebar
        activeScreen={activeScreen}
        clientName={clientName}
        clientPeriod={clientPeriod}
        onNavigate={onNavigate}
      />
      <main style={{ padding: "28px 36px 80px" }}>
        {children}
      </main>
      {atlas && React.cloneElement(atlas, {
        collapsed: atlasCollapsed,
        onToggle: () => setAtlasCollapsed(c => !c),
      })}
    </div>
  );
}
