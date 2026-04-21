/**
 * ChannelShiftPanel — the Channel Shift visualization added in plan v2.
 *
 * A 100%-stacked area chart showing how channel mix has evolved over
 * the lookback window. Festival / peak-window markers from the macro
 * baseline overlay the timeline, so the user can see why a shift
 * happened (e.g. Display share spiked around Diwali).
 *
 * Data: /api/channel-performance .channel_shift
 *   - series: [{ channel, color, points: [{month, percentage}] }]
 *   - overlay_events: [{ month, name, kind }]
 *   - source: "historical" | "synthetic_from_snapshot"
 */
import React, { useMemo } from "react";
import { tok } from "../../design/tokens.js";

const CHART_W = 720;
const CHART_H = 220;
const PAD_LEFT = 40;
const PAD_RIGHT = 12;
const PAD_TOP = 16;
const PAD_BOTTOM = 36;

function buildStackedPaths(series, months) {
  if (!series?.length || !months?.length) return [];
  const innerW = CHART_W - PAD_LEFT - PAD_RIGHT;
  const innerH = CHART_H - PAD_TOP - PAD_BOTTOM;
  const xStep = months.length > 1 ? innerW / (months.length - 1) : 0;

  // Cumulative running total at each month index, per-slot
  const running = months.map(() => 0);
  const paths = [];

  for (const s of series) {
    const top = s.points.map((p, i) => {
      running[i] += p.percentage;
      const y = PAD_TOP + innerH * (1 - running[i] / 100);
      return { x: PAD_LEFT + i * xStep, y };
    });
    const bottomRunning = top.map((pt, i) => {
      const belowCumulative = running[i] - s.points[i].percentage;
      const y = PAD_TOP + innerH * (1 - belowCumulative / 100);
      return { x: pt.x, y };
    });

    const topStr = top.map((p, i) => (i === 0 ? `M${p.x},${p.y}` : `L${p.x},${p.y}`)).join(" ");
    const bottomStr = bottomRunning
      .slice().reverse()
      .map(p => `L${p.x},${p.y}`).join(" ");
    paths.push({
      channel: s.channel,
      color: s.color,
      d: `${topStr} ${bottomStr} Z`,
    });
  }
  return paths;
}

export default function ChannelShiftPanel({ shift }) {
  const series = shift?.series || [];
  const months = useMemo(
    () => (series[0]?.points || []).map(p => p.month),
    [series]
  );

  const paths = useMemo(() => buildStackedPaths(series, months), [series, months]);

  const innerW = CHART_W - PAD_LEFT - PAD_RIGHT;
  const innerH = CHART_H - PAD_TOP - PAD_BOTTOM;
  const xStep = months.length > 1 ? innerW / (months.length - 1) : 0;

  const overlay = shift?.overlay_events || [];
  const overlayByMonth = new Map();
  for (const e of overlay) {
    if (!overlayByMonth.has(e.month)) overlayByMonth.set(e.month, []);
    overlayByMonth.get(e.month).push(e);
  }

  // Show ~6 X-axis labels evenly spaced
  const labelEvery = Math.max(1, Math.floor(months.length / 6));

  return (
    <div style={{
      background: tok.card, border: `1px solid ${tok.border}`,
      borderRadius: 12, padding: "20px 24px", marginBottom: 18,
      fontFamily: tok.fontUi,
    }}>
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "flex-start",
        marginBottom: 4,
      }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700 }}>Channel Shift</div>
          <div style={{
            fontSize: 10, color: tok.text3, fontWeight: 500,
            textTransform: "uppercase", letterSpacing: "0.05em",
            marginTop: 2,
          }}>
            Mix evolution · last {shift?.lookback_months || 0} months
          </div>
        </div>
        {shift?.source?.startsWith("synthetic") && (
          <div style={{
            padding: "4px 10px", background: tok.amberSoft,
            color: tok.amberDeep, fontSize: 10, fontWeight: 600,
            borderRadius: 4, letterSpacing: "0.05em",
          }}>
            DEMO · synthesised from snapshot
          </div>
        )}
      </div>

      {series.length === 0 ? (
        <div style={{
          padding: "40px 0", textAlign: "center",
          color: tok.text3, fontSize: 12, fontStyle: "italic",
        }}>
          Channel shift populates once performance data is loaded.
        </div>
      ) : (
        <>
          <div style={{ marginTop: 14, overflow: "hidden" }}>
            <svg viewBox={`0 0 ${CHART_W} ${CHART_H}`} style={{ width: "100%", height: "auto" }}>
              {/* Y-axis gridlines (0, 25, 50, 75, 100%) */}
              {[0, 25, 50, 75, 100].map(pct => {
                const y = PAD_TOP + innerH * (1 - pct / 100);
                return (
                  <g key={pct}>
                    <line x1={PAD_LEFT} x2={CHART_W - PAD_RIGHT}
                          y1={y} y2={y}
                          stroke={tok.border} strokeWidth="1" strokeDasharray={pct === 0 ? "0" : "2,3"}/>
                    <text x={PAD_LEFT - 6} y={y + 3}
                          fontSize="9" fill={tok.text3} textAnchor="end">
                      {pct}%
                    </text>
                  </g>
                );
              })}

              {/* Stacked areas */}
              {paths.map((p, i) => (
                <path key={i} d={p.d} fill={p.color} fillOpacity="0.85"/>
              ))}

              {/* X-axis labels */}
              {months.map((m, i) => {
                if (i % labelEvery !== 0 && i !== months.length - 1) return null;
                const x = PAD_LEFT + i * xStep;
                const [, mm] = m.split("-");
                const label = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][parseInt(mm,10)-1] || m;
                return (
                  <text key={m} x={x} y={CHART_H - 18}
                        fontSize="9" fill={tok.text3} textAnchor="middle">
                    {label}
                  </text>
                );
              })}

              {/* Overlay event markers */}
              {Array.from(overlayByMonth.entries()).map(([month, events]) => {
                const idx = months.indexOf(month);
                if (idx < 0) return null;
                const x = PAD_LEFT + idx * xStep;
                const label = events.map(e => e.name).join(" + ");
                return (
                  <g key={month}>
                    <line x1={x} x2={x} y1={PAD_TOP} y2={CHART_H - PAD_BOTTOM}
                          stroke={tok.atlas} strokeWidth="1.5" strokeDasharray="2,3"
                          opacity="0.7"/>
                    <circle cx={x} cy={PAD_TOP - 2} r="3.5" fill={tok.atlas}/>
                    <text x={x} y={PAD_TOP - 6} fontSize="8" fill={tok.atlasDeep}
                          textAnchor="middle" fontWeight="600">
                      {events[0].name.split(" ")[0]}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>

          {/* Legend */}
          <div style={{
            display: "flex", flexWrap: "wrap", gap: 14,
            marginTop: 14, paddingTop: 14,
            borderTop: `1px solid ${tok.border}`,
          }}>
            {series.map((s, i) => (
              <div key={i} style={{
                display: "flex", alignItems: "center", gap: 6, fontSize: 12,
              }}>
                <span style={{
                  width: 10, height: 10, borderRadius: 2,
                  background: s.color,
                }}/>
                <span>{s.channel}</span>
                <span style={{ color: tok.text3, fontSize: 11 }}>
                  {s.points[s.points.length - 1]?.percentage}%
                </span>
              </div>
            ))}
            {overlay.length > 0 && (
              <div style={{
                marginLeft: "auto", display: "flex", alignItems: "center", gap: 6,
                fontSize: 11, color: tok.atlasDeep,
              }}>
                <span style={{
                  width: 8, height: 8, borderRadius: "50%", background: tok.atlas,
                }}/>
                Macro events
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
