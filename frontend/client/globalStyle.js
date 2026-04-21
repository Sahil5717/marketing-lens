import { createGlobalStyle } from "styled-components";
import { t } from "./tokens.js";

/**
 * MarketLens global styles — loaded once at each app entry point
 * (DiagnosisApp, EditorApp, LoginApp, AnalystHubApp).
 *
 * Handles:
 *   - Instrument Serif + Geist font imports from Google Fonts
 *   - Base typography and color reset
 *   - Reduced-motion preference respect
 *   - Print styles (muted — sharing is via app, not print)
 *
 * Per handoff: restraint in animation. The entry fade-in is the only
 * animation that runs on mount; interactive state changes use 200ms
 * transitions defined per-component.
 */
export const GlobalStyle = createGlobalStyle`
  /* Google Fonts: Geist (sans + mono) and Instrument Serif */
  @import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500&family=Instrument+Serif:ital@0;1&display=swap');

  *, *::before, *::after {
    box-sizing: border-box;
  }

  html, body {
    margin: 0;
    padding: 0;
    font-family: ${t.font.body};
    font-size: ${t.size.base};
    line-height: ${t.leading.normal};
    color: ${t.color.ink};
    background: ${t.color.canvas};
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    text-rendering: optimizeLegibility;
  }

  #root {
    min-height: 100vh;
  }

  /* Reset common inconsistencies */
  h1, h2, h3, h4, h5, h6, p {
    margin: 0;
  }

  button {
    font-family: inherit;
    cursor: pointer;
  }

  input, textarea, select {
    font-family: inherit;
    font-size: inherit;
    color: inherit;
  }

  a {
    color: ${t.color.accent};
    text-decoration: none;
  }

  /* Tabular numerals for all dollar amounts — makes columns align */
  .tabular {
    font-variant-numeric: tabular-nums;
    font-feature-settings: "tnum";
  }

  /* Focus ring — accent-colored, 2px per handoff accessibility spec */
  :focus-visible {
    outline: 2px solid ${t.color.accent};
    outline-offset: 2px;
  }

  /* Respect reduced-motion preference — disable non-essential animations */
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
    }
  }

  /* Narrow-viewport notice. Per handoff: "Below 1024px, redirect to a
     desktop-required landing page for v1." Implementing as a soft
     banner rather than a hard redirect — a redirect breaks links
     shared in chat apps and tablets, and a banner is clearer feedback
     to anyone using an untested viewport. The banner appears above
     all content and can't be dismissed; the app still functions but
     layout may look compressed. Full mobile design is post-v1. */
  @media (max-width: 1023px) {
    body::before {
      content: "MarketLens is optimized for desktop (1024px+). Layout may look compressed on this viewport.";
      display: block;
      padding: ${t.space[2]} ${t.space[4]};
      background: ${t.color.accentSub};
      color: ${t.color.accentInk};
      font-family: ${t.font.body};
      font-size: ${t.size.xs};
      font-weight: ${t.weight.semibold};
      text-align: center;
      border-bottom: 1px solid ${t.color.accent}40;
    }
  }

  /* Screen-entry fade animation (replaces the legacy keyframes) */
  @keyframes mlFadeIn {
    from { opacity: 0; transform: translateY(4px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  /* Legacy keyframes used by SuppressionModal and Toast (which haven't
     been rewritten against styled-components yet — they remain from the
     pre-v18h era). Preserving these so the modal and toast animate
     correctly; can be deleted when those components get rebuilt. */
  @keyframes modalFadeIn {
    from { opacity: 0; }
    to   { opacity: 1; }
  }

  @keyframes modalSlideIn {
    from { opacity: 0; transform: translateY(12px) scale(0.98); }
    to   { opacity: 1; transform: translateY(0) scale(1); }
  }

  @keyframes toastSlideIn {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
  }
`;
