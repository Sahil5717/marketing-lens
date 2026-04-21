/**
 * MarketContextPanel
 *
 * Renders the left card of Screen 01's bottom row. Shows a demand-trend
 * area chart over a macro baseline lookback window (default 4 months,
 * to match the HTML reference's "Last 90 Days" framing).
 *
 * Data contract: the `data.demand_trend.points` array from
 *   GET /api/market-context
 * Each point: { month: "YYYY-MM", value: number, label: "Mar" }
 *
 * Design references:
 *   - 05-hybrid-executive-summary.html  (bottom-row left card)
 *   - Build plan v2 §2A.3 (macro baseline feeds Screen 01)
 *
 * Intentionally stateless and pure — passes all data in via props so it
 * drops into either the current app or a fresh Vite rebuild.
 */
import React from "react";
import { tok, panelStyle, panelHeadingStyle, panelTagStyle } from "./tokens.js";

const CHART_W = 400;
const CHART_H = 140;
const PAD_TOP = 10;
const PAD_BOTTOM = 18;  // leaves room for month labels

/**
 * Given an array of { value } points, return an SVG path `d` string for
 * a line (no fill) going through them, left-to-right.
 */
function buildLinePath(points) {
  if (points.length === 0) return "";
  const { xs, ys } = mapPoints(points);
  return xs.map((x, i) => (i === 0 ? `M${x},${ys[i]}` : `L${x},${ys[i]}`)).join(" ");
}

/**
 * Area fill version — same line but closed at the bottom of the chart.
 */
function buildAreaPath(points) {
  if (points.length === 0) return "";
  const { xs, ys } = mapPoints(points);
  const line = xs.map((x, i) => (i === 0 ? `M${x},${ys[i]}` : `L${x},${ys[i]}`)).join(" ");
  const lastX = xs[xs.length - 1];
  const firstX = xs[0];
  return `${line} L${lastX},${CHART_H} L${firstX},${CHART_H} Z`;
}

/**
 * Map the raw values into chart-space coordinates. The y-axis auto-scales
 * to the data's min/max with a small headroom so the line doesn't kiss
 * the card edges.
 */
function mapPoints(points) {
  const values = points.map(p => p.value);
  const minV = Math.min(...values);
  const maxV = Math.max(...values);
  const range = maxV - minV || 1;  // avoid /0 when all values equal
  const headroom = range * 0.15;
  const yMin = minV - headroom;
  const yMax = maxV + headroom;

  const innerH = CHART_H - PAD_TOP - PAD_BOTTOM;
  const xStep = points.length > 1 ? CHART_W / (points.length - 1) : 0;

  const xs = points.map((_, i) => i * xStep);
  const ys = points.map(p => {
    const t = (p.value - yMin) / (yMax - yMin);
    return PAD_TOP + (1 - t) * innerH;
  });
  return { xs, ys };
}

function DemandTrendChart({ points }) {
  if (!points || points.length === 0) {
    return (
      <div style={{
        height: CHART_H, display: "flex", alignItems: "center",
        justifyContent: "center", color: tok.text3, fontSize: 12,
      }}>
        No macro data available for the selected window.
      </div>
    );
  }

  const { xs, ys } = mapPoints(points);
  const linePath = buildLinePath(points);
  const areaPath = buildAreaPath(points);

  return (
    <div style={{ height: CHART_H, marginTop: 8 }}>
      <svg
        viewBox={`0 0 ${CHART_W} ${CHART_H}`}
        preserveAspectRatio="none"
        style={{ width: "100%", height: "100%" }}
      >
        <defs>
          <linearGradient id="mc-gradient" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={tok.accent} stopOpacity="0.25" />
            <stop offset="100%" stopColor={tok.accent} stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={areaPath} fill="url(#mc-gradient)" />
        <path d={linePath} stroke={tok.accent} strokeWidth="2" fill="none" />

        {/* Month labels below the chart */}
        <g fontSize="9" fill={tok.text3} fontFamily={tok.fontUi}>
          {points.map((p, i) => (
            <text
              key={p.month}
              x={xs[i]}
              y={CHART_H - 3}
              textAnchor={i === 0 ? "start" : i === points.length - 1 ? "end" : "middle"}
            >
              {p.label}
            </text>
          ))}
        </g>
      </svg>
    </div>
  );
}

export default function MarketContextPanel({ data, loading, error }) {
  if (loading) {
    return (
      <div style={panelStyle}>
        <div style={panelHeadingStyle}>Market Context</div>
        <div style={panelTagStyle}>Demand Trend</div>
        <div style={{ height: CHART_H, ...centeredStyle, color: tok.text3 }}>Loading…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={panelStyle}>
        <div style={panelHeadingStyle}>Market Context</div>
        <div style={panelTagStyle}>Demand Trend</div>
        <div style={{ height: CHART_H, ...centeredStyle, color: tok.red, fontSize: 12 }}>
          {String(error)}
        </div>
      </div>
    );
  }

  const points = data?.demand_trend?.points ?? [];
  const lookback = data?.demand_trend?.lookback_months;
  const tag = lookback
    ? `Demand trend — last ${lookback} months`
    : "Demand trend";

  return (
    <div style={panelStyle}>
      <div style={panelHeadingStyle}>Market Context</div>
      <div style={panelTagStyle}>{tag}</div>
      <DemandTrendChart points={points} />
    </div>
  );
}

const centeredStyle = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
};
