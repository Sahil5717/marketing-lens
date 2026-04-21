import styled from "styled-components";
import { t } from "../tokens.js";

/**
 * ConfidenceBar — 3-segment visual showing confidence tier.
 *
 * Per handoff §5 (ConfidenceBar spec):
 *   - 3 horizontal bars, 3px tall, 3px gaps, max 80px wide
 *   - high: all 3 green
 *   - directional: 2 amber, 1 empty
 *   - inconclusive: 1 gray, 2 empty
 *
 * Used in KpiHero for Plan Confidence, and inline anywhere confidence
 * needs a visual rather than a text label. A text-only variant (TierChip)
 * handles in-card usage.
 */
export function ConfidenceBar({ tier = "directional" }) {
  const { filled, color } = CONFIG[tier] || CONFIG.directional;
  return (
    <Bars role="img" aria-label={`Confidence: ${tier}`}>
      {[0, 1, 2].map((i) => (
        <Segment key={i} $filled={i < filled} $color={color} />
      ))}
    </Bars>
  );
}

const CONFIG = {
  high: { filled: 3, color: t.color.positive },
  directional: { filled: 2, color: t.color.warning },
  inconclusive: { filled: 1, color: t.color.neutral },
};

const Bars = styled.span`
  display: inline-flex;
  gap: 3px;
  max-width: 80px;
`;

const Segment = styled.span`
  flex: 1;
  height: 3px;
  border-radius: 1.5px;
  background: ${({ $filled, $color }) => ($filled ? $color : t.color.borderFaint)};
  min-width: 18px;
`;
