/**
 * MintHeroInsight — hero variant for Screen 06 and other "same input,
 * better output" story moments. Differs from HeroInsight in:
 *   - eyebrow accent is mint, not amber
 *   - headline emphasises "same [budget]" in muted grey and "[gain]" in mint
 *
 * Props:
 *   - headline: { prefix, same, middle, gain, suffix }
 *       same renders muted grey italic; gain renders mint italic.
 */
import React from "react";
import { tok } from "../../design/tokens.js";

export default function MintHeroInsight({ eyebrow, headline, sub, cta, onCtaClick }) {
  return (
    <div style={{
      background: `linear-gradient(135deg, ${tok.heroFrom} 0%, ${tok.heroTo} 100%)`,
      borderRadius: 14, padding: "28px 32px", marginBottom: 18,
      display: "grid", gridTemplateColumns: "1fr auto", gap: 32,
      alignItems: "center", position: "relative", overflow: "hidden",
      fontFamily: tok.fontUi,
    }}>
      <div style={{
        position: "absolute", top: -40, right: -40, width: 240, height: 240,
        borderRadius: "50%",
        background: "radial-gradient(circle, rgba(123,224,188,.18) 0%, transparent 70%)",
        pointerEvents: "none",
      }}/>

      <div style={{ position: "relative", zIndex: 1 }}>
        <div style={{
          fontSize: 10, color: tok.heroGain,
          textTransform: "uppercase", letterSpacing: "0.22em",
          fontWeight: 700, marginBottom: 14,
          display: "flex", alignItems: "center", gap: 10,
        }}>
          <span style={{ width: 24, height: 1, background: tok.heroGain }}/>
          {eyebrow}
        </div>

        <div style={{
          fontFamily: tok.fontDisplay, fontSize: 32, fontWeight: 500,
          lineHeight: 1.15, color: "#fff", letterSpacing: "-.02em", maxWidth: 640,
        }}>
          {headline.prefix && <span>{headline.prefix} </span>}
          {headline.same && (
            <span style={{ color: "#B5BAD4", fontStyle: "italic" }}>{headline.same}</span>
          )}
          {headline.middle && <span> {headline.middle} </span>}
          {headline.gain && (
            <span style={{
              color: tok.heroGain, fontStyle: "italic", fontWeight: 600,
            }}>{headline.gain}</span>
          )}
          {headline.suffix}
        </div>

        {sub && (
          <div style={{
            fontSize: 13, color: "#B5BAD4",
            marginTop: 12, maxWidth: 560, lineHeight: 1.55,
          }}>{sub}</div>
        )}
      </div>

      {cta && (
        <div style={{ position: "relative", zIndex: 1, textAlign: "right" }}>
          <button
            onClick={onCtaClick}
            style={{
              padding: "11px 20px", background: "rgba(255,255,255,.1)",
              color: "#fff", border: "1px solid rgba(255,255,255,.18)",
              borderRadius: 8, fontSize: 12, fontWeight: 600,
              cursor: onCtaClick ? "pointer" : "default",
              fontFamily: tok.fontUi, transition: "all .2s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "rgba(255,255,255,.18)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "rgba(255,255,255,.1)";
            }}
          >{cta.label}</button>
          {cta.meta && (
            <div style={{
              fontSize: 10, color: "#8C92AC",
              textTransform: "uppercase", letterSpacing: "0.15em",
              marginTop: 10, fontWeight: 600,
            }}>{cta.meta}</div>
          )}
        </div>
      )}
    </div>
  );
}
