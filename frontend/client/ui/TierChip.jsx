import styled from "styled-components";
import { t } from "../tokens.js";

/**
 * TierChip — inline confidence chip used in card meta rows.
 *
 * Per handoff §5 (Tier chip spec):
 *   - 6px colored dot + all-caps tier label
 *   - 11px, 600 weight, wider tracking
 *   - high (green), directional (amber), inconclusive (gray)
 *
 * This is the inline-text form; ConfidenceBar is the bar form used in
 * KPI contexts. Both exist because a KPI card has room for a visual
 * element and cards don't.
 */
export function TierChip({ tier = "directional", label }) {
  const { color, defaultLabel } = CONFIG[tier] || CONFIG.directional;
  const resolvedLabel = label || defaultLabel;
  return (
    <Chip>
      <Dot $color={color} />
      <Text $color={color}>{resolvedLabel}</Text>
    </Chip>
  );
}

const CONFIG = {
  high: { color: t.color.positive, defaultLabel: "High confidence" },
  directional: { color: t.color.warning, defaultLabel: "Directional" },
  inconclusive: { color: t.color.neutral, defaultLabel: "Inconclusive" },
};

const Chip = styled.span`
  display: inline-flex;
  align-items: center;
  gap: ${t.space[1]};
  white-space: nowrap;
`;

const Dot = styled.span`
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: ${({ $color }) => $color};
  flex-shrink: 0;
`;

const Text = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${({ $color }) => $color};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
`;
