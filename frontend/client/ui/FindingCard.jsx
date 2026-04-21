import styled, { css } from "styled-components";
import { t } from "../tokens.js";
import { TierChip } from "./TierChip.jsx";

/**
 * FindingCard — used on Diagnosis body.
 *
 * Per handoff §5 (FindingCard spec):
 *   - Three columns: rank (44px) / body (flex) / impact (min 120px)
 *   - Rank: serif numeral in muted tone on a sunken panel
 *   - Body: meta row (TierChip + channel + optional editor's-note chip),
 *          headline, sub-copy (2 lines max, no truncation)
 *   - Impact: "OPPORTUNITY" label + dollar value, right-aligned
 *   - Editor footer: slide-out action strip visible only in editor mode
 *   - Suppressed state: 55% opacity, sunken bg, "Hidden from client" tag
 *
 * This is the single most important card type in the product. Nothing
 * expands — all the information the user needs to evaluate the finding
 * is visible in the collapsed state. The UX designer flagged
 * "accordion fatigue" as a core concern; our answer is "don't have
 * accordions on the primary scanning surface."
 */
export function FindingCard({
  rank,
  tier = "directional",
  channel,
  hasEditorNote = false,
  headline,
  subCopy,
  impactLabel = "Opportunity",
  impactValue,
  recommendation,     // { action, impact_display, risk, link_to? }
  suppressed = false,
  editorMode = false,
  onEditNote,
  onToggleSuppress,
  editorFooter, // custom footer content — overrides default action row
  children, // optional expanded content slot (rarely used)
}) {
  return (
    <Card $suppressed={suppressed}>
      <Row>
        <Rank>{rank}</Rank>

        <Body>
          <MetaRow>
            {suppressed ? (
              <SuppressedTag>⊘ Hidden from client</SuppressedTag>
            ) : (
              <TierChip tier={tier} />
            )}
            {channel && <ChannelName>{channel}</ChannelName>}
            {hasEditorNote && <NoteChip>✎ Editor's note</NoteChip>}
          </MetaRow>

          <Headline>{headline}</Headline>
          {subCopy && <SubCopy>{subCopy}</SubCopy>}
        </Body>

        {impactValue && impactValue !== "—" && impactValue !== "+$0" && (
          <Impact>
            <ImpactLabel>{impactLabel}</ImpactLabel>
            <ImpactValue className="tabular">{impactValue}</ImpactValue>
          </Impact>
        )}
      </Row>

      {recommendation && recommendation.action && (
        <RecBlock>
          <RecLabel>What to do</RecLabel>
          <RecAction>{recommendation.action}</RecAction>
          <RecMeta>
            {recommendation.impact_display && (
              <RecMetaItem $tone="positive">
                {recommendation.impact_display}
              </RecMetaItem>
            )}
            {recommendation.risk && (
              <RecMetaItem $tone="warning">
                ⚠ {recommendation.risk}
              </RecMetaItem>
            )}
            {recommendation.link_to === "plan" && (
              <RecLink href="?screen=plan">See full plan →</RecLink>
            )}
          </RecMeta>
        </RecBlock>
      )}

      {editorMode && (editorFooter ?? (
        <EditorFooter>
          <FooterMeta>
            {hasEditorNote
              ? <>Has commentary <Sep>·</Sep> Visible to client</>
              : <>No commentary added</>}
          </FooterMeta>
          <FooterActions>
            {onEditNote && (
              <FooterButton onClick={onEditNote}>
                {hasEditorNote ? "Edit note" : "Add note"}
              </FooterButton>
            )}
            {onToggleSuppress && (
              <FooterButton onClick={onToggleSuppress} $danger={!suppressed}>
                {suppressed ? "Unhide" : "Hide from client"}
              </FooterButton>
            )}
          </FooterActions>
        </EditorFooter>
      ))}

      {children}
    </Card>
  );
}

// ─── Styled components ───

const Card = styled.article`
  background: ${({ $suppressed }) => ($suppressed ? t.color.sunken : t.color.surface)};
  border: 1px solid ${({ $suppressed }) => ($suppressed ? t.color.borderFaint : t.color.border)};
  border-radius: ${t.radius.md};
  box-shadow: ${({ $suppressed }) => ($suppressed ? "none" : t.shadow.card)};
  overflow: hidden;
  opacity: ${({ $suppressed }) => ($suppressed ? 0.55 : 1)};
  transition: box-shadow ${t.motion.base} ${t.motion.ease},
              border-color ${t.motion.base} ${t.motion.ease};

  &:hover {
    ${({ $suppressed }) => !$suppressed && css`
      box-shadow: ${t.shadow.raised};
      border-color: ${t.color.borderStrong};
    `}
  }
`;

const Row = styled.div`
  display: grid;
  grid-template-columns: 44px 1fr minmax(120px, auto);
  gap: ${t.space[5]};
  padding: ${t.space[5]} ${t.space[6]};
  align-items: flex-start;
`;

const Rank = styled.span`
  font-family: ${t.font.serif};
  font-size: ${t.size["2xl"]};
  font-weight: ${t.weight.regular};
  color: ${t.color.ink3};
  line-height: 1;
  background: ${t.color.sunken};
  border-radius: ${t.radius.sm};
  width: 44px;
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  letter-spacing: ${t.tracking.tight};
`;

const Body = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${t.space[2]};
  min-width: 0;
`;

const MetaRow = styled.div`
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: ${t.space[3]};
`;

const ChannelName = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.medium};
  color: ${t.color.ink2};
`;

const NoteChip = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px ${t.space[2]};
  background: ${t.color.accentSub};
  color: ${t.color.accentInk};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
`;

const SuppressedTag = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px ${t.space[2]};
  background: ${t.color.surface};
  color: ${t.color.ink3};
  border: 1px dashed ${t.color.borderStrong};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
`;

const Headline = styled.h3`
  font-family: ${t.font.body};
  font-size: ${t.size.md};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink};
  line-height: ${t.leading.snug};
  letter-spacing: ${t.tracking.snug};
  margin: 0;
`;

const SubCopy = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink2};
  line-height: ${t.leading.normal};
  margin: 0;
`;

const Impact = styled.div`
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: ${t.space[1]};
  text-align: right;
`;

const ImpactLabel = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  color: ${t.color.ink3};
`;

const ImpactValue = styled.span`
  font-family: ${t.font.serif};
  font-size: ${t.size.xl};
  font-weight: ${t.weight.regular};
  color: ${t.color.positive};
  letter-spacing: ${t.tracking.tight};
  line-height: 1;
`;

const EditorFooter = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: ${t.space[4]};
  padding: ${t.space[3]} ${t.space[6]};
  border-top: 1px solid ${t.color.borderFaint};
  background: ${t.color.sunken};
`;

const FooterMeta = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
`;

const Sep = styled.span`
  color: ${t.color.ink4};
  margin: 0 ${t.space[1]};
`;

const FooterActions = styled.div`
  display: flex;
  gap: ${t.space[2]};
`;

const FooterButton = styled.button`
  padding: ${t.space[2]} ${t.space[3]};
  background: ${t.color.surface};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.medium};
  color: ${({ $danger }) => ($danger ? t.color.negative : t.color.ink)};
  cursor: pointer;
  transition: background ${t.motion.base} ${t.motion.ease}, border-color ${t.motion.base} ${t.motion.ease};

  &:hover {
    background: ${t.color.sunken};
    border-color: ${t.color.borderStrong};
  }
`;

// ─── Recommendation block ───
// Renders between the finding body and the editor footer. Visually
// distinct but part of the same card — findings that imply an action
// should carry the action inline, not force a separate screen navigation.

const RecBlock = styled.div`
  margin-top: ${t.space[4]};
  padding: ${t.space[4]} ${t.space[5]};
  background: ${t.color.sunken};
  border-left: 3px solid ${t.color.accent};
  border-radius: 0 ${t.radius.sm} ${t.radius.sm} 0;
`;

const RecLabel = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${t.color.accentInk};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  margin-bottom: ${t.space[2]};
`;

const RecAction = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.md};
  font-weight: ${t.weight.medium};
  color: ${t.color.ink};
  line-height: ${t.leading.normal};
`;

const RecMeta = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: ${t.space[3]};
  margin-top: ${t.space[3]};
  align-items: center;
`;

const RecMetaItem = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.medium};
  color: ${({ $tone }) =>
    $tone === "positive" ? t.color.positive :
    $tone === "warning" ? t.color.accentInk :
    t.color.ink3};
  line-height: ${t.leading.normal};
`;

const RecLink = styled.a`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${t.color.accent};
  text-decoration: none;
  margin-left: auto;

  &:hover {
    color: ${t.color.accentHover};
    text-decoration: underline;
  }
`;
