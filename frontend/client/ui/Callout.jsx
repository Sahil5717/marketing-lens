import styled from "styled-components";
import { t } from "../tokens.js";

/**
 * Callout — accent-tinted pull-quote card for analyst commentary.
 *
 * Per handoff §5 (Callout spec):
 *   - accentSub background with 1px border
 *   - Decorative large italic opening-quote in the top-left at 18% opacity
 *   - Small caps label in accentInk color ("Editor's take", "Scenario note",
 *     "What could go wrong")
 *   - Serif italic body text
 *   - Sans-serif em-dash + byline
 *
 * Used in Diagnosis sidebar (Editor's Take), Plan sidebar (What could go
 * wrong), Scenarios sidebar (Scenario note), and Channel Detail sidebar.
 * Same visual treatment across all; label varies per context.
 */
export function Callout({ label = "Editor's Take", children, byline }) {
  return (
    <Card>
      <Quote aria-hidden="true">“</Quote>
      <Label>{label}</Label>
      <Body>{children}</Body>
      {byline && <Byline>— {byline}</Byline>}
    </Card>
  );
}

// ─── Styled components ───

const Card = styled.aside`
  position: relative;
  background: ${t.color.accentSub};
  border: 1px solid ${t.color.accent}26;  /* 15% opacity */
  border-radius: ${t.radius.md};
  padding: ${t.space[6]} ${t.space[5]} ${t.space[5]};
  display: flex;
  flex-direction: column;
  gap: ${t.space[2]};
  overflow: hidden;
`;

const Quote = styled.span`
  position: absolute;
  top: -${t.space[4]};
  left: ${t.space[4]};
  font-family: ${t.font.serif};
  font-style: italic;
  font-size: 96px;
  line-height: 1;
  color: ${t.color.accent};
  opacity: 0.18;
  pointer-events: none;
  user-select: none;
`;

const Label = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  color: ${t.color.accentInk};
  position: relative;
  z-index: 1;
`;

const Body = styled.div`
  font-family: ${t.font.serif};
  font-style: italic;
  font-size: ${t.size.md};
  font-weight: ${t.weight.regular};
  line-height: ${t.leading.normal};
  color: ${t.color.ink};
  position: relative;
  z-index: 1;
`;

const Byline = styled.div`
  font-family: ${t.font.body};
  font-style: normal;
  font-size: ${t.size.sm};
  color: ${t.color.ink2};
  margin-top: ${t.space[1]};
  position: relative;
  z-index: 1;
`;
