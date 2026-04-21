import styled, { css } from "styled-components";
import { t } from "../tokens.js";

/**
 * SubNav — tab strip shown between hero and body on Diagnosis and Plan.
 *
 * Per mockup:
 *   - Active tab has a 1px-thick accent-colored underline at the bottom
 *     and ink (dark) text
 *   - Inactive tabs have muted (ink3) text, no underline
 *   - Optional count badge shown as a small dark pill after the label
 *   - Separator border at the bottom (full-width hairline)
 *
 * Usage:
 *   <SubNav>
 *     <SubNavTab label="Findings" count={7} active />
 *     <SubNavTab label="Channel performance" />
 *     <SubNavTab label="Data & assumptions" />
 *   </SubNav>
 *
 * For URL-param routing, pass `href` to SubNavTab. For client-side
 * tab state, pass `onClick`.
 */
export function SubNav({ children }) {
  return (
    <NavWrap>
      <NavRow role="tablist">{children}</NavRow>
    </NavWrap>
  );
}

export function SubNavTab({ label, count, active = false, href, onClick }) {
  const Component = href ? "a" : "button";
  return (
    <Tab
      as={Component}
      href={href}
      onClick={onClick}
      $active={active}
      role="tab"
      aria-selected={active}
    >
      <TabLabel>{label}</TabLabel>
      {count != null && <TabBadge $active={active}>{count}</TabBadge>}
    </Tab>
  );
}

// ─── Styled components ───

const NavWrap = styled.nav`
  max-width: ${t.layout.maxWidth};
  margin: 0 auto;
  padding: 0 ${t.layout.pad.wide};
  border-bottom: 1px solid ${t.color.borderFaint};

  @media (max-width: ${t.layout.bp.wide}) {
    padding: 0 ${t.layout.pad.narrow};
  }
`;

const NavRow = styled.div`
  display: flex;
  gap: ${t.space[1]};
  align-items: center;
`;

const Tab = styled.button`
  display: inline-flex;
  align-items: center;
  gap: ${t.space[2]};
  padding: ${t.space[3]} ${t.space[4]};
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;  /* overlap the NavWrap bottom border */
  font-family: ${t.font.body};
  font-size: ${t.size.base};
  font-weight: ${t.weight.medium};
  text-decoration: none;
  cursor: pointer;
  transition: color ${t.motion.base} ${t.motion.ease},
              border-color ${t.motion.base} ${t.motion.ease};

  ${({ $active }) =>
    $active
      ? css`
          color: ${t.color.ink};
          border-bottom-color: ${t.color.ink};
          font-weight: ${t.weight.semibold};
        `
      : css`
          color: ${t.color.ink3};

          &:hover {
            color: ${t.color.ink};
          }
        `}
`;

const TabLabel = styled.span`
  line-height: 1;
`;

const TabBadge = styled.span`
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 ${t.space[1]};
  border-radius: 10px;
  background: ${({ $active }) => ($active ? t.color.dark : t.color.sunken)};
  color: ${({ $active }) => ($active ? t.color.inkInverse : t.color.ink2)};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  line-height: 1;
`;
