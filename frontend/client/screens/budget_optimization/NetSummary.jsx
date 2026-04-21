/**
 * NetSummary — the closing summary card that reiterates the value
 * proposition in one line before the bridge to Screen 07.
 *
 * Uses mint gradient + same headline pattern as the hero, but smaller.
 */
import React from "react";
import { tok } from "../../design/tokens.js";

export default function NetSummary({ budgetDisplay, upliftDisplay, impact, onRunScenario }) {
  return (
    <div style={{
      background: `linear-gradient(135deg, ${tok.greenSoft}, #F0FCF6)`,
      border: `1px solid #CDECDD`,
      borderRadius: 12, padding: "22px 28px", marginBottom: 18,
      display: "flex", alignItems: "center", justifyContent: "space-between",
      gap: 24, fontFamily: tok.fontUi,
    }}>
      <div style={{ flex: 1 }}>
        <div style={{
          fontSize: 10, color: tok.greenDeep,
          textTransform: "uppercase", letterSpacing: "0.2em",
          fontWeight: 700, marginBottom: 6,
        }}>Net result</div>
        <div style={{
          fontFamily: tok.fontDisplay, fontSize: 22, fontWeight: 500,
          letterSpacing: "-.01em", lineHeight: 1.3,
        }}>
          Same <span style={{ color: tok.text2, fontStyle: "italic" }}>{budgetDisplay}</span> in.{" "}
          <span style={{
            color: tok.greenDeep, fontStyle: "italic", fontWeight: 600,
          }}>{upliftDisplay} more out.</span>
        </div>
        {impact && (
          <div style={{
            fontSize: 12, color: tok.text2, marginTop: 8,
          }}>
            ROI moves from{" "}
            <strong>
              {impact.projected_roi?.current_display || "current"} →{" "}
              {impact.projected_roi?.value}
            </strong>
            {impact.cac_improvement?.value && impact.cac_improvement.value !== "—" && (
              <> · CAC {impact.cac_improvement.value}</>
            )}
            {impact.payback_period?.value && impact.payback_period.value !== "—" && (
              <> · Payback {impact.payback_period.value}</>
            )}
          </div>
        )}
      </div>
      <button
        onClick={onRunScenario}
        style={{
          padding: "11px 20px",
          background: tok.greenDeep, color: "#fff",
          border: "none", borderRadius: 8,
          fontFamily: "inherit", fontSize: 12, fontWeight: 600,
          cursor: "pointer", whiteSpace: "nowrap",
        }}
      >Run as scenario →</button>
    </div>
  );
}
