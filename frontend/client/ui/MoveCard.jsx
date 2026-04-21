import styled from "styled-components";
import { t } from "../tokens.js";
import { TierChip } from "./TierChip.jsx";

/**
 * MoveCard — used on Plan and Scenarios body.
 *
 * Per handoff §5 (MoveCard spec):
 *   - Two columns: description (flex) / delta block (min 180px right-aligned)
 *   - Description: TierChip + channel on first line; action sentence
 *     with bolded key figures on second line
 *   - Delta: large delta ($+/-), small percent pill, before→after line
 *   - No expand/collapse — moves are already the summary
 *
 * The action sentence supports inline <strong> tags for the bolded
 * figures shown in the mockup. We don't try to parse figures out of
 * the sentence automatically; the caller is expected to wrap the
 * dollar amounts and percentages in <strong>.
 */
export function MoveCard({
  tier = "high",
  channel,
  action,      // string — may contain inline <strong> for bolded figures
  actionNode,  // alternative: full JSX node (takes precedence over `action`)
  deltaValue,  // e.g. "+$2.8M"
  deltaPct,    // e.g. "+93.3%"
  deltaDirection = "up", // "up" | "down" | "neutral"
  beforeSpend, // e.g. "$3.0M"
  afterSpend,  // e.g. "$5.8M"
  constraints, // { swing_cap, lead_time_weeks, min_annual_floor } — offline only
  bayesDeltaHdi, // [lo, hi] dollars — 80% credible region on revenue delta; null when not in Bayesian subset
  onClick,
}) {
  const clickable = typeof onClick === "function";
  // Surface offline constraints as a subtle line below the action.
  // Only shown when there's meaningful info — don't clutter digital moves.
  const hasOfflineConstraint = constraints &&
    (constraints.swing_cap != null || constraints.lead_time_weeks > 1);
  const hasBayesHdi = Array.isArray(bayesDeltaHdi) && bayesDeltaHdi.length === 2;
  return (
    <Card as={clickable ? "button" : "div"} onClick={onClick} $clickable={clickable}>
      <Description>
        <MetaRow>
          <TierChip tier={tier} />
          {channel && <ChannelName>{channel}</ChannelName>}
          {hasOfflineConstraint && (
            <ConstraintPill>
              {constraints.lead_time_weeks} week lead time
            </ConstraintPill>
          )}
        </MetaRow>
        {actionNode ? (
          <Action>{actionNode}</Action>
        ) : (
          <Action dangerouslySetInnerHTML={{ __html: action || "" }} />
        )}
        {hasOfflineConstraint && constraints.swing_cap != null && (
          <ConstraintNote>
            Offline channel — contractually capped at ±{Math.round(constraints.swing_cap * 100)}%
            per quarter. Optimized move respects this constraint.
          </ConstraintNote>
        )}
      </Description>

      <DeltaBlock>
        <DeltaValue className="tabular" $direction={deltaDirection}>
          {deltaValue}
        </DeltaValue>
        {deltaPct && (
          <DeltaPill $direction={deltaDirection}>{deltaPct}</DeltaPill>
        )}
        {(beforeSpend && afterSpend) && (
          <SpendTransition className="tabular">
            {beforeSpend} → {afterSpend}
          </SpendTransition>
        )}
        {hasBayesHdi && (
          <BayesHdiLine
            className="tabular"
            title="Bayesian MMM 80% credible region on this move's revenue impact"
          >
            HDI {formatHdiMoney(bayesDeltaHdi[0])} – {formatHdiMoney(bayesDeltaHdi[1])}
          </BayesHdiLine>
        )}
      </DeltaBlock>
    </Card>
  );
}

// Compact dollar formatter for HDI ranges — always signed, always
// rounded to the same resolution as the main delta
function formatHdiMoney(n) {
  if (n == null) return "—";
  const sign = n < 0 ? "-" : "+";
  const abs = Math.abs(n);
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(0)}K`;
  return `${sign}$${Math.round(abs)}`;
}

// ─── Styled components ───

const Card = styled.div`
  display: grid;
  grid-template-columns: 1fr minmax(180px, auto);
  gap: ${t.space[6]};
  padding: ${t.space[5]} ${t.space[6]};
  background: ${t.color.surface};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.md};
  box-shadow: ${t.shadow.card};
  text-align: left;
  width: 100%;
  transition: box-shadow ${t.motion.base} ${t.motion.ease},
              border-color ${t.motion.base} ${t.motion.ease};

  ${({ $clickable }) => $clickable && `
    cursor: pointer;

    &:hover {
      box-shadow: ${t.shadow.raised};
      border-color: ${t.color.borderStrong};
    }
  `}
`;

const Description = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${t.space[2]};
  min-width: 0;
`;

const MetaRow = styled.div`
  display: flex;
  align-items: center;
  gap: ${t.space[3]};
`;

const ChannelName = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.medium};
  color: ${t.color.ink2};
`;

const Action = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.regular};
  color: ${t.color.ink};
  line-height: ${t.leading.normal};
  margin: 0;

  strong {
    font-weight: ${t.weight.semibold};
    color: ${t.color.ink};
  }
`;

const DeltaBlock = styled.div`
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: ${t.space[1]};
  text-align: right;
`;

const DeltaValue = styled.span`
  font-family: ${t.font.serif};
  font-size: ${t.size.xl};
  font-weight: ${t.weight.regular};
  letter-spacing: ${t.tracking.tight};
  line-height: 1;
  color: ${({ $direction }) =>
    $direction === "up" ? t.color.positive :
    $direction === "down" ? t.color.negative :
    t.color.ink};
`;

const DeltaPill = styled.span`
  display: inline-flex;
  align-items: center;
  padding: 2px ${t.space[2]};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  background: ${({ $direction }) =>
    $direction === "up" ? t.color.positiveBg :
    $direction === "down" ? t.color.negativeBg :
    t.color.sunken};
  color: ${({ $direction }) =>
    $direction === "up" ? t.color.positive :
    $direction === "down" ? t.color.negative :
    t.color.ink3};
`;

const SpendTransition = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
  margin-top: ${t.space[1]};
`;

const ConstraintPill = styled.span`
  display: inline-flex;
  align-items: center;
  padding: 1px ${t.space[2]};
  border-radius: ${t.radius.sm};
  background: ${t.color.accentSub};
  color: ${t.color.accentInk};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  letter-spacing: ${t.tracking.wider};
  text-transform: uppercase;
  white-space: nowrap;
`;

const ConstraintNote = styled.div`
  margin-top: ${t.space[2]};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
  font-style: italic;
  line-height: ${t.leading.relaxed};
`;

const BayesHdiLine = styled.span`
  margin-top: ${t.space[1]};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.accentInk};
  font-weight: ${t.weight.medium};
  letter-spacing: ${t.tracking.wider};
  font-variant-numeric: tabular-nums;
  /* Subtle but discoverable. Accent-colored so it reads as "Bayesian"
     without competing with the primary delta value. */
  opacity: 0.9;
  white-space: nowrap;
  cursor: help;
`;
