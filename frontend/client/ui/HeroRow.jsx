import styled from "styled-components";
import { t } from "../tokens.js";

/**
 * HeroRow — two-column hero layout used on Diagnosis and Plan.
 *
 * Per handoff §5 (HeroRow spec):
 *   - 1.25fr / 1fr column ratio, 48px gap
 *   - Left slot: eyebrow + serif h1 + lede paragraph + byline
 *   - Right slot: stack of 3 KpiHero cards, 10px gap
 *   - Max width 1280px, centered
 *   - 32px top / 40px sides / 24px bottom padding
 *
 * The left column carries a subtle vertical separator border extending
 * the full column height, per the mockup. At narrow viewports (<1024px)
 * the columns stack; we don't support below 1024px for v1.
 */
export function HeroRow({ children }) {
  return <Row>{children}</Row>;
}

export function HeroLeft({ children }) {
  return <Left>{children}</Left>;
}

export function HeroRight({ children }) {
  return <Right>{children}</Right>;
}

/**
 * Eyebrow — small caps label above the hero headline. Colored dot
 * prefix ties back to the section identity (accent color).
 */
export function Eyebrow({ children }) {
  return (
    <EyebrowText>
      <EyebrowDot />
      {children}
    </EyebrowText>
  );
}

/**
 * HeroHeadline — the main serif headline. Supports inline italic/accent
 * fragments via children (wrap key figures in <em> tags for the italic
 * accent-colored treatment shown in the mockup).
 */
export function HeroHeadline({ children }) {
  return <Headline>{children}</Headline>;
}

export function HeroLede({ children }) {
  return <Lede>{children}</Lede>;
}

// ─── Styled components ───

const Row = styled.section`
  max-width: ${t.layout.maxWidth};
  margin: 0 auto;
  padding: ${t.space[8]} ${t.layout.pad.wide} ${t.space[6]};
  display: grid;
  grid-template-columns: 1.25fr 1fr;
  gap: ${t.layout.heroGap};
  align-items: start;

  @media (max-width: ${t.layout.bp.wide}) {
    padding-left: ${t.layout.pad.narrow};
    padding-right: ${t.layout.pad.narrow};
  }
`;

const Left = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${t.space[4]};
  padding-right: ${t.space[6]};
  border-right: 1px solid ${t.color.borderFaint};
  min-width: 0;
  animation: mlFadeIn ${t.motion.slow} ${t.motion.ease};
`;

const Right = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${t.space[3]};
  animation: mlFadeIn ${t.motion.slow} ${t.motion.ease} 80ms both;
`;

const EyebrowText = styled.div`
  display: inline-flex;
  align-items: center;
  gap: ${t.space[2]};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  color: ${t.color.accentInk};
`;

const EyebrowDot = styled.span`
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: ${t.color.accent};
`;

const Headline = styled.h1`
  font-family: ${t.font.serif};
  font-size: clamp(28px, 3.6vw, 40px);
  font-weight: ${t.weight.regular};
  line-height: ${t.leading.snug};
  letter-spacing: ${t.tracking.tight};
  color: ${t.color.ink};
  margin: 0;
  max-width: 640px;

  /* Inline italic fragments carry the accent color — pattern from mockup */
  em, i {
    font-style: italic;
    color: ${t.color.accent};
    font-weight: ${t.weight.regular};
  }
`;

const Lede = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.md};
  font-weight: ${t.weight.regular};
  line-height: ${t.leading.relaxed};
  color: ${t.color.ink2};
  margin: 0;
  max-width: 620px;
`;
