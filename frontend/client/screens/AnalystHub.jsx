import { useState, useEffect, useCallback, useRef } from "react";
import styled, { css } from "styled-components";
import { t } from "../tokens.js";
import {
  fetchAnalystStatus,
  uploadDataFile,
  templateDownloadUrl,
  runFullAnalysis,
} from "../api.js";

/**
 * AnalystHub — analyst-only home screen (mockup Image 6/7 adapted).
 *
 * We deliberately departed from the designer's "multi-customer
 * engagements list" concept in favor of an analyst working-tools hub.
 * Rationale: multi-customer requires real multi-tenancy which is v19
 * scope; the tools hub is immediately pitch-useful and matches the
 * backend endpoints we already have (five upload endpoints, five
 * CSV templates, a run-analysis endpoint).
 *
 * Structure:
 *   Hero: "Good morning, Sarah." serif greeting + one-line status
 *   Stats strip: 4 compact cards (loaded sources / channels / campaigns / analysis status)
 *   Data sources section: 5 upload zones, one per data type.
 *     Each has: label, required badge, description, row count if loaded,
 *     drag-drop area, "Download template" link, upload button.
 *
 * Client users never land here — the shell checks role before rendering.
 */
export function AnalystHub({ onAnalysisComplete }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [runningAnalysis, setRunningAnalysis] = useState(false);
  const [toast, setToast] = useState(null);

  // Fetch status on mount and after every upload
  const refreshStatus = useCallback(async () => {
    const { data, error: e } = await fetchAnalystStatus();
    if (data) {
      setStatus(data);
      setError(null);
    } else {
      setError(e?.message || "Unable to load status");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    refreshStatus();
  }, [refreshStatus]);

  const handleUpload = useCallback(async (kind, file) => {
    setToast({ kind: "info", message: `Uploading ${file.name}…` });
    const { data, error: e } = await uploadDataFile(kind, file);
    if (e) {
      setToast({
        kind: "error",
        message: `Upload failed: ${e.message || "unknown error"}`,
      });
      // Toast will linger until next upload — errors are sticky
      return;
    }
    setToast({
      kind: "success",
      message: `${file.name} — ${data.rows} rows loaded${
        data.status ? `. ${data.status}` : ""
      }`,
    });
    // Auto-dismiss success after 5s
    setTimeout(() => setToast(null), 5000);
    refreshStatus();
  }, [refreshStatus]);

  const handleRunAnalysis = useCallback(async () => {
    setRunningAnalysis(true);
    setToast({ kind: "info", message: "Running analysis… this can take 30-60 seconds." });
    const { data, error: e } = await runFullAnalysis();
    setRunningAnalysis(false);
    if (e) {
      setToast({
        kind: "error",
        message: `Analysis failed: ${e.message || "unknown error"}`,
      });
      return;
    }
    setToast({
      kind: "success",
      message: "Analysis complete. Refresh Diagnosis, Plan, and Scenarios to see updated results.",
    });
    setTimeout(() => setToast(null), 8000);
    refreshStatus();
    if (onAnalysisComplete) onAnalysisComplete();
  }, [refreshStatus, onAnalysisComplete]);

  if (loading) {
    return (
      <Main>
        <Shell>
          <LoadingState>Loading your workspace…</LoadingState>
        </Shell>
      </Main>
    );
  }

  if (error || !status) {
    return (
      <Main>
        <Shell>
          <ErrorBox>
            Unable to load workspace status. {error || "Try refreshing the page."}
          </ErrorBox>
        </Shell>
      </Main>
    );
  }

  return (
    <Main>
      <Shell>
        {/* Greeting */}
        <GreetingSection>
          <Greeting>
            Good morning, <em>{status.greeting_name || "Sarah"}</em>.
          </Greeting>
          <NextStep>{status.next_step}</NextStep>
        </GreetingSection>

        {/* Stats strip */}
        <StatsRow>
          <StatCard>
            <StatLabel>Data sources loaded</StatLabel>
            <StatValue>
              {status.stats.loaded_sources}<StatSmall>/{status.stats.total_sources}</StatSmall>
            </StatValue>
            <StatSub>
              {status.stats.loaded_sources === status.stats.total_sources
                ? "All data available"
                : `${status.stats.total_sources - status.stats.loaded_sources} optional source${status.stats.total_sources - status.stats.loaded_sources === 1 ? "" : "s"} missing`}
            </StatSub>
          </StatCard>
          <StatCard>
            <StatLabel>Channels</StatLabel>
            <StatValue>{status.stats.channels || "—"}</StatValue>
            <StatSub>Across uploaded data</StatSub>
          </StatCard>
          <StatCard>
            <StatLabel>Campaigns</StatLabel>
            <StatValue>{status.stats.campaigns || "—"}</StatValue>
            <StatSub>Distinct campaigns tracked</StatSub>
          </StatCard>
          <StatCard>
            <StatLabel>Analysis</StatLabel>
            <StatValue $tone={status.stats.analysis_complete ? "positive" : "neutral"}>
              {status.stats.analysis_complete ? "Ready" : "Pending"}
            </StatValue>
            <StatSub>
              {status.stats.analysis_complete
                ? "Diagnosis and Plan are current"
                : "Run analysis to refresh outputs"}
            </StatSub>
          </StatCard>
        </StatsRow>

        {/* Data sources section */}
        <DataSection>
          <SectionHead>
            <SectionTitle>Data sources</SectionTitle>
            <SectionCopy>
              Upload client data for each source. Campaign performance is required for
              analysis; the rest are optional but improve accuracy and context.
            </SectionCopy>
          </SectionHead>

          <UploadGrid>
            {status.data_sources.map((source) => (
              <UploadCard
                key={source.kind}
                source={source}
                onUpload={handleUpload}
              />
            ))}
          </UploadGrid>
        </DataSection>

        {/* Run analysis CTA — sticky at bottom of hub if data is loaded */}
        {status.data_sources.some((s) => s.loaded) && (
          <RunAnalysisRow>
            <RunCopy>
              <RunTitle>Refresh the analysis</RunTitle>
              <RunSub>
                Re-runs MMM, optimizer, and diagnostics across all loaded data.
                Updates Diagnosis, Plan, Scenarios, and Channel Detail.
              </RunSub>
            </RunCopy>
            <RunButton onClick={handleRunAnalysis} disabled={runningAnalysis}>
              {runningAnalysis ? "Running…" : "Run analysis"}
            </RunButton>
          </RunAnalysisRow>
        )}
      </Shell>

      {toast && <ToastCard $kind={toast.kind}>{toast.message}</ToastCard>}
    </Main>
  );
}

// ─── UploadCard ───

function UploadCard({ source, onUpload }) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef(null);

  const pickFile = useCallback((file) => {
    if (!file) return;
    onUpload(source.kind, file);
  }, [source.kind, onUpload]);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };
  const handleDragLeave = () => setIsDragging(false);
  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) pickFile(file);
  };
  const handleInputChange = (e) => {
    const file = e.target.files?.[0];
    if (file) pickFile(file);
    e.target.value = ""; // reset so re-uploading same filename re-fires change
  };

  return (
    <CardWrap $loaded={source.loaded}>
      <CardHead>
        <CardLabelRow>
          <CardLabel>{source.label}</CardLabel>
          {source.required && <RequiredBadge>Required</RequiredBadge>}
          {source.loaded && <LoadedBadge>✓ Loaded · {source.rows.toLocaleString()} rows</LoadedBadge>}
        </CardLabelRow>
        <CardDescription>{source.description}</CardDescription>
      </CardHead>

      <DropZone
        $dragging={isDragging}
        $loaded={source.loaded}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") inputRef.current?.click(); }}
      >
        <DropIcon aria-hidden="true">↑</DropIcon>
        <DropCopy>
          {isDragging ? (
            <strong>Drop to upload</strong>
          ) : source.loaded ? (
            <>Drop a new file or click to replace</>
          ) : (
            <>Drop a CSV here or click to browse</>
          )}
        </DropCopy>
        <input
          type="file"
          accept=".csv,.xlsx,.xls"
          style={{ display: "none" }}
          onChange={handleInputChange}
          ref={inputRef}
        />
      </DropZone>

      <CardFooter>
        <TemplateLink href={templateDownloadUrl(source.kind)} download>
          ↓ Download CSV template
        </TemplateLink>
      </CardFooter>
    </CardWrap>
  );
}

// ─── Styled ───

const Main = styled.main`
  min-height: 100vh;
  background: ${t.color.canvas};
  animation: mlFadeIn ${t.motion.slow} ${t.motion.ease};
  position: relative;
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

const LoadingState = styled.div`
  padding: ${t.space[16]} 0;
  text-align: center;
  font-family: ${t.font.body};
  color: ${t.color.ink3};
`;

const ErrorBox = styled.div`
  padding: ${t.space[6]};
  background: ${t.color.negativeBg};
  border: 1px solid ${t.color.negative}33;
  border-radius: ${t.radius.md};
  color: ${t.color.negative};
  font-family: ${t.font.body};
`;

const GreetingSection = styled.section`
  margin-bottom: ${t.space[10]};
`;

const Greeting = styled.h1`
  font-family: ${t.font.serif};
  font-size: clamp(36px, 4.5vw, 56px);
  font-weight: ${t.weight.regular};
  line-height: 1.1;
  letter-spacing: ${t.tracking.tightest};
  color: ${t.color.ink};
  margin: 0 0 ${t.space[3]} 0;

  em {
    font-style: italic;
    color: ${t.color.accent};
    font-weight: ${t.weight.regular};
  }
`;

const NextStep = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.md};
  color: ${t.color.ink2};
  max-width: 640px;
  margin: 0;
  line-height: ${t.leading.relaxed};
`;

const StatsRow = styled.div`
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: ${t.space[3]};
  margin-bottom: ${t.space[10]};

  @media (max-width: 900px) {
    grid-template-columns: repeat(2, 1fr);
  }
`;

const StatCard = styled.div`
  padding: ${t.space[4]} ${t.space[5]};
  background: ${t.color.surface};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.md};
  box-shadow: ${t.shadow.card};
`;

const StatLabel = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink3};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  margin-bottom: ${t.space[1]};
`;

const StatValue = styled.div`
  font-family: ${t.font.serif};
  font-size: ${t.size["2xl"]};
  font-weight: ${t.weight.regular};
  letter-spacing: ${t.tracking.tight};
  color: ${({ $tone }) =>
    $tone === "positive" ? t.color.positive :
    $tone === "warning" ? t.color.warning :
    t.color.ink};
  line-height: 1.1;
`;

const StatSmall = styled.span`
  font-size: ${t.size.md};
  color: ${t.color.ink3};
`;

const StatSub = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
  margin-top: ${t.space[1]};
`;

const DataSection = styled.section`
  margin-bottom: ${t.space[10]};
`;

const SectionHead = styled.header`
  margin-bottom: ${t.space[5]};
  display: flex;
  flex-direction: column;
  gap: ${t.space[2]};
`;

const SectionTitle = styled.h2`
  font-family: ${t.font.serif};
  font-size: ${t.size.xl};
  font-weight: ${t.weight.regular};
  letter-spacing: ${t.tracking.tight};
  color: ${t.color.ink};
  margin: 0;
`;

const SectionCopy = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink3};
  line-height: ${t.leading.relaxed};
  margin: 0;
  max-width: 680px;
`;

const UploadGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: ${t.space[4]};

  @media (max-width: 900px) {
    grid-template-columns: 1fr;
  }
`;

const CardWrap = styled.div`
  background: ${t.color.surface};
  border: 1px solid ${({ $loaded }) => $loaded ? t.color.border : t.color.border};
  border-radius: ${t.radius.md};
  box-shadow: ${t.shadow.card};
  padding: ${t.space[5]} ${t.space[5]} ${t.space[4]};
  display: flex;
  flex-direction: column;
  gap: ${t.space[4]};
`;

const CardHead = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${t.space[2]};
`;

const CardLabelRow = styled.div`
  display: flex;
  align-items: center;
  gap: ${t.space[2]};
  flex-wrap: wrap;
`;

const CardLabel = styled.h3`
  font-family: ${t.font.body};
  font-size: ${t.size.md};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink};
  margin: 0;
  letter-spacing: ${t.tracking.tight};
`;

const RequiredBadge = styled.span`
  padding: 2px ${t.space[2]};
  background: ${t.color.accentSub};
  color: ${t.color.accentInk};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
`;

const LoadedBadge = styled.span`
  padding: 2px ${t.space[2]};
  background: ${t.color.positiveBg};
  color: ${t.color.positive};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
`;

const CardDescription = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink2};
  line-height: ${t.leading.normal};
  margin: 0;
`;

const DropZone = styled.div`
  position: relative;
  padding: ${t.space[7]} ${t.space[5]};
  background: ${({ $dragging }) => $dragging ? t.color.accentSub : t.color.sunken};
  border: 2px dashed ${({ $dragging }) => $dragging ? t.color.accent : t.color.border};
  border-radius: ${t.radius.md};
  text-align: center;
  cursor: pointer;
  transition: background ${t.motion.base} ${t.motion.ease},
              border-color ${t.motion.base} ${t.motion.ease};

  &:hover {
    background: ${t.color.accentSub};
    border-color: ${t.color.accent};
  }

  &:focus-visible {
    outline: 2px solid ${t.color.accent};
    outline-offset: 2px;
  }
`;

const DropIcon = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.xl};
  color: ${t.color.ink3};
  margin-bottom: ${t.space[2]};
  line-height: 1;
`;

const DropCopy = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink2};

  strong {
    font-weight: ${t.weight.semibold};
    color: ${t.color.accent};
  }
`;

const CardFooter = styled.div`
  display: flex;
  justify-content: flex-end;
  padding-top: ${t.space[2]};
  border-top: 1px solid ${t.color.borderFaint};
`;

const TemplateLink = styled.a`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.medium};
  color: ${t.color.accent};
  text-decoration: none;

  &:hover {
    color: ${t.color.accentHover};
    text-decoration: underline;
  }
`;

const RunAnalysisRow = styled.section`
  padding: ${t.space[5]} ${t.space[6]};
  background: ${t.color.dark};
  border-radius: ${t.radius.lg};
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: ${t.space[5]};
  flex-wrap: wrap;
`;

const RunCopy = styled.div`
  flex: 1;
  min-width: 280px;
`;

const RunTitle = styled.div`
  font-family: ${t.font.serif};
  font-size: ${t.size.xl};
  font-weight: ${t.weight.regular};
  color: ${t.color.inkInverse};
  letter-spacing: ${t.tracking.tight};
  margin-bottom: ${t.space[1]};
`;

const RunSub = styled.div`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink4};
  line-height: ${t.leading.relaxed};
`;

const RunButton = styled.button`
  padding: ${t.space[3]} ${t.space[6]};
  background: ${t.color.accent};
  color: ${t.color.inkInverse};
  border: none;
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.semibold};
  cursor: pointer;
  transition: background ${t.motion.base} ${t.motion.ease};

  &:hover:not(:disabled) {
    background: ${t.color.accentHover};
  }

  &:disabled {
    opacity: 0.6;
    cursor: wait;
  }
`;

const ToastCard = styled.div`
  position: fixed;
  bottom: ${t.space[6]};
  right: ${t.space[6]};
  max-width: 440px;
  padding: ${t.space[4]} ${t.space[5]};
  background: ${({ $kind }) =>
    $kind === "success" ? t.color.positiveBg :
    $kind === "error" ? t.color.negativeBg :
    t.color.surface};
  border: 1px solid ${({ $kind }) =>
    $kind === "success" ? `${t.color.positive}33` :
    $kind === "error" ? `${t.color.negative}33` :
    t.color.border};
  border-radius: ${t.radius.md};
  box-shadow: ${t.shadow.modal};
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${({ $kind }) =>
    $kind === "success" ? t.color.positive :
    $kind === "error" ? t.color.negative :
    t.color.ink};
  z-index: ${t.z.toast};
  animation: mlFadeIn ${t.motion.base} ${t.motion.ease};
`;
