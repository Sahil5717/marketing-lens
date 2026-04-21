import { useMemo, useState } from "react";
import styled from "styled-components";
import { t } from "../tokens.js";
import {
  HeroRow,
  HeroLeft,
  HeroRight,
  Eyebrow,
  HeroHeadline,
  HeroLede,
} from "../ui/HeroRow.jsx";
import { KpiHero } from "../ui/KpiHero.jsx";
import { Byline } from "../ui/Byline.jsx";
import { Callout } from "../ui/Callout.jsx";
import { FindingCard } from "../ui/FindingCard.jsx";
import { SubNav, SubNavTab } from "../ui/SubNav.jsx";
import { PageShell, TwoColumn, MainColumn, Sidebar } from "../ui/PageShell.jsx";
import { ConfidenceBar } from "../ui/ConfidenceBar.jsx";

/**
 * Diagnosis — redesigned per UX handoff + mockup Image 2.
 *
 * Structure:
 *   Hero (two columns)
 *     Left: eyebrow + answer-first serif headline + lede + byline
 *     Right: 3 KPI cards (Portfolio ROAS primary/dark, Value at Risk,
 *            Plan Confidence with ConfidenceBar)
 *   SubNav (3 tabs)
 *     Findings · Channel performance · Data & assumptions
 *   Body (2 columns)
 *     Main: findings head + stacked FindingCards
 *     Sidebar: Editor's Take Callout + Confidence by Finding list
 *
 * Editor mode behavior is threaded through:
 *   - Suppressed findings appear (dimmed) instead of being hidden
 *   - Each FindingCard shows Add/Edit note + Hide buttons in a footer strip
 *   - onCommentaryEdit / onSuppressToggle callbacks handle persistence
 *
 * This component is rendered by both DiagnosisApp (client view, no
 * editor affordances) and EditorApp (editor view, with affordances).
 * The `editorMode` prop toggles the affordances.
 */
export function Diagnosis({
  data,
  editorMode = false,
  onCommentaryEdit,
  onSuppressToggle,
}) {
  // Body tab state — URL-based routing is future work; keep it local
  // for now to match the mockup's behavior
  const [activeTab, setActiveTab] = useState("findings");

  if (!data) return null;

  const hero = data.hero || {};
  const kpis = data.kpis || {};
  const findings = data.findings || [];
  const visibleFindings = editorMode
    ? findings
    : findings.filter((f) => !f.suppressed);

  // Render hero segments — plain text and emphasis (italic accent) fragments
  const headlineElements = useMemo(() => {
    const segments = hero.segments || [];
    return segments.map((seg, i) =>
      seg.emphasis ? <em key={i}>{seg.text}</em> : <span key={i}>{seg.text}</span>
    );
  }, [hero.segments]);

  const portfolioKpi = kpis.portfolio_roas;
  const varKpi = kpis.value_at_risk;
  const confKpi = kpis.plan_confidence;

  return (
    <Main>
      {/* ── Hero ── */}
      <HeroRow>
        <HeroLeft>
          <Eyebrow>
            Diagnosis · Reviewed {data.reviewed_at || formatToday()}
          </Eyebrow>

          <HeroHeadline>
            {headlineElements.length > 0 ? headlineElements : data.headline_paragraph}
          </HeroHeadline>

          {hero.lede && <HeroLede>{hero.lede}</HeroLede>}

          <Byline
            initials={(data.analyst?.initials) || "SR"}
            name={(data.analyst?.name) || "Sarah Rahman"}
            role={(data.analyst?.role) || "Senior Manager"}
            verb="Reviewed by"
            meta={formatCoverageMeta(data.data_coverage)}
          />
        </HeroLeft>

        <HeroRight>
          {portfolioKpi && (
            <KpiHero
              primary
              label={portfolioKpi.label}
              value={portfolioKpi.display.replace(/x$/i, "")}
              unit={portfolioKpi.display.match(/x$/i) ? "×" : ""}
              context={portfolioKpi.benchmark ? `Retail benchmark ${portfolioKpi.benchmark}` : undefined}
              deltaText={portfolioKpi.delta_text}
              deltaDirection={portfolioKpi.delta_direction}
            />
          )}
          {varKpi && (
            <KpiHero
              label={varKpi.label}
              value={varKpi.display.replace(/^\$|M$/g, "")}
              unit={varKpi.display.endsWith("M") ? "M" : ""}
              context={varKpi.pct_of_revenue_display ||
                       (varKpi.pct_of_revenue ? `${varKpi.pct_of_revenue}% of attributable revenue` : undefined)}
              deltaText={varKpi.delta_text || (varKpi.tone === "warning" ? "Recoverable via reallocation" : undefined)}
              deltaDirection={varKpi.delta_direction || "down"}
            />
          )}
          {confKpi && (
            <KpiHero
              label={confKpi.label}
              value={confKpi.display}
              context={confKpi.r2_display
                ? `${confKpi.r2_display}${confKpi.mape_display ? ` · ${confKpi.mape_display}` : ""}`
                : "Based on fit quality of underlying models"}
              confidence={confKpi.display?.toLowerCase()}
            />
          )}
        </HeroRight>
      </HeroRow>

      {/* ── SubNav ── */}
      <SubNav>
        <SubNavTab
          label="Findings"
          count={visibleFindings.length}
          active={activeTab === "findings"}
          onClick={() => setActiveTab("findings")}
        />
        <SubNavTab
          label="Channel performance"
          active={activeTab === "channels"}
          onClick={() => setActiveTab("channels")}
        />
        <SubNavTab
          label="Data & assumptions"
          active={activeTab === "data"}
          onClick={() => setActiveTab("data")}
        />
      </SubNav>

      {/* ── Body ── */}
      <BodyShell>
        {activeTab === "findings" && (
          <TwoColumn>
            <MainColumn>
              {/* Market snippet — interpretive cross-reference of current
                  market conditions against the findings below. Hidden when
                  no external data has been loaded. Sits above the findings
                  list because understanding market conditions changes the
                  priority of the findings. */}
              {data.market_snippet && (
                <MarketSnippetCard snippet={data.market_snippet} />
              )}

              <FindingsHead>
                <FindingsTitle>What the analysis surfaces</FindingsTitle>
                <FindingsMeta>
                  {editorMode
                    ? "Ranked by estimated impact. Click a finding to add commentary or hide from client."
                    : "Ranked by estimated impact."}
                </FindingsMeta>
              </FindingsHead>

              {visibleFindings.length === 0 && (
                <EmptyState>No findings surfaced by this analysis.</EmptyState>
              )}

              {visibleFindings.map((f, i) => (
                <FindingCard
                  key={f.key || `f-${i}`}
                  rank={i + 1}
                  tier={confidenceTierFor(f.confidence)}
                  channel={f.evidence_metric?.channel_display || formatChannel(f.evidence_metric?.channel)}
                  hasEditorNote={!!f.ey_commentary}
                  headline={f.headline}
                  subCopy={f.narrative}
                  impactLabel="Opportunity"
                  impactValue={formatImpact(f.impact_dollars)}
                  recommendation={f.recommendation}
                  suppressed={f.suppressed}
                  editorMode={editorMode}
                  onEditNote={() => onCommentaryEdit?.(f)}
                  onToggleSuppress={() => onSuppressToggle?.(f)}
                />
              ))}
            </MainColumn>

            <Sidebar>
              <EditorTakeCard data={data} editorMode={editorMode} />
              <ConfidenceCard findings={visibleFindings} />
              <MarketContextCard context={data.market_context} />
            </Sidebar>
          </TwoColumn>
        )}

        {activeTab === "channels" && (
          <PlaceholderPane>
            Channel performance lives on its own screen now —{" "}
            <a href="?screen=channels" style={{ color: t.color.accent, fontWeight: 600 }}>
              open the Channels view
            </a>{" "}
            for response curves, saturation analysis, and campaign-level detail.
          </PlaceholderPane>
        )}

        {activeTab === "data" && (
          <DataAssumptionsPane data={data} />
        )}
      </BodyShell>
    </Main>
  );
}

// ─── Sub-components ───

/**
 * Editor's Take callout — shows analyst commentary on the top finding
 * if present, or a synthesized take if none. Per the mockup, this is
 * the most visually distinctive element in the sidebar and earns the
 * terracotta tint.
 */
function EditorTakeCard({ data, editorMode = false, onAddCommentary }) {
  const findingWithCommentary = (data.findings || []).find((f) => f.ey_commentary);
  const analyst = data.analyst?.name || "Sarah Rahman";

  // Case 1: An analyst has actually written commentary. Show it.
  if (findingWithCommentary) {
    return (
      <Callout label="Editor's Take" byline={`${analyst}, reviewing analyst`}>
        {findingWithCommentary.ey_commentary.body || findingWithCommentary.ey_commentary}
      </Callout>
    );
  }

  // Case 2: No commentary, editor mode. Prompt the editor to add one
  // rather than fake a "take" by regurgitating finding metrics.
  if (editorMode) {
    const topFinding = data.findings?.[0];
    if (!topFinding) return null;
    return (
      <EditorTakePrompt>
        <EditorTakeLabel>Editor's take</EditorTakeLabel>
        <EditorTakePromptCopy>
          No commentary added yet. Click any finding's <strong>Add note</strong>
          {" "}button to write the analyst's perspective — the first note added
          will appear here for the client.
        </EditorTakePromptCopy>
      </EditorTakePrompt>
    );
  }

  // Case 3: No commentary, client mode. Hide the card entirely rather
  // than show auto-generated technical text that reads as gibberish.
  return null;
}

/**
 * Confidence by Finding sidebar card — quick scan of which findings
 * are high-confidence vs directional vs inconclusive. Per mockup
 * Image 2 it uses the 3-segment ConfidenceBar beside each finding name.
 */
function ConfidenceCard({ findings }) {
  const rows = findings.slice(0, 5).map((f) => ({
    key: f.key,
    label: confidenceSidebarLabel(f),
    tier: confidenceTierFor(f.confidence),
  }));

  return (
    <SidebarCard>
      <SidebarLabel>Confidence by finding</SidebarLabel>
      <RowList>
        {rows.map((r) => (
          <ConfRow key={r.key}>
            <ConfLabel>{r.label}</ConfLabel>
            <ConfRight>
              <ConfidenceBar tier={r.tier} />
              <ConfTierText>{tierDisplayShort(r.tier)}</ConfTierText>
            </ConfRight>
          </ConfRow>
        ))}
      </RowList>
    </SidebarCard>
  );
}

/**
 * MarketContextCard — surfaces external data (events, trends, competitive)
 * that the analyst has uploaded. Even when external data doesn't yet
 * feed into the MMM itself (full integration is planned for the Bayesian
 * rebuild), this card makes visible that the data was received and
 * provides the analyst/client with the signals it carries.
 *
 * Renders nothing if no external data has been loaded — we don't want
 * a permanent empty card.
 */
function MarketContextCard({ context }) {
  if (!context) return null;
  const loaded = context.data_sources_loaded || [];
  if (loaded.length === 0) return null;

  const events = context.events || [];
  const eventRecs = context.event_recommendations || [];
  const trendAlerts = context.trends_alerts || [];
  const compSnapshot = context.competitive_snapshot;

  return (
    <SidebarCard>
      <SidebarLabel>Market context</SidebarLabel>

      {/* Near-term recommendations get top billing — they're actionable */}
      {eventRecs.length > 0 && (
        <MCSection>
          <MCSectionHead>Near-term action</MCSectionHead>
          {eventRecs.slice(0, 2).map((r, i) => (
            <MCAction key={i}>
              <MCActionTitle>{r.action_summary || r.title}</MCActionTitle>
              {r.narrative && (
                <MCActionBody>{truncate(r.narrative, 180)}</MCActionBody>
              )}
            </MCAction>
          ))}
        </MCSection>
      )}

      {/* Upcoming events — full horizon, not just 90-day window */}
      {events.length > 0 && (
        <MCSection>
          <MCSectionHead>Upcoming events ({events.length})</MCSectionHead>
          <MCEventList>
            {events.slice(0, 5).map((e, i) => (
              <MCEventRow key={i}>
                <MCEventDot $direction={e.direction} />
                <MCEventBody>
                  <MCEventName>{e.name}</MCEventName>
                  <MCEventMeta>
                    {formatDaysAway(e.days_away)}
                    {e.impact_pct != null && e.direction && (
                      <>
                        <MCDot>·</MCDot>
                        <MCEventImpact $direction={e.direction}>
                          {e.direction === "positive" ? "+" : ""}{e.impact_pct}% expected
                        </MCEventImpact>
                      </>
                    )}
                  </MCEventMeta>
                </MCEventBody>
              </MCEventRow>
            ))}
          </MCEventList>
        </MCSection>
      )}

      {/* Trend alerts — CPC inflation, CPM shifts */}
      {trendAlerts.length > 0 && (
        <MCSection>
          <MCSectionHead>Trend alerts</MCSectionHead>
          {trendAlerts.slice(0, 2).map((a, i) => (
            <MCAction key={i}>
              <MCActionTitle>{a.title}</MCActionTitle>
              {a.narrative && (
                <MCActionBody>{truncate(a.narrative, 180)}</MCActionBody>
              )}
            </MCAction>
          ))}
        </MCSection>
      )}

      {/* Competitive snapshot */}
      {compSnapshot && compSnapshot.narrative && (
        <MCSection>
          <MCSectionHead>Competitive</MCSectionHead>
          <MCActionBody>{compSnapshot.narrative}</MCActionBody>
        </MCSection>
      )}

      <MCFooter>
        Context loaded: {loaded.join(", ")}
      </MCFooter>
    </SidebarCard>
  );
}

/**
 * MarketSnippetCard — interpretive cross-reference of market signals
 * against the findings list. Sits at the TOP of the Findings tab when
 * external market data is present.
 *
 * Distinguishes from MarketContextCard (sidebar, raw data): this card
 * connects market conditions to specific findings ("Makes Finding X
 * more urgent because...").
 *
 * Signals ranked by urgency: high first (drawing analyst attention to
 * time-sensitive moves), then medium, then low opportunities.
 */
function MarketSnippetCard({ snippet }) {
  if (!snippet || !snippet.interpretations || snippet.interpretations.length === 0) {
    return null;
  }

  const interpretations = [...snippet.interpretations].sort((a, b) => {
    const order = { high: 0, medium: 1, low: 2 };
    return (order[a.urgency] ?? 3) - (order[b.urgency] ?? 3);
  });

  return (
    <SnippetWrap>
      <SnippetHead>
        <SnippetEyebrow>
          <SnippetDot />
          CURRENT MARKET CONDITIONS
        </SnippetEyebrow>
        <SnippetHeadline>{snippet.headline}</SnippetHeadline>
        <SnippetSummary>{snippet.summary_paragraph}</SnippetSummary>
      </SnippetHead>

      <SnippetBody>
        {interpretations.map((interp, i) => (
          <SnippetItem key={i}>
            <SnippetKindBadge $kind={interp.kind}>
              {kindLabel(interp.kind)}
            </SnippetKindBadge>
            <SnippetContent>
              <SnippetSignalRow>
                <SnippetSignal>{interp.signal}</SnippetSignal>
                <SnippetUrgency $urgency={interp.urgency}>
                  {interp.urgency}
                </SnippetUrgency>
              </SnippetSignalRow>
              <SnippetImplication>{interp.implication}</SnippetImplication>
              {interp.related_finding_key && (
                <SnippetLink>
                  ↔ Linked to a finding below
                </SnippetLink>
              )}
            </SnippetContent>
          </SnippetItem>
        ))}
      </SnippetBody>
    </SnippetWrap>
  );
}

function kindLabel(kind) {
  if (kind === "event") return "Event";
  if (kind === "cost_trend") return "Cost";
  if (kind === "competitive") return "SOV";
  return kind;
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

function truncate(s, n) {
  if (!s) return "";
  if (s.length <= n) return s;
  return s.slice(0, n - 1).trimEnd() + "…";
}

function DataAssumptionsPane({ data }) {
  const cov = data.data_coverage || {};
  const method = data.methodology || [];
  return (
    <PageShell>
      <PaneSection>
        <PaneHead>Data coverage</PaneHead>
        <PaneList>
          {cov.total_spend && <li>Total spend analyzed: <strong>${formatMoneyPlain(cov.total_spend)}</strong></li>}
          {cov.total_revenue && <li>Attributable revenue: <strong>${formatMoneyPlain(cov.total_revenue)}</strong></li>}
          {cov.n_channels && <li>Channels included: <strong>{cov.n_channels}</strong></li>}
          {cov.n_campaigns && <li>Campaigns: <strong>{cov.n_campaigns}</strong></li>}
          {cov.period_rows && <li>Observations: <strong>{cov.period_rows.toLocaleString()}</strong></li>}
        </PaneList>
      </PaneSection>

      <PaneSection>
        <PaneHead>Methodology</PaneHead>
        <PaneList>
          {method.map((m, i) => (
            <li key={i}>
              <strong>{m.engine}:</strong> {m.method}
            </li>
          ))}
        </PaneList>
      </PaneSection>
    </PageShell>
  );
}

// ─── Helpers ───

function confidenceTierFor(conf) {
  if (!conf) return "directional";
  const lower = String(conf).toLowerCase();
  if (lower.startsWith("high")) return "high";
  if (lower.startsWith("inconclusive") || lower.startsWith("low")) return "inconclusive";
  return "directional";
}

function tierDisplayShort(tier) {
  if (tier === "high") return "High";
  if (tier === "directional") return "Dir.";
  return "Low";
}

function confidenceSidebarLabel(finding) {
  // Prefer a short channel-based label if available, else truncate headline
  const ch = finding.evidence_metric?.channel_display || finding.evidence_metric?.channel;
  if (ch) return ch.charAt(0).toUpperCase() + ch.slice(1).replaceAll("_", " ");
  const h = finding.headline || "";
  return h.length > 28 ? h.slice(0, 28) + "…" : h;
}

function formatChannel(ch) {
  if (!ch) return "";
  return ch.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatImpact(dollars) {
  if (dollars == null) return "—";
  const abs = Math.abs(dollars);
  const sign = dollars >= 0 ? "+" : "-";
  if (abs >= 1_000_000) return `${sign}$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1_000) return `${sign}$${Math.round(abs / 1e3)}K`;
  return `${sign}$${Math.round(abs)}`;
}

function formatMoneyPlain(n) {
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)}K`;
  return String(n);
}

function formatCoverageMeta(coverage) {
  if (!coverage) return null;
  const parts = [];
  if (coverage.n_channels) parts.push(`${coverage.n_channels} channels`);
  if (coverage.n_campaigns) parts.push(`${coverage.n_campaigns} campaigns`);
  return parts.join(" · ");
}

function formatToday() {
  const d = new Date();
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`;
}

// ─── Styled ───

const Main = styled.main`
  min-height: 100vh;
  background: ${t.color.canvas};
  animation: mlFadeIn ${t.motion.slow} ${t.motion.ease};
`;

const BodyShell = styled.div`
  max-width: ${t.layout.maxWidth};
  margin: 0 auto;
  padding: ${t.space[8]} ${t.layout.pad.wide} ${t.space[16]};

  @media (max-width: ${t.layout.bp.wide}) {
    padding-left: ${t.layout.pad.narrow};
    padding-right: ${t.layout.pad.narrow};
  }
`;

const FindingsHead = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${t.space[2]};
  margin-bottom: ${t.space[2]};
`;

const FindingsTitle = styled.h2`
  font-family: ${t.font.serif};
  font-size: ${t.size.xl};
  font-weight: ${t.weight.regular};
  color: ${t.color.ink};
  letter-spacing: ${t.tracking.tight};
  line-height: ${t.leading.snug};
  margin: 0;
`;

const FindingsMeta = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink3};
  margin: 0;
`;

const EmptyState = styled.div`
  padding: ${t.space[10]} ${t.space[6]};
  background: ${t.color.surface};
  border: 1px dashed ${t.color.border};
  border-radius: ${t.radius.md};
  text-align: center;
  color: ${t.color.ink3};
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
`;

const SidebarCard = styled.aside`
  background: ${t.color.surface};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.md};
  padding: ${t.space[5]} ${t.space[5]};
  box-shadow: ${t.shadow.card};
`;

const SidebarLabel = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink3};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  margin-bottom: ${t.space[3]};
`;

const RowList = styled.ul`
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: ${t.space[3]};
`;

const ConfRow = styled.li`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: ${t.space[3]};
`;

const ConfLabel = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink2};
  font-weight: ${t.weight.medium};
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
`;

const ConfRight = styled.span`
  display: inline-flex;
  align-items: center;
  gap: ${t.space[2]};
  flex-shrink: 0;
`;

const ConfTierText = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink2};
  font-weight: ${t.weight.semibold};
  min-width: 32px;
  text-align: right;
`;

const PlaceholderPane = styled.div`
  max-width: ${t.layout.readingWidth};
  margin: 0 auto;
  padding: ${t.space[10]} ${t.space[6]};
  background: ${t.color.surface};
  border: 1px dashed ${t.color.border};
  border-radius: ${t.radius.md};
  text-align: center;
  color: ${t.color.ink3};
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
`;

const PaneSection = styled.section`
  margin-bottom: ${t.space[8]};
`;

const PaneHead = styled.h3`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink3};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  margin: 0 0 ${t.space[3]} 0;
`;

const PaneList = styled.ul`
  list-style: disc;
  padding-left: ${t.space[5]};
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: ${t.space[2]};
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink};
  line-height: ${t.leading.relaxed};

  strong {
    font-weight: ${t.weight.semibold};
  }
`;

// ─── Editor's take prompt (empty state in editor mode) ───

const EditorTakePrompt = styled.div`
  padding: ${t.space[4]} ${t.space[5]};
  background: ${t.color.surface};
  border: 1px dashed ${t.color.border};
  border-radius: ${t.radius.md};
`;

const EditorTakeLabel = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink3};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  margin-bottom: ${t.space[2]};
`;

const EditorTakePromptCopy = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink2};
  line-height: ${t.leading.relaxed};
  margin: 0;

  strong {
    color: ${t.color.ink};
    font-weight: ${t.weight.semibold};
  }
`;

// ─── Market context sidebar card ───

const MCSection = styled.div`
  padding-top: ${t.space[3]};
  margin-top: ${t.space[3]};
  border-top: 1px solid ${t.color.borderFaint};

  &:first-of-type {
    border-top: none;
    padding-top: 0;
    margin-top: 0;
  }
`;

const MCSectionHead = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink3};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  margin-bottom: ${t.space[2]};
`;

const MCAction = styled.div`
  margin-bottom: ${t.space[3]};

  &:last-child {
    margin-bottom: 0;
  }
`;

const MCActionTitle = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink};
  line-height: ${t.leading.normal};
  margin-bottom: ${t.space[1]};
`;

const MCActionBody = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink2};
  line-height: ${t.leading.relaxed};
  margin: 0;
`;

const MCEventList = styled.ul`
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: ${t.space[2]};
`;

const MCEventRow = styled.li`
  display: flex;
  align-items: flex-start;
  gap: ${t.space[2]};
`;

const MCEventDot = styled.span`
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 6px;
  background: ${({ $direction }) =>
    $direction === "positive" ? t.color.positive :
    $direction === "negative" ? t.color.negative :
    t.color.ink4};
  flex-shrink: 0;
`;

const MCEventBody = styled.div`
  flex: 1;
  min-width: 0;
`;

const MCEventName = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.medium};
  color: ${t.color.ink};
  line-height: ${t.leading.normal};
`;

const MCEventMeta = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
  margin-top: 2px;
  display: inline-flex;
  align-items: center;
  gap: ${t.space[1]};
  flex-wrap: wrap;
`;

const MCEventImpact = styled.span`
  color: ${({ $direction }) =>
    $direction === "positive" ? t.color.positive :
    $direction === "negative" ? t.color.negative :
    t.color.ink3};
  font-weight: ${t.weight.medium};
`;

const MCDot = styled.span`
  color: ${t.color.ink4};
`;

const MCFooter = styled.div`
  margin-top: ${t.space[3]};
  padding-top: ${t.space[3]};
  border-top: 1px solid ${t.color.borderFaint};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
`;

// ─── Market snippet card ───

const SnippetWrap = styled.section`
  margin-bottom: ${t.space[6]};
  background: ${t.color.surface};
  border: 1px solid ${t.color.border};
  border-left: 3px solid ${t.color.accent};
  border-radius: ${t.radius.md};
  box-shadow: ${t.shadow.card};
  overflow: hidden;
`;

const SnippetHead = styled.div`
  padding: ${t.space[5]} ${t.space[5]} ${t.space[4]};
  background: linear-gradient(to bottom, ${t.color.sunken}, ${t.color.surface});
  border-bottom: 1px solid ${t.color.borderFaint};
`;

const SnippetEyebrow = styled.div`
  display: inline-flex;
  align-items: center;
  gap: ${t.space[2]};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${t.color.accent};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  margin-bottom: ${t.space[2]};
`;

const SnippetDot = styled.span`
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: ${t.color.accent};
`;

const SnippetHeadline = styled.h3`
  font-family: ${t.font.serif};
  font-size: ${t.size.lg};
  font-weight: ${t.weight.medium};
  color: ${t.color.ink};
  line-height: ${t.leading.tight};
  margin: 0 0 ${t.space[2]};
`;

const SnippetSummary = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink2};
  line-height: ${t.leading.relaxed};
  margin: 0;
`;

const SnippetBody = styled.div`
  padding: ${t.space[3]} ${t.space[5]};
`;

const SnippetItem = styled.div`
  display: flex;
  gap: ${t.space[4]};
  padding: ${t.space[4]} 0;
  border-bottom: 1px solid ${t.color.borderFaint};

  &:last-child { border-bottom: none; }
`;

const SnippetKindBadge = styled.span`
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  min-width: 56px;
  height: 24px;
  padding: 0 ${t.space[2]};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  border-radius: ${t.radius.sm};
  ${({ $kind }) => {
    if ($kind === "event") return `background: ${t.color.accentSub}; color: ${t.color.accentInk};`;
    if ($kind === "cost_trend") return `background: ${t.color.sunken}; color: ${t.color.ink2};`;
    if ($kind === "competitive") return `background: ${t.color.positiveBg}; color: ${t.color.positive};`;
    return `background: ${t.color.sunken}; color: ${t.color.ink3};`;
  }}
`;

const SnippetContent = styled.div`
  flex: 1;
`;

const SnippetSignalRow = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: ${t.space[3]};
  margin-bottom: ${t.space[2]};
`;

const SnippetSignal = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink};
`;

const SnippetUrgency = styled.span`
  flex-shrink: 0;
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  padding: 1px ${t.space[2]};
  border-radius: ${t.radius.sm};
  ${({ $urgency }) => {
    if ($urgency === "high") return `background: ${t.color.negativeBg}; color: ${t.color.negative};`;
    if ($urgency === "medium") return `background: ${t.color.accentSub}; color: ${t.color.accentInk};`;
    return `background: ${t.color.sunken}; color: ${t.color.ink3};`;
  }}
`;

const SnippetImplication = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink2};
  line-height: ${t.leading.relaxed};
  margin: 0;
`;

const SnippetLink = styled.div`
  margin-top: ${t.space[2]};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-style: italic;
  color: ${t.color.accent};
`;
