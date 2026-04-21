import styled from "styled-components";
import { t } from "../tokens.js";

/**
 * Byline — analyst attribution shown under the hero headline.
 *
 * Per mockup:
 *   - Circular avatar with initials, accent-tinted background
 *   - "Reviewed by {name}, {role}" label
 *   - Metadata line below: date range, counts
 *
 * This is the editorial-voice signal the UX designer identified as
 * central to the product feeling curated rather than generated. The
 * byline is as important as the headline — it says "someone stands
 * behind this analysis."
 */
export function Byline({ initials, name, role, verb = "Reviewed by", meta }) {
  return (
    <Row>
      <Avatar>{initials}</Avatar>
      <Text>
        <Primary>
          {verb} <strong>{name}</strong>
          {role && <>, {role}</>}
        </Primary>
        {meta && <Meta>{meta}</Meta>}
      </Text>
    </Row>
  );
}

const Row = styled.div`
  display: flex;
  align-items: flex-start;
  gap: ${t.space[3]};
  margin-top: ${t.space[2]};
`;

const Avatar = styled.span`
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: ${t.color.accent};
  color: ${t.color.inkInverse};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  letter-spacing: 0;
`;

const Text = styled.div`
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
`;

const Primary = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink2};
  line-height: ${t.leading.snug};

  strong {
    font-weight: ${t.weight.semibold};
    color: ${t.color.ink};
  }
`;

const Meta = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
  line-height: ${t.leading.snug};
`;
