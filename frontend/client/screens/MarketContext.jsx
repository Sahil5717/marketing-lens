import { useState, useEffect } from "react";
import styled from "styled-components";
import { t } from "../tokens.js";
import { fetchMarketContext } from "../api.js";
import { Callout } from "../ui/Callout.jsx";

/**
 * MarketContext screen — dedicated view for external data the analyst
 * has uploaded (events, trends, competitive).
 *
 * Layout:
 *   Hero strip — headline + sources-loaded badges
 *   Upcoming events — timeline-style list with day countdown and
 *       color-coded direction pill
 *   Near-term actions — the 90-day-window recommendations from events
 *       engine, surfaced as callouts
 *   Cost trend signals — channels with notable CPC/CPM/CVR movement
 *   Competitive landscape — our share of voice per channel, channels
 *       under pressure
 *   Empty state — if nothing uploaded, clear CTA to Workspace
 */
export function MarketContext({ data: initialData }) {
  const [data, setData] = useState(initialData);
  const [loading, setLoading] = useState(!initialData);

  useEffect(() => {
    if (initialData) {
      setData(initialData);
      setLoading(false);
      return;
    }
    let cancelled = false;
    fetchMarketContext().then(({ data: d, error }) => {
      if (!cancelled) {
        setData(d);
        setLoading(false);
      }
    });
    return () => { cancelled = true; };
  }, [initialData]);

  if (loading) {
    return (
      <Main>
        <Shell>
          <Loading>Loading market context…</Loading>
        </Shell>
      </Main>
    );
  }

  if (!data) {
    return (
      <Main>
        <Shell>
          <EmptyCard>
            <EmptyTitle>Market context unavailable</EmptyTitle>
            <EmptyCopy>
              Try refreshing, or check that analysis has been run.
            </EmptyCopy>
          </EmptyCard>
        </Shell>
      </Main>
    );
  }

  const sources = data.data_sources_loaded || [];
  const noDataUploaded = sources.length === 0;
  const events = data.events?.all || [];
  const eventRecs = data.events?.recommendations || [];
  const costAdjustments = data.trends?.cost_adjustments || [];
  const trendRecs = data.trends?.recommendations || [];
  const sovList = data.competitive?.share_of_voice || [];
  const compSummary = data.competitive?.summary || {};

  return (
    <Main>
      {/* Hero strip */}
      <HeroShell>
        <Eyebrow>
          <EyebrowDot /> Market context · External signal inventory
        </Eyebrow>
        <Headline>{data.headline}</Headline>

        {!noDataUploaded && (
          <SourceBadges>
            {sources.includes("events") && (
              <SourceBadge $color={t.color.accent}>
                ◉ Events calendar
              </SourceBadge>
            )}
            {sources.includes("trends") && (
              <SourceBadge $color={t.color.positive}>
                ◉ Cost trends
              </SourceBadge>
            )}
            {sources.includes("competitive") && (
              <SourceBadge $color={t.color.ink}>
                ◉ Competitive intel
              </SourceBadge>
            )}
          </SourceBadges>
        )}
      </HeroShell>

      {noDataUploaded && (
        <Shell>
          <EmptyCard>
            <EmptyTitle>No external context uploaded yet</EmptyTitle>
            <EmptyCopy>
              Upload events, trends, or competitive data on the <strong>Workspace</strong>
              {" "}screen to populate this view. Once uploaded, this screen shows
              upcoming events with expected impact, cost-trend alerts, and
              share-of-voice versus competitors.
            </EmptyCopy>
            <EmptyLink href="?screen=hub">Go to Workspace →</EmptyLink>
          </EmptyCard>
        </Shell>
      )}

      {!noDataUploaded && (
        <Shell>
          {/* Near-term action — the 90-day-window event recommendations */}
          {eventRecs.length > 0 && (
            <Section>
              <SectionTitle>Near-term actions</SectionTitle>
              <SectionCopy>
                Events in the next 90 days where the analyst should prepare or
                react. Impact numbers are estimated based on affected-channel
                spend and event magnitude.
              </SectionCopy>
              <ActionGrid>
                {eventRecs.map((r, i) => (
                  <ActionCard key={i} $type={r.type}>
                    <ActionType $type={r.type}>
                      {r.type === "PREPARE" ? "▲ Prepare" :
                       r.type === "MITIGATE" ? "⚠ Mitigate" :
                       r.type === "CAPITALIZE" ? "↑ Capitalize" :
                       "Action"}
                    </ActionType>
                    <ActionTitle>{r.action_summary || r.title}</ActionTitle>
                    {r.narrative && <ActionBody>{r.narrative}</ActionBody>}
                    {r.impact != null && r.impact !== 0 && (
                      <ActionImpact>
                        Est. impact: {formatMoney(r.impact)}
                      </ActionImpact>
                    )}
                  </ActionCard>
                ))}
              </ActionGrid>
            </Section>
          )}

          {/* Events timeline */}
          {events.length > 0 && (
            <Section>
              <SectionTitle>
                Upcoming events
                <SectionCount>{events.length}</SectionCount>
              </SectionTitle>
              <SectionCopy>
                Every event the analyst has loaded, sorted by proximity.
                Events inside the 90-day window surface as near-term actions above.
              </SectionCopy>
              <EventList>
                {events.map((e, i) => (
                  <EventRow key={i}>
                    <EventTimelineCol>
                      <EventDot $direction={e.direction} />
                      {i < events.length - 1 && <EventLine />}
                    </EventTimelineCol>
                    <EventContent>
                      <EventTopRow>
                        <EventName>{e.name}</EventName>
                        <EventDate>{formatDaysAway(e.days_away)} · {e.date}</EventDate>
                      </EventTopRow>
                      <EventMetaRow>
                        <EventType>{formatEventType(e.type)}</EventType>
                        {e.impact_pct != null && (
                          <>
                            <EventSep>·</EventSep>
                            <EventImpactPill $direction={e.direction}>
                              {e.direction === "positive" ? "+" : ""}{e.impact_pct}% expected
                            </EventImpactPill>
                          </>
                        )}
                        {e.magnitude && (
                          <>
                            <EventSep>·</EventSep>
                            <EventMagnitude>{e.magnitude} magnitude</EventMagnitude>
                          </>
                        )}
                      </EventMetaRow>
                      {e.affected_channels && e.affected_channels.length > 0 && (
                        <EventChannels>
                          Affects: {e.affected_channels.map(c =>
                            c.replaceAll("_", " ").replace(/\b\w/g, l => l.toUpperCase())
                          ).join(", ")}
                        </EventChannels>
                      )}
                    </EventContent>
                  </EventRow>
                ))}
              </EventList>
            </Section>
          )}

          {/* Cost trends */}
          {costAdjustments.length > 0 && (
            <Section>
              <SectionTitle>Cost trend signals</SectionTitle>
              <SectionCopy>
                Year-over-year changes in channel costs (CPC, CPM) per uploaded
                trends data. Rising costs compress the response curve — what
                worked at $X spend last year may now require $X + Y for the
                same return.
              </SectionCopy>
              <TrendTable>
                <thead>
                  <tr>
                    <Th $align="left">Channel</Th>
                    <Th $align="right">YoY change</Th>
                    <Th $align="left">Implication</Th>
                  </tr>
                </thead>
                <tbody>
                  {costAdjustments.map((c, i) => (
                    <tr key={i}>
                      <Td $align="left"><strong>{c.channel_display}</strong></Td>
                      <Td $align="right">
                        <TrendPill $direction={
                          (c.yoy_change_pct || 0) > 0 ? "up" :
                          (c.yoy_change_pct || 0) < 0 ? "down" : "flat"
                        }>
                          {(c.yoy_change_pct || 0) > 0 ? "▲" :
                           (c.yoy_change_pct || 0) < 0 ? "▼" : "—"}
                          {" "}
                          {(c.yoy_change_pct || 0) > 0 ? "+" : ""}{c.yoy_change_pct || 0}%
                        </TrendPill>
                      </Td>
                      <Td $align="left" $muted>
                        {costImplication(c)}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </TrendTable>
            </Section>
          )}

          {trendRecs.length > 0 && (
            <Section>
              <SectionTitle>Trend-driven recommendations</SectionTitle>
              <Callout label="From trends data">
                <ul style={{ margin: 0, paddingLeft: "1.25rem" }}>
                  {trendRecs.slice(0, 5).map((r, i) => (
                    <li key={i} style={{ marginBottom: "0.5rem" }}>
                      <strong>{r.action_summary || r.title}:</strong>{" "}
                      {r.narrative || ""}
                    </li>
                  ))}
                </ul>
              </Callout>
            </Section>
          )}

          {/* Competitive */}
          {sovList.length > 0 && (
            <Section>
              <SectionTitle>Competitive landscape</SectionTitle>
              <SectionCopy>
                Your share of voice per channel vs tracked competitors.
                Channels with low SOV face more auction pressure; channels
                with 100% SOV have no recorded competitor spend in that
                dataset (may reflect a gap in the competitive data feed
                rather than true dominance).
              </SectionCopy>
              <CompTable>
                <thead>
                  <tr>
                    <Th $align="left">Channel</Th>
                    <Th $align="right">Our SOV</Th>
                    <Th $align="left">Market position</Th>
                    <Th $align="right">Our spend</Th>
                    <Th $align="right">Competitor spend</Th>
                  </tr>
                </thead>
                <tbody>
                  {sovList.map((s, i) => (
                    <tr key={i}>
                      <Td $align="left"><strong>{s.channel_display}</strong></Td>
                      <Td $align="right">
                        <SOVBar $pct={(s.share_of_voice || 0) * 100}>
                          <span>{((s.share_of_voice || 0) * 100).toFixed(0)}%</span>
                        </SOVBar>
                      </Td>
                      <Td $align="left" $muted>
                        {marketPositionLabel(s.share_of_voice)}
                      </Td>
                      <Td $align="right" className="tabular">{formatMoney(s.our_spend)}</Td>
                      <Td $align="right" className="tabular">
                        {s.competitor_spend > 0 ? formatMoney(s.competitor_spend) : "—"}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </CompTable>
            </Section>
          )}

          {/* Methodology footer */}
          <MethodologyNote>
            Note: This screen surfaces external data the analyst has uploaded.
            Event timing and impact estimates drive near-term recommendations.
            Full integration of these signals into the optimizer and response
            curves is planned for the Bayesian MMM rebuild — the numbers on
            the Plan and Scenarios screens currently reflect internal data
            only.
          </MethodologyNote>
        </Shell>
      )}
    </Main>
  );
}

// ─── Helpers ───

function formatMoney(n) {
  if (n == null) return "—";
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(0)}K`;
  return `${sign}$${Math.round(abs)}`;
}

function formatDaysAway(days) {
  if (days == null) return "";
  if (days < 0) {
    const d = Math.abs(days);
    if (d < 7) return `${d}d ago`;
    if (d < 35) {
      const w = Math.round(d / 7);
      return `${w} ${w === 1 ? "week" : "weeks"} ago`;
    }
    if (d < 365) {
      const m = Math.round(d / 30);
      return `${m} ${m === 1 ? "month" : "months"} ago`;
    }
    const y = Math.round(d / 365);
    return `${y} ${y === 1 ? "year" : "years"} ago`;
  }
  if (days === 0) return "Today";
  if (days < 7) return `In ${days} ${days === 1 ? "day" : "days"}`;
  if (days < 35) {
    const w = Math.round(days / 7);
    return `In ${w} ${w === 1 ? "week" : "weeks"}`;
  }
  if (days < 365) {
    const m = Math.round(days / 30);
    return `In ${m} ${m === 1 ? "month" : "months"}`;
  }
  const y = Math.round(days / 365);
  return `In ${y} ${y === 1 ? "year" : "years"}`;
}

function formatEventType(t) {
  if (!t) return "Event";
  return t.replaceAll("_", " ").replace(/\b\w/g, l => l.toUpperCase());
}

function costImplication(c) {
  const pct = c.yoy_change_pct || 0;
  if (pct > 15) return "Rising costs — response curve compressing; expect lower marginal returns.";
  if (pct > 5) return "Moderate cost increase. Watch CPA trends.";
  if (pct < -10) return "Falling costs — opportunity window to scale efficient channels.";
  if (pct < -3) return "Slight cost relief.";
  return "Stable cost environment.";
}

function marketPositionLabel(sov) {
  if (sov == null) return "—";
  if (sov >= 0.95) return "Dominant (or no competitor data)";
  if (sov >= 0.6) return "Leader";
  if (sov >= 0.35) return "Competitive";
  if (sov >= 0.15) return "Challenger";
  return "Under pressure";
}

// ─── Styled ───

const Main = styled.main`
  min-height: 100vh;
  background: ${t.color.canvas};
  animation: mlFadeIn ${t.motion.slow} ${t.motion.ease};
`;

const Shell = styled.div`
  max-width: ${t.layout.maxWidth};
  margin: 0 auto;
  padding: 0 ${t.layout.pad.wide} ${t.space[16]};

  @media (max-width: ${t.layout.bp.wide}) {
    padding-left: ${t.layout.pad.narrow};
    padding-right: ${t.layout.pad.narrow};
  }
`;

const HeroShell = styled.section`
  max-width: ${t.layout.maxWidth};
  margin: 0 auto;
  padding: ${t.space[10]} ${t.layout.pad.wide} ${t.space[8]};

  @media (max-width: ${t.layout.bp.wide}) {
    padding-left: ${t.layout.pad.narrow};
    padding-right: ${t.layout.pad.narrow};
  }
`;

const Eyebrow = styled.div`
  display: inline-flex;
  align-items: center;
  gap: ${t.space[2]};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  color: ${t.color.accentInk};
  margin-bottom: ${t.space[3]};
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
  font-size: clamp(32px, 4vw, 48px);
  font-weight: ${t.weight.regular};
  line-height: ${t.leading.snug};
  letter-spacing: ${t.tracking.tight};
  color: ${t.color.ink};
  margin: 0 0 ${t.space[5]} 0;
  max-width: 900px;

  em, i {
    font-style: italic;
    color: ${t.color.accent};
  }
`;

const SourceBadges = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: ${t.space[2]};
`;

const SourceBadge = styled.span`
  display: inline-flex;
  align-items: center;
  padding: ${t.space[1]} ${t.space[3]};
  background: ${t.color.surface};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${({ $color }) => $color};
  letter-spacing: ${t.tracking.wider};
  text-transform: uppercase;
`;

const Loading = styled.div`
  padding: ${t.space[16]} 0;
  text-align: center;
  color: ${t.color.ink3};
  font-family: ${t.font.body};
`;

const EmptyCard = styled.div`
  padding: ${t.space[10]} ${t.space[8]};
  background: ${t.color.surface};
  border: 1px dashed ${t.color.border};
  border-radius: ${t.radius.lg};
  text-align: center;
  max-width: 640px;
  margin: 0 auto;
`;

const EmptyTitle = styled.h2`
  font-family: ${t.font.serif};
  font-size: ${t.size.xl};
  font-weight: ${t.weight.regular};
  color: ${t.color.ink};
  margin: 0 0 ${t.space[3]} 0;
`;

const EmptyCopy = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.md};
  color: ${t.color.ink2};
  line-height: ${t.leading.relaxed};
  margin: 0 0 ${t.space[5]} 0;

  strong {
    color: ${t.color.ink};
    font-weight: ${t.weight.semibold};
  }
`;

const EmptyLink = styled.a`
  display: inline-flex;
  align-items: center;
  padding: ${t.space[3]} ${t.space[5]};
  background: ${t.color.dark};
  color: ${t.color.inkInverse};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.semibold};
  text-decoration: none;

  &:hover {
    background: ${t.color.darkSurface};
  }
`;

const Section = styled.section`
  margin-bottom: ${t.space[10]};
`;

const SectionTitle = styled.h2`
  display: flex;
  align-items: baseline;
  gap: ${t.space[3]};
  font-family: ${t.font.serif};
  font-size: ${t.size.xl};
  font-weight: ${t.weight.regular};
  letter-spacing: ${t.tracking.tight};
  color: ${t.color.ink};
  margin: 0 0 ${t.space[2]} 0;
`;

const SectionCount = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.medium};
  color: ${t.color.ink3};
`;

const SectionCopy = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink3};
  line-height: ${t.leading.relaxed};
  margin: 0 0 ${t.space[5]} 0;
  max-width: 720px;
`;

const ActionGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: ${t.space[4]};
`;

const ActionCard = styled.div`
  padding: ${t.space[5]};
  background: ${t.color.surface};
  border: 1px solid ${t.color.border};
  border-left: 3px solid ${({ $type }) =>
    $type === "PREPARE" ? t.color.positive :
    $type === "MITIGATE" ? t.color.accent :
    $type === "CAPITALIZE" ? t.color.accent :
    t.color.ink3};
  border-radius: ${t.radius.md};
  box-shadow: ${t.shadow.card};
`;

const ActionType = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${({ $type }) =>
    $type === "PREPARE" ? t.color.positive :
    $type === "MITIGATE" ? t.color.accent :
    $type === "CAPITALIZE" ? t.color.accent :
    t.color.ink3};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  margin-bottom: ${t.space[2]};
`;

const ActionTitle = styled.h3`
  font-family: ${t.font.body};
  font-size: ${t.size.md};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink};
  margin: 0 0 ${t.space[2]} 0;
  line-height: ${t.leading.normal};
`;

const ActionBody = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink2};
  line-height: ${t.leading.relaxed};
  margin: 0 0 ${t.space[3]} 0;
`;

const ActionImpact = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.semibold};
  color: ${t.color.positive};
`;

const EventList = styled.div`
  display: flex;
  flex-direction: column;
`;

const EventRow = styled.div`
  display: flex;
  gap: ${t.space[4]};
  padding-bottom: ${t.space[5]};
`;

const EventTimelineCol = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 16px;
  flex-shrink: 0;
  padding-top: 6px;
`;

const EventDot = styled.span`
  display: block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: ${({ $direction }) =>
    $direction === "positive" ? t.color.positive :
    $direction === "negative" ? t.color.negative :
    t.color.ink3};
  box-shadow: 0 0 0 2px ${t.color.canvas};
`;

const EventLine = styled.span`
  display: block;
  width: 2px;
  flex: 1;
  background: ${t.color.border};
  margin-top: ${t.space[1]};
  min-height: ${t.space[6]};
`;

const EventContent = styled.div`
  flex: 1;
  min-width: 0;
  padding: ${t.space[3]} ${t.space[5]};
  background: ${t.color.surface};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.md};
  box-shadow: ${t.shadow.card};
`;

const EventTopRow = styled.div`
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: ${t.space[3]};
  flex-wrap: wrap;
  margin-bottom: ${t.space[1]};
`;

const EventName = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.md};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink};
`;

const EventDate = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink3};
  white-space: nowrap;
`;

const EventMetaRow = styled.div`
  display: flex;
  align-items: center;
  gap: ${t.space[1]};
  flex-wrap: wrap;
  margin-bottom: ${t.space[2]};
`;

const EventType = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  font-weight: ${t.weight.semibold};
`;

const EventSep = styled.span`
  color: ${t.color.ink4};
  margin: 0 ${t.space[1]};
`;

const EventImpactPill = styled.span`
  padding: 1px ${t.space[2]};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  background: ${({ $direction }) =>
    $direction === "positive" ? t.color.positiveBg :
    $direction === "negative" ? t.color.negativeBg :
    t.color.sunken};
  color: ${({ $direction }) =>
    $direction === "positive" ? t.color.positive :
    $direction === "negative" ? t.color.negative :
    t.color.ink3};
`;

const EventMagnitude = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
  font-style: italic;
`;

const EventChannels = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
`;

const TrendTable = styled.table`
  width: 100%;
  border-collapse: collapse;
  background: ${t.color.surface};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.md};
  overflow: hidden;
  box-shadow: ${t.shadow.card};
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
`;

const CompTable = styled(TrendTable)``;

const Th = styled.th`
  text-align: ${({ $align }) => $align || "left"};
  padding: ${t.space[3]} ${t.space[4]};
  background: ${t.color.sunken};
  border-bottom: 1px solid ${t.color.border};
  font-weight: ${t.weight.semibold};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
`;

const Td = styled.td`
  text-align: ${({ $align }) => $align || "left"};
  padding: ${t.space[3]} ${t.space[4]};
  border-bottom: 1px solid ${t.color.borderFaint};
  color: ${({ $muted }) => ($muted ? t.color.ink2 : t.color.ink)};
  vertical-align: middle;

  tbody tr:last-child & {
    border-bottom: none;
  }

  strong {
    font-weight: ${t.weight.semibold};
  }
`;

const TrendPill = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 1px ${t.space[2]};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  white-space: nowrap;
  background: ${({ $direction }) =>
    $direction === "up" ? t.color.negativeBg :  /* rising costs = bad */
    $direction === "down" ? t.color.positiveBg :  /* falling costs = good */
    t.color.sunken};
  color: ${({ $direction }) =>
    $direction === "up" ? t.color.negative :
    $direction === "down" ? t.color.positive :
    t.color.ink3};
`;

const SOVBar = styled.div`
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: ${t.space[2]};
  position: relative;
  min-width: 100px;
  height: 24px;

  span {
    font-family: ${t.font.body};
    font-size: ${t.size.sm};
    font-weight: ${t.weight.semibold};
    color: ${({ $pct }) =>
      $pct >= 60 ? t.color.positive :
      $pct >= 30 ? t.color.ink :
      t.color.warning};
    z-index: 1;
  }

  &::before {
    content: "";
    position: absolute;
    left: 0;
    top: 50%;
    transform: translateY(-50%);
    height: 6px;
    width: ${({ $pct }) => `${Math.max(2, Math.min(100, $pct))}%`};
    background: ${({ $pct }) =>
      $pct >= 60 ? t.color.positive :
      $pct >= 30 ? t.color.accent :
      t.color.warning};
    border-radius: 3px;
    opacity: 0.25;
  }
`;

const MethodologyNote = styled.div`
  margin-top: ${t.space[8]};
  padding: ${t.space[5]};
  background: ${t.color.sunken};
  border-left: 3px solid ${t.color.ink4};
  border-radius: 0 ${t.radius.sm} ${t.radius.sm} 0;
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink2};
  line-height: ${t.leading.relaxed};
`;
