import { useState, useEffect, useCallback } from "react";
import styled from "styled-components";
import { t } from "../tokens.js";
import {
  fetchEngagements,
  createEngagement,
  deleteEngagement,
  activateEngagement,
} from "../api.js";

/**
 * Engagements screen — editor landing. Shows every engagement the
 * analyst has in flight, plus controls to activate, add, or delete.
 *
 * Data model is ephemeral (in-memory) per the honest scoping decision
 * for Week 3 — the pitch needs the visual concept of multi-engagement
 * support but full per-engagement data isolation is a bigger lift that
 * belongs with the real multi-tenant work.
 */
export function Engagements({ onNavigateToWorkspace }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [addOpen, setAddOpen] = useState(false);
  const [toast, setToast] = useState(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const { data: d, error: e } = await fetchEngagements();
    if (d) {
      setData(d);
      setError(null);
    } else {
      setError(e?.message || "Unable to load engagements");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleActivate = async (id) => {
    setBusy(true);
    const { error: e } = await activateEngagement(id);
    if (e) setToast({ kind: "error", text: e.message });
    else setToast({ kind: "success", text: "Active engagement switched." });
    await refresh();
    setBusy(false);
    setTimeout(() => setToast(null), 2400);
  };

  const handleDelete = async (id, name) => {
    if (!confirm(`Delete "${name}"? This removes it from the list for this session.`)) return;
    setBusy(true);
    const { error: e } = await deleteEngagement(id);
    if (e) setToast({ kind: "error", text: e.message });
    else setToast({ kind: "success", text: "Engagement deleted." });
    await refresh();
    setBusy(false);
    setTimeout(() => setToast(null), 2400);
  };

  const handleCreate = async (payload) => {
    setBusy(true);
    const { error: e } = await createEngagement(payload);
    if (e) {
      setToast({ kind: "error", text: e.message });
      setBusy(false);
      setTimeout(() => setToast(null), 2400);
      return false;
    }
    setToast({ kind: "success", text: "Engagement added." });
    setAddOpen(false);
    await refresh();
    setBusy(false);
    setTimeout(() => setToast(null), 2400);
    return true;
  };

  if (loading) {
    return (
      <Main>
        <Shell>
          <Loading>Loading engagements…</Loading>
        </Shell>
      </Main>
    );
  }

  if (error && !data) {
    return (
      <Main>
        <Shell>
          <ErrorCard>
            <ErrorTitle>Couldn't load engagements</ErrorTitle>
            <ErrorBody>{error}</ErrorBody>
          </ErrorCard>
        </Shell>
      </Main>
    );
  }

  const engagements = data?.engagements || [];
  const activeId = data?.active_engagement_id;

  // Sort: active first, then by status (active, in_review, wrapped), then by updated date desc
  const statusOrder = { active: 0, in_review: 1, wrapped: 2 };
  const sorted = [...engagements].sort((a, b) => {
    if (a.id === activeId) return -1;
    if (b.id === activeId) return 1;
    const s = (statusOrder[a.status] ?? 3) - (statusOrder[b.status] ?? 3);
    if (s !== 0) return s;
    return (b.last_updated || "").localeCompare(a.last_updated || "");
  });

  const activeCount = engagements.filter((e) => e.status === "active").length;
  const inReviewCount = engagements.filter((e) => e.status === "in_review").length;
  const wrappedCount = engagements.filter((e) => e.status === "wrapped").length;

  return (
    <Main>
      <Shell>
        {/* Hero */}
        <Hero>
          <Eyebrow>Workspace · Engagements</Eyebrow>
          <Headline>{engagements.length} engagements in flight.</Headline>
          <HeroMeta>
            <HeroStat>
              <HeroStatValue>{activeCount}</HeroStatValue>
              <HeroStatLabel>Active</HeroStatLabel>
            </HeroStat>
            <HeroStatSep>·</HeroStatSep>
            <HeroStat>
              <HeroStatValue>{inReviewCount}</HeroStatValue>
              <HeroStatLabel>In review</HeroStatLabel>
            </HeroStat>
            <HeroStatSep>·</HeroStatSep>
            <HeroStat>
              <HeroStatValue>{wrappedCount}</HeroStatValue>
              <HeroStatLabel>Wrapped</HeroStatLabel>
            </HeroStat>
          </HeroMeta>
        </Hero>

        {/* Add action */}
        <ToolbarRow>
          <ToolbarCopy>
            Select an engagement to make it active. Opening the Workspace tab
            lands you in the tools for the active engagement.
          </ToolbarCopy>
          <PrimaryButton onClick={() => setAddOpen(true)} disabled={busy}>
            + New engagement
          </PrimaryButton>
        </ToolbarRow>

        {/* List */}
        <List>
          {sorted.map((e) => (
            <EngagementCard
              key={e.id}
              $active={e.id === activeId}
            >
              <CardMain>
                <CardTopRow>
                  <StatusBadge $status={e.status}>
                    {e.status === "active" ? "Active" :
                     e.status === "in_review" ? "In review" : "Wrapped"}
                  </StatusBadge>
                  {e.id === activeId && (
                    <ActiveBadge>◉ Current engagement</ActiveBadge>
                  )}
                  <CardPeriod>{e.period}</CardPeriod>
                </CardTopRow>
                <CardClient>{e.client}</CardClient>
                <CardName>{e.engagement_name}</CardName>
                {e.summary && <CardSummary>{e.summary}</CardSummary>}
                <CardFooter>
                  Owner: {e.owner} · Last updated {formatDate(e.last_updated)}
                </CardFooter>
              </CardMain>

              <CardActions>
                {e.id === activeId ? (
                  <CardButton
                    onClick={() => onNavigateToWorkspace?.()}
                    $primary
                  >
                    Open workspace →
                  </CardButton>
                ) : (
                  <CardButton
                    onClick={() => handleActivate(e.id)}
                    disabled={busy}
                  >
                    Set active
                  </CardButton>
                )}
                <CardButton
                  onClick={() => handleDelete(e.id, e.engagement_name)}
                  disabled={busy || e.id === activeId}
                  $danger
                >
                  Delete
                </CardButton>
              </CardActions>
            </EngagementCard>
          ))}
        </List>

        {/* Methodology note */}
        <MethodologyNote>
          Note: For the current demo, all engagements share the same analysis
          data. Switching active engagement is a UI-only change —
          per-engagement data isolation, analysis snapshots, and deliverable
          history are part of the full multi-tenant roadmap.
        </MethodologyNote>
      </Shell>

      {addOpen && (
        <AddEngagementModal
          onClose={() => setAddOpen(false)}
          onSubmit={handleCreate}
          busy={busy}
        />
      )}

      {toast && <Toast $kind={toast.kind}>{toast.text}</Toast>}
    </Main>
  );
}

// ─── Add engagement modal ───

function AddEngagementModal({ onClose, onSubmit, busy }) {
  const [client, setClient] = useState("");
  const [name, setName] = useState("");
  const [period, setPeriod] = useState("");
  const [summary, setSummary] = useState("");
  const [status, setStatus] = useState("active");

  const canSubmit = client.trim() && name.trim() && period.trim();

  const submit = async (ev) => {
    ev.preventDefault();
    if (!canSubmit) return;
    await onSubmit({
      client: client.trim(),
      engagement_name: name.trim(),
      period: period.trim(),
      status,
      summary: summary.trim(),
    });
  };

  return (
    <ModalBackdrop onClick={(e) => e.target === e.currentTarget && onClose()}>
      <ModalCard as="form" onSubmit={submit}>
        <ModalHead>
          <ModalTitle>New engagement</ModalTitle>
          <ModalClose type="button" onClick={onClose}>✕</ModalClose>
        </ModalHead>

        <Field>
          <FieldLabel>Client</FieldLabel>
          <FieldInput
            value={client}
            onChange={(e) => setClient(e.target.value)}
            placeholder="e.g., Acme Retail"
            autoFocus
          />
        </Field>

        <Field>
          <FieldLabel>Engagement name</FieldLabel>
          <FieldInput
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., FY2026 Budget Review"
          />
        </Field>

        <Field>
          <FieldLabel>Period</FieldLabel>
          <FieldInput
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            placeholder="e.g., Jan – Dec 2026"
          />
          <FieldHint>Free-form. This is what shows up in the header.</FieldHint>
        </Field>

        <Field>
          <FieldLabel>Status</FieldLabel>
          <FieldSelect
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="active">Active</option>
            <option value="in_review">In review</option>
            <option value="wrapped">Wrapped</option>
          </FieldSelect>
        </Field>

        <Field>
          <FieldLabel>Summary <FieldOptional>(optional)</FieldOptional></FieldLabel>
          <FieldTextarea
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            rows={3}
            placeholder="One-line description."
          />
        </Field>

        <ModalFoot>
          <SecondaryButton type="button" onClick={onClose}>
            Cancel
          </SecondaryButton>
          <PrimaryButton type="submit" disabled={!canSubmit || busy}>
            {busy ? "Adding…" : "Add engagement"}
          </PrimaryButton>
        </ModalFoot>
      </ModalCard>
    </ModalBackdrop>
  );
}

function formatDate(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    // new Date on malformed strings returns Invalid Date (not throws).
    // Guard against that rendering as "Invalid Date" in the UI.
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return iso;
  }
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
  padding: ${t.space[10]} ${t.layout.pad.wide} ${t.space[16]};

  @media (max-width: ${t.layout.bp.wide}) {
    padding-left: ${t.layout.pad.narrow};
    padding-right: ${t.layout.pad.narrow};
  }
`;

const Hero = styled.section`
  margin-bottom: ${t.space[8]};
`;

const Eyebrow = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${t.color.accentInk};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  margin-bottom: ${t.space[3]};
`;

const Headline = styled.h1`
  font-family: ${t.font.serif};
  font-size: clamp(32px, 4vw, 48px);
  font-weight: ${t.weight.regular};
  line-height: ${t.leading.snug};
  letter-spacing: ${t.tracking.tight};
  color: ${t.color.ink};
  margin: 0 0 ${t.space[3]} 0;
`;

const HeroMeta = styled.div`
  display: inline-flex;
  align-items: baseline;
  gap: ${t.space[3]};
  font-family: ${t.font.body};
`;

const HeroStat = styled.span`
  display: inline-flex;
  align-items: baseline;
  gap: ${t.space[2]};
`;

const HeroStatValue = styled.span`
  font-size: ${t.size.lg};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink};
  font-variant-numeric: tabular-nums;
`;

const HeroStatLabel = styled.span`
  font-size: ${t.size.sm};
  color: ${t.color.ink3};
`;

const HeroStatSep = styled.span`
  color: ${t.color.ink4};
`;

const ToolbarRow = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: ${t.space[5]};
  margin-bottom: ${t.space[5]};
  flex-wrap: wrap;
`;

const ToolbarCopy = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink3};
  line-height: ${t.leading.relaxed};
  margin: 0;
  max-width: 560px;
`;

const PrimaryButton = styled.button`
  display: inline-flex;
  align-items: center;
  padding: ${t.space[3]} ${t.space[5]};
  background: ${t.color.dark};
  color: ${t.color.inkInverse};
  border: none;
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.semibold};
  cursor: pointer;
  transition: background ${t.motion.base} ${t.motion.ease};
  white-space: nowrap;

  &:hover:not(:disabled) {
    background: ${t.color.darkSurface};
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const SecondaryButton = styled.button`
  display: inline-flex;
  align-items: center;
  padding: ${t.space[3]} ${t.space[5]};
  background: transparent;
  color: ${t.color.ink};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.medium};
  cursor: pointer;

  &:hover {
    background: ${t.color.sunken};
  }
`;

const List = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${t.space[3]};
`;

const EngagementCard = styled.article`
  display: flex;
  justify-content: space-between;
  gap: ${t.space[5]};
  padding: ${t.space[5]} ${t.space[6]};
  background: ${t.color.surface};
  border: 1px solid ${({ $active }) => ($active ? t.color.accent : t.color.border)};
  border-left-width: ${({ $active }) => ($active ? "3px" : "1px")};
  border-radius: ${t.radius.md};
  box-shadow: ${t.shadow.card};
  transition: border-color ${t.motion.base} ${t.motion.ease};

  &:hover {
    border-color: ${({ $active }) => ($active ? t.color.accent : t.color.borderStrong)};
  }

  @media (max-width: 800px) {
    flex-direction: column;
  }
`;

const CardMain = styled.div`
  flex: 1;
  min-width: 0;
`;

const CardTopRow = styled.div`
  display: flex;
  align-items: center;
  gap: ${t.space[2]};
  margin-bottom: ${t.space[2]};
  flex-wrap: wrap;
`;

const StatusBadge = styled.span`
  display: inline-flex;
  align-items: center;
  padding: 2px ${t.space[2]};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  background: ${({ $status }) =>
    $status === "active" ? t.color.positiveBg :
    $status === "in_review" ? t.color.accentSub :
    t.color.sunken};
  color: ${({ $status }) =>
    $status === "active" ? t.color.positive :
    $status === "in_review" ? t.color.accentInk :
    t.color.ink3};
`;

const ActiveBadge = styled.span`
  display: inline-flex;
  align-items: center;
  padding: 2px ${t.space[2]};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  background: ${t.color.accent};
  color: ${t.color.inkInverse};
  letter-spacing: ${t.tracking.wider};
  text-transform: uppercase;
`;

const CardPeriod = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink3};
  margin-left: auto;
`;

const CardClient = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink3};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  margin-bottom: ${t.space[1]};
`;

const CardName = styled.h3`
  font-family: ${t.font.serif};
  font-size: ${t.size.lg};
  font-weight: ${t.weight.regular};
  color: ${t.color.ink};
  margin: 0 0 ${t.space[2]} 0;
  letter-spacing: ${t.tracking.tight};
`;

const CardSummary = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink2};
  line-height: ${t.leading.relaxed};
  margin: 0 0 ${t.space[3]} 0;
`;

const CardFooter = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
`;

const CardActions = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${t.space[2]};
  justify-content: center;
  align-items: stretch;
  flex-shrink: 0;

  @media (max-width: 800px) {
    flex-direction: row;
    align-items: flex-start;
  }
`;

const CardButton = styled.button`
  padding: ${t.space[2]} ${t.space[4]};
  background: ${({ $primary, $danger }) =>
    $primary ? t.color.dark :
    $danger ? "transparent" :
    t.color.surface};
  color: ${({ $primary, $danger }) =>
    $primary ? t.color.inkInverse :
    $danger ? t.color.negative :
    t.color.ink};
  border: 1px solid ${({ $primary, $danger }) =>
    $primary ? t.color.dark :
    $danger ? t.color.border :
    t.color.border};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.medium};
  cursor: pointer;
  white-space: nowrap;
  min-width: 120px;

  &:hover:not(:disabled) {
    background: ${({ $primary, $danger }) =>
      $primary ? t.color.darkSurface :
      $danger ? t.color.negativeBg :
      t.color.sunken};
  }

  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
`;

const Loading = styled.div`
  padding: ${t.space[16]} 0;
  text-align: center;
  color: ${t.color.ink3};
  font-family: ${t.font.body};
`;

const ErrorCard = styled.div`
  padding: ${t.space[8]};
  background: ${t.color.negativeBg};
  border: 1px solid ${t.color.negative};
  border-radius: ${t.radius.md};
  text-align: center;
`;

const ErrorTitle = styled.h2`
  font-family: ${t.font.serif};
  font-size: ${t.size.lg};
  color: ${t.color.negative};
  margin: 0 0 ${t.space[2]} 0;
`;

const ErrorBody = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink};
  margin: 0;
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

// ─── Modal ───

const ModalBackdrop = styled.div`
  position: fixed;
  inset: 0;
  background: rgba(24, 22, 21, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: ${t.z.modal};
  padding: ${t.space[4]};
  animation: mlFadeIn ${t.motion.base} ${t.motion.ease};
`;

const ModalCard = styled.div`
  background: ${t.color.surface};
  border-radius: ${t.radius.lg};
  box-shadow: ${t.shadow.pop};
  padding: ${t.space[6]};
  width: 100%;
  max-width: 520px;
  max-height: calc(100vh - ${t.space[8]});
  overflow-y: auto;
`;

const ModalHead = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: ${t.space[5]};
`;

const ModalTitle = styled.h2`
  font-family: ${t.font.serif};
  font-size: ${t.size.xl};
  font-weight: ${t.weight.regular};
  color: ${t.color.ink};
  margin: 0;
`;

const ModalClose = styled.button`
  background: none;
  border: none;
  font-size: ${t.size.lg};
  color: ${t.color.ink3};
  cursor: pointer;
  padding: ${t.space[1]} ${t.space[2]};

  &:hover {
    color: ${t.color.ink};
  }
`;

const Field = styled.div`
  margin-bottom: ${t.space[4]};
`;

const FieldLabel = styled.label`
  display: block;
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink2};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  margin-bottom: ${t.space[2]};
`;

const FieldOptional = styled.span`
  font-weight: ${t.weight.regular};
  color: ${t.color.ink3};
  text-transform: none;
  letter-spacing: normal;
`;

const FieldInput = styled.input`
  width: 100%;
  padding: ${t.space[3]};
  background: ${t.color.surface};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.md};
  color: ${t.color.ink};

  &:focus {
    outline: none;
    border-color: ${t.color.accent};
  }
`;

const FieldSelect = styled.select`
  width: 100%;
  padding: ${t.space[3]};
  background: ${t.color.surface};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.md};
  color: ${t.color.ink};

  &:focus {
    outline: none;
    border-color: ${t.color.accent};
  }
`;

const FieldTextarea = styled.textarea`
  width: 100%;
  padding: ${t.space[3]};
  background: ${t.color.surface};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.md};
  color: ${t.color.ink};
  resize: vertical;

  &:focus {
    outline: none;
    border-color: ${t.color.accent};
  }
`;

const FieldHint = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
  margin: ${t.space[1]} 0 0 0;
`;

const ModalFoot = styled.div`
  display: flex;
  justify-content: flex-end;
  gap: ${t.space[3]};
  margin-top: ${t.space[5]};
`;

const Toast = styled.div`
  position: fixed;
  bottom: ${t.space[5]};
  right: ${t.space[5]};
  padding: ${t.space[3]} ${t.space[5]};
  background: ${({ $kind }) => ($kind === "error" ? t.color.negativeBg : t.color.positiveBg)};
  color: ${({ $kind }) => ($kind === "error" ? t.color.negative : t.color.positive)};
  border: 1px solid ${({ $kind }) => ($kind === "error" ? t.color.negative : t.color.positive)};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.medium};
  box-shadow: ${t.shadow.raised};
  z-index: ${t.z.toast};
  animation: mlFadeIn ${t.motion.base} ${t.motion.ease};
`;
