/**
 * HeroInsight — dark gradient card that frames the screen's single
 * most important number. Used at the top of Screen 01 and 06.
 *
 * Props:
 *   - eyebrow:  short uppercase label ("Where you stand this quarter")
 *   - headline: { prefix, loss, middle, gain, suffix }
 *       prefix/middle/suffix render as white Fraunces italic-ish copy;
 *       loss renders in coral italic, gain renders in mint italic.
 *   - sub:      muted body copy underneath
 *   - cta:      { label, meta } — right-side CTA with confidence meta
 */
import React from "react";
import { tok } from "../../design/tokens.js";

export default function HeroInsight({ eyebrow, headline, sub, cta, onCtaClick }) {
  return (
    <div style={{
      background: `linear-gradient(135deg, ${tok.heroFrom} 0%, ${tok.heroTo} 100%)`,
      borderRadius: 14,
      padding: "28px 32px",
      marginBottom: 18,
      display: "grid",
      gridTemplateColumns: "1fr auto",
      gap: 32,
      alignItems: "center",
      position: "relative",
      overflow: "hidden",
      fontFamily: tok.fontUi,
    }}>
      {/* Decorative radial gradient blobs */}
      <div style={{
        position: "absolute", top: -40, right: -40, width: 240, height: 240,
        borderRadius: "50%",
        background: `radial-gradient(circle, rgba(124,92,255,.18) 0%, transparent 70%)`,
        pointerEvents: "none",
      }}/>
      <div style={{
        position: "absolute", bottom: -30, left: -30, width: 180, height: 180,
        borderRadius: "50%",
        background: `radial-gradient(circle, rgba(232,193,106,.08) 0%, transparent 70%)`,
        pointerEvents: "none",
      }}/>

      <div style={{ position: "relative", zIndex: 1 }}>
        {/* Eyebrow */}
        <div style={{
          fontSize: 10, color: tok.heroEyebrow,
          textTransform: "uppercase", letterSpacing: "0.22em",
          fontWeight: 700, marginBottom: 14,
          display: "flex", alignItems: "center", gap: 10,
        }}>
          <span style={{ width: 24, height: 1, background: tok.heroEyebrow }}/>
          {eyebrow}
        </div>

        {/* Headline */}
        <div style={{
          fontFamily: tok.fontDisplay, fontSize: 32, fontWeight: 500,
          lineHeight: 1.15, color: "#fff", letterSpacing: "-.02em",
          maxWidth: 640,
        }}>
          {headline.prefix && <span>{headline.prefix} </span>}
          {headline.loss && (
            <span style={{
              color: tok.heroNum, fontStyle: "italic", fontWeight: 600,
            }}>{headline.loss}</span>
          )}
          {headline.middle && <span> {headline.middle} </span>}
          {headline.gain && (
            <span style={{
              color: tok.heroGain, fontStyle: "italic", fontWeight: 600,
            }}>{headline.gain}</span>
          )}
          {headline.suffix}
        </div>

        {/* Sub */}
        {sub && (
          <div style={{
            fontSize: 13, color: "#B5BAD4",
            marginTop: 12, maxWidth: 560, lineHeight: 1.55,
          }}>{sub}</div>
        )}
      </div>

      {/* CTA */}
      {cta && (
        <div style={{ position: "relative", zIndex: 1, textAlign: "right" }}>
          <button
            onClick={onCtaClick}
            style={{
              padding: "11px 20px",
              background: "rgba(255,255,255,.1)",
              color: "#fff",
              border: "1px solid rgba(255,255,255,.18)",
              borderRadius: 8,
              fontSize: 12, fontWeight: 600,
              cursor: onCtaClick ? "pointer" : "default",
              fontFamily: tok.fontUi,
              transition: "all .2s",
              backdropFilter: "blur(4px)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "rgba(255,255,255,.18)";
              e.currentTarget.style.borderColor = "rgba(255,255,255,.3)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "rgba(255,255,255,.1)";
              e.currentTarget.style.borderColor = "rgba(255,255,255,.18)";
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
