/**
 * UpcomingPeakWindowsPanel
 *
 * Renders the right card of Screen 01's bottom row. Lists upcoming
 * festivals + public holidays with an impact badge, sourced from the
 * centrally-curated macro baseline.
 *
 * Data contract: the `data.upcoming_peaks` array from
 *   GET /api/market-context
 * Each peak: { start_date, end_date, name, kind, significance,
 *              significance_score, regions, notes, days_away }
 *
 * Design references:
 *   - 05-hybrid-executive-summary.html  (bottom-row right card)
 */
import React from "react";
import { tok, panelStyle, panelHeadingStyle, panelTagStyle } from "./tokens.js";

const SHORT_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/**
 * Format a date range like the HTML reference:
 *   "Jun 14 – Jun 28"   for multi-day
 *   "Aug 15"            for single-day
 * Inputs are ISO strings from the API.
 */
function formatDateRange(startISO, endISO) {
  const s = new Date(startISO);
  const e = new Date(endISO);
  const startStr = `${SHORT_MONTHS[s.getUTCMonth()]} ${s.getUTCDate()}`;
  if (startISO === endISO) return startStr;
  const endStr = `${SHORT_MONTHS[e.getUTCMonth()]} ${e.getUTCDate()}`;
  return `${startStr} – ${endStr}`;
}

/** Map significance display string to a badge style (red-soft / amber-soft). */
function badgeStyleFor(significance) {
  if (significance === "High") {
    return { background: tok.redSoft, color: "#B91C1C" };
  }
  if (significance === "Medium") {
    return { background: tok.amberSoft, color: "#92400E" };
  }
  return { background: tok.bg, color: tok.text3 };
}

function PeakRow({ peak, isLast }) {
  const range = formatDateRange(peak.start_date, peak.end_date);
  const badge = badgeStyleFor(peak.significance);

  return (
    <div style={{
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      padding: "10px 0",
      borderBottom: isLast ? "none" : `1px solid ${tok.border}`,
      fontSize: 12,
    }}>
      <div>
        <div style={{ fontWeight: 600 }}>{range}</div>
        <div style={{ color: tok.text2, fontSize: 11, marginTop: 2 }}>
          {peak.name}
        </div>
      </div>
      <span style={{
        padding: "2px 8px",
        borderRadius: 4,
        fontSize: 10,
        fontWeight: 600,
        ...badge,
      }}>
        {peak.significance}
      </span>
    </div>
  );
}

export default function UpcomingPeakWindowsPanel({ data, loading, error }) {
  if (loading) {
    return (
      <div style={panelStyle}>
        <div style={panelHeadingStyle}>Upcoming Peak Windows</div>
        <div style={panelTagStyle}>Plan ahead</div>
        <div style={{ color: tok.text3, padding: "20px 0", fontSize: 12 }}>Loading…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={panelStyle}>
        <div style={panelHeadingStyle}>Upcoming Peak Windows</div>
        <div style={panelTagStyle}>Plan ahead</div>
        <div style={{ color: tok.red, padding: "20px 0", fontSize: 12 }}>{String(error)}</div>
      </div>
    );
  }

  const peaks = data?.upcoming_peaks ?? [];

  if (peaks.length === 0) {
    return (
      <div style={panelStyle}>
        <div style={panelHeadingStyle}>Upcoming Peak Windows</div>
        <div style={panelTagStyle}>Plan ahead</div>
        <div style={{
          color: tok.text3,
          padding: "24px 0",
          fontSize: 12,
          fontStyle: "italic",
        }}>
          No peak windows in the lookahead range. Macro baseline is
          sparse during this period — expand the window or check back
          closer to festival season.
        </div>
      </div>
    );
  }

  return (
    <div style={panelStyle}>
      <div style={panelHeadingStyle}>Upcoming Peak Windows</div>
      <div style={panelTagStyle}>Plan ahead</div>
      {peaks.map((peak, i) => (
        <PeakRow
          key={`${peak.name}-${peak.start_date}`}
          peak={peak}
          isLast={i === peaks.length - 1}
        />
      ))}
    </div>
  );
}
