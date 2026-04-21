/**
 * Donut — renders a donut chart from allocation slices.
 *
 * Props:
 *   - slices: Array<{ channel, color, percentage }>  // percentages sum ≤ 100
 *   - centerLabel, centerSub
 *   - size: pixel size (default 140)
 */
import React from "react";
import { tok } from "../../design/tokens.js";

const STROKE = 3;
const R = 15.915;  // 2πR = 100 → percentage maps directly to stroke-dasharray

export default function Donut({
  slices = [],
  centerLabel,
  centerSub,
  centerColor,
  size = 140,
}) {
  let offset = 0;
  return (
    <div style={{
      position: "relative", width: size, height: size, flexShrink: 0,
    }}>
      <svg viewBox="0 0 36 36" style={{ width: "100%", height: "100%" }}>
        {/* Track */}
        <circle cx="18" cy="18" r={R} fill="none"
                stroke={tok.border} strokeWidth={STROKE}/>
        {/* Slices */}
        {slices.map((s, i) => {
          const pct = Math.max(0, Math.min(100, s.percentage || 0));
          const dash = `${pct} ${100 - pct}`;
          const dashOffset = -offset;
          offset += pct;
          return (
            <circle
              key={s.channel + i}
              cx="18" cy="18" r={R} fill="none"
              stroke={s.color} strokeWidth={STROKE}
              strokeDasharray={dash}
              strokeDashoffset={dashOffset}
              transform="rotate(-90 18 18)"
            />
          );
        })}
      </svg>
      {(centerLabel || centerSub) && (
        <div style={{
          position: "absolute", inset: 0,
          display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center",
        }}>
          {centerLabel && (
            <div style={{
              fontFamily: tok.fontDisplay, fontSize: 18, fontWeight: 600,
              letterSpacing: "-.02em", color: centerColor || tok.text,
            }}>{centerLabel}</div>
          )}
          {centerSub && (
            <div style={{
              fontSize: 9, color: tok.text3,
              textTransform: "uppercase", letterSpacing: "0.12em",
              marginTop: 2, fontWeight: 600,
            }}>{centerSub}</div>
          )}
        </div>
      )}
    </div>
  );
}
