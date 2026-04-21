import styled from "styled-components";
import { t } from "../tokens.js";

/**
 * PageShell — the wrapping container for each screen's main content.
 *
 * Holds max-width (1280px) and horizontal padding (40px → 24px at narrow
 * viewports) so every screen's horizontal alignment matches exactly. The
 * AppHeader uses the same values internally.
 *
 * Variants:
 *   - default: full max-width (1280px), used for screens with sidebars
 *   - reading: narrower (780px), used for prose-heavy sections
 *   - narrow: medium (960px), reserved for future use
 */
export const PageShell = styled.div`
  max-width: ${t.layout.maxWidth};
  margin: 0 auto;
  padding: 0 ${t.layout.pad.wide};

  @media (max-width: ${t.layout.bp.wide}) {
    padding: 0 ${t.layout.pad.narrow};
  }
`;

export const ReadingShell = styled.div`
  max-width: ${t.layout.readingWidth};
  margin: 0 auto;
  padding: 0 ${t.layout.pad.wide};

  @media (max-width: ${t.layout.bp.wide}) {
    padding: 0 ${t.layout.pad.narrow};
  }
`;

/**
 * TwoColumn — main-column + sidebar layout used below the hero on
 * Diagnosis, Plan, Scenarios.
 *
 *   - Main column: flexible, carries the finding/move cards
 *   - Sidebar: fixed 340px, carries Editor's Take + Confidence + Methodology
 *   - 32px gap between
 */
export const TwoColumn = styled.div`
  display: grid;
  grid-template-columns: 1fr ${t.layout.sidebarWidth};
  gap: ${t.space[8]};
  align-items: start;

  @media (max-width: 1100px) {
    /* Below 1100px the sidebar gets squeezed; stack instead */
    grid-template-columns: 1fr;
  }
`;

export const MainColumn = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${t.space[5]};
  min-width: 0;
`;

export const Sidebar = styled.aside`
  display: flex;
  flex-direction: column;
  gap: ${t.space[4]};
  position: sticky;
  top: calc(${t.layout.headerHeight} + ${t.space[4]});

  @media (max-width: 1100px) {
    position: static;
  }
`;
