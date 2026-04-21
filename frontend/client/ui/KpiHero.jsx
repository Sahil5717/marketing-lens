import styled, { css } from "styled-components";
import { t } from "../tokens.js";
import { ConfidenceBar } from "./ConfidenceBar.jsx";

/**
 * KpiHero — the KPI card used in the Diagnosis/Plan/Channel Detail hero.
 *
 * Per handoff §5 (KpiHero spec):
 *   - Label (caps, small, muted)
 *   - Value (large, bold, tabular-nums, tight tracking)
 *   - Unit (small, sits next to value baseline)
 *   - Optional delta text with arrow indicator
 *   - Optional context line (right-aligned small text)
 *   - Primary variant: dark inverted background — one per hero group
 *   - Optional confidence bar (for Plan Confidence KPI specifically)
 *
 * Deliberate choice: this component does NOT expand/collapse. It's a
 * summary readout, not an interactive control. If drill-down is needed,
 * the entire card becomes a link.
 */
export function KpiHero({
  label,
  value,
  unit,
  deltaText,
  deltaDirection, // "up" | "down" | "neutral"
  context,
  primary = false,
  confidence, // "high" | "directional" | "inconclusive" — shows ConfidenceBar
}) {
  return (
    <Card $primary={primary}>
      <Row>
        <Label $primary={primary}>{label}</Label>
        {context && <Context $primary={primary}>{context}</Context>}
      </Row>

      <ValueRow>
        <Value $primary={primary} className="tabular">
          {value}
        </Value>
        {unit && <Unit $primary={primary}>{unit}</Unit>}
      </ValueRow>

      {deltaText && (
        <Delta $direction={deltaDirection} $primary={primary}>
          <Arrow>{arrowFor(deltaDirection)}</Arrow>
          {deltaText}
        </Delta>
      )}

      {confidence && <ConfidenceBar tier={confidence} />}
    </Card>
  );
}

function arrowFor(direction) {
  switch (direction) {
    case "up": return "▲";
    case "down": return "▼";
    default: return "—";
  }
}

// ─── Styled components ───

const Card = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${t.space[3]};
  padding: ${t.space[5]} ${t.space[6]};
  border-radius: ${t.radius.lg};
  border: 1px solid ${({ $primary }) => ($primary ? "transparent" : t.color.border)};
  background: ${({ $primary }) => ($primary ? t.color.dark : t.color.surface)};
  box-shadow: ${({ $primary }) => ($primary ? "none" : t.shadow.card)};
`;

const Row = styled.div`
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: ${t.space[3]};
`;

const Label = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  letter-spacing: ${t.tracking.wider};
  text-transform: uppercase;
  color: ${({ $primary }) => ($primary ? t.color.ink4 : t.color.ink3)};
`;

const Context = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.regular};
  color: ${({ $primary }) => ($primary ? t.color.ink4 : t.color.ink3)};
  text-align: right;
  line-height: ${t.leading.tight};
`;

const ValueRow = styled.div`
  display: flex;
  align-items: baseline;
  gap: ${t.space[1]};
  line-height: 1;
`;

const Value = styled.span`
  font-family: ${t.font.serif};
  font-size: ${t.size["3xl"]};
  font-weight: ${t.weight.regular};
  color: ${({ $primary }) => ($primary ? t.color.inkInverse : t.color.ink)};
  letter-spacing: ${t.tracking.tightest};
  line-height: 1;
`;

const Unit = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.md};
  font-weight: ${t.weight.medium};
  color: ${({ $primary }) => ($primary ? t.color.ink4 : t.color.ink3)};
  letter-spacing: 0;
`;

const Delta = styled.span`
  display: inline-flex;
  align-items: center;
  gap: ${t.space[1]};
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.medium};

  ${({ $direction, $primary }) => {
    const color =
      $direction === "up" ? t.color.positive :
      $direction === "down" ? (t.color.accent) :
      ($primary ? t.color.ink4 : t.color.ink3);
    return css`color: ${color};`;
  }}
`;

const Arrow = styled.span`
  font-size: ${t.size.xs};
`;
