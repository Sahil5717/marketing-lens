/**
 * MarketLens design tokens — v1 (redesign based on UX handoff).
 *
 * Canonical color/typography/spacing values for the entire client. Every
 * styled-component references these via the `t` alias. Do NOT introduce
 * ad-hoc hex values or pixel measurements in component code — add to the
 * appropriate scale here instead.
 *
 * Key shifts from legacy:
 *   - Accent: teal (#0F766E) → warm terracotta (#B45309)
 *   - Typography: Geist only → Geist + Instrument Serif (for hero
 *     headlines, h2s, and pull-quote callouts)
 *   - Semantic naming: textPrimary/textSecondary → ink/ink2/ink3/ink4
 *   - Confidence gets its own color scale (was just signal colors)
 *
 * The legacy tokens are preserved at tokens.legacy.js for reference
 * during the migration. Can be deleted once all screens are rebuilt.
 */

export const tokens = {
  // ─── Color ───
  color: {
    // Surfaces — warm paper tones, not cool greys
    canvas: "#FBFAF7",        // page background
    surface: "#FFFFFF",       // cards, inputs
    sunken: "#F3F1EB",        // subdued panels, table headers, inset sections
    surfaceSunken: "#F3F1EB", // alias for backward compat during migration

    // Borders
    border: "#E8E4DA",        // default border
    borderFaint: "#F0EDE4",   // hairlines, dividers inside cards
    borderStrong: "#D4CFC2",  // hover state borders, selected state

    // Ink — semantic text scale, replaces textPrimary/Secondary/Tertiary
    ink: "#1A1815",           // primary text — near-black, warm
    ink2: "#55524C",          // secondary text — metadata, descriptions
    ink3: "#85827B",          // tertiary text — captions, labels
    ink4: "#B5B2AA",          // disabled text, separator dots
    inkInverse: "#FBFAF7",    // text on dark surfaces (primary KPI card)

    // Legacy aliases — kept so existing screens don't break mid-migration
    // Delete these when the last legacy screen is rewritten.
    textPrimary: "#1A1815",
    textSecondary: "#55524C",
    textTertiary: "#85827B",
    textInverse: "#FBFAF7",

    // Accent — warm terracotta, replaces the legacy teal
    accent: "#B45309",        // buttons, active nav, key figure italics
    accentHover: "#9A4508",   // 8% darker for hover states
    accentSub: "#FEF3E2",     // accent-tinted backgrounds (Editor's Take)
    accentInk: "#7C2D12",     // dark accent text on accentSub surfaces

    // Signal colors — confidence tiers and delta indicators
    positive: "#166534",      // green — high confidence, positive delta
    positiveBg: "#F0FDF4",    // green-tinted background
    warning: "#92400E",       // amber — directional, caution
    warningBg: "#FFFBEB",     // amber-tinted background
    negative: "#991B1B",      // red — bad delta, errors
    negativeBg: "#FEF2F2",    // red-tinted background
    neutral: "#85827B",       // gray — inconclusive, no-change

    // Dark surface — for the primary KPI card's inverted treatment
    dark: "#1A1815",
    darkSurface: "#24211D",   // slightly lighter for nested dark elements
  },

  // ─── Typography ───
  font: {
    // Geist stays as the primary sans-serif body face
    body: "'Geist', system-ui, -apple-system, sans-serif",
    display: "'Geist', system-ui, -apple-system, sans-serif",
    // NEW: Instrument Serif — hero headlines, section h2s, callout pull
    // quotes, preset values on Scenarios. Distinctive editorial voice.
    serif: "'Instrument Serif', 'Times New Roman', Georgia, serif",
    mono: "'Geist Mono', ui-monospace, 'SF Mono', Monaco, monospace",
  },

  // Size scale — proportional to Geist's metrics, not changed from legacy
  size: {
    xs: "11px",
    sm: "13px",
    base: "14px",
    md: "15px",
    lg: "18px",
    xl: "22px",
    "2xl": "28px",
    "3xl": "36px",
    "4xl": "48px",  // hero headline on Scenarios ("What happens if...")
    "5xl": "60px",  // reserved for future
  },

  weight: {
    regular: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
  },

  leading: {
    tight: 1.1,
    snug: 1.25,
    normal: 1.45,
    relaxed: 1.55,
    loose: 1.7,
  },

  tracking: {
    tightest: "-0.03em",   // serif display text
    tight: "-0.015em",     // h1/h2
    snug: "-0.005em",      // large body
    normal: "0",
    wide: "0.025em",
    wider: "0.06em",       // uppercase labels / eyebrow text
  },

  // ─── Spacing ───
  // Base unit: 4px. Every padding/margin uses these values.
  space: {
    0: "0",
    1: "4px",
    2: "8px",
    3: "12px",
    4: "16px",
    5: "20px",
    6: "24px",
    7: "28px",
    8: "32px",
    10: "40px",
    12: "48px",
    16: "64px",
    20: "80px",
    24: "96px",
  },

  // ─── Radius ───
  radius: {
    none: "0",
    sm: "4px",
    md: "6px",
    lg: "10px",
    xl: "14px",
    full: "9999px",
  },

  // ─── Shadow ───
  // Deliberately subtle. Per handoff: "No shadows beyond the ones
  // specified." These are the specified ones.
  shadow: {
    none: "none",
    card: "0 1px 2px rgba(26, 24, 21, 0.04), 0 0 0 1px rgba(26, 24, 21, 0.02)",
    raised: "0 4px 12px rgba(26, 24, 21, 0.06), 0 0 0 1px rgba(26, 24, 21, 0.03)",
    modal: "0 24px 48px rgba(26, 24, 21, 0.15)",
  },

  // ─── Motion ───
  motion: {
    fast: "120ms",
    base: "200ms",
    slow: "320ms",
    ease: "cubic-bezier(0.4, 0, 0.2, 1)",
    // Per handoff: "No animations beyond 200ms fades on interactive
    // elements." Use `base` for interactive state changes, `slow` only
    // for screen-entry fades.
  },

  // ─── Layout ───
  layout: {
    maxWidth: "1280px",        // max content width, centered
    gridWidth: "1280px",       // alias for backward compat
    readingWidth: "780px",     // max width for prose-heavy blocks
    sidebarWidth: "340px",     // fixed width for right-side callouts (Editor's Take, Confidence by Finding)
    headerHeight: "60px",      // sticky app header
    heroGap: "48px",           // gap between hero left and right columns

    // Responsive breakpoints (per handoff: desktop-first, ≥1024px minimum)
    bp: {
      wide: "1280px",          // full design
      narrow: "1024px",        // tighter padding, same layout
      // Below 1024px: we show a "desktop-required" page. Real mobile
      // design is post-v1 scope.
    },

    // Horizontal padding — tighter at narrow breakpoint
    pad: {
      wide: "40px",
      narrow: "24px",
    },
  },

  // ─── Z-index ───
  z: {
    base: 0,
    sticky: 10,
    modal: 100,
    toast: 200,
  },
};

export const t = tokens;
export default tokens;
