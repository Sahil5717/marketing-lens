import { useState, useEffect, useCallback, Suspense, lazy } from "react";
import { tokens as t } from "./tokens.js";
import {
  ensureDiagnosisReady,
  ensurePlanReady,
  ensureScenarioReady,
  ensureChannelDetailReady,
  ensureMarketContextReady,
  saveCommentary,
  deleteCommentary,
  suppressFinding,
  unsuppressFinding,
  getStoredAuth,
  setUnauthorizedHandler,
  logout,
  fetchEngagements,
  fetchBayesStatus,
  refitBayes,
} from "./api.js";
import { Diagnosis } from "./screens/Diagnosis.jsx";
import { Plan } from "./screens/Plan.jsx";
import { Scenarios } from "./screens/Scenarios.jsx";
import { AnalystHub } from "./screens/AnalystHub.jsx";
import { MarketContext } from "./screens/MarketContext.jsx";
import { Engagements } from "./screens/Engagements.jsx";
// Lazy-load ChannelDetail + Recharts — see DiagnosisApp for rationale.
const ChannelDetail = lazy(() =>
  import("./screens/ChannelDetail.jsx").then((m) => ({ default: m.ChannelDetail }))
);
import { SuppressionModal } from "./components/SuppressionModal.jsx";
import { CommentaryModal } from "./components/CommentaryModal.jsx";
import { Toast } from "./components/Toast.jsx";
import { GlobalStyle } from "./globalStyle.js";
import { AppHeader } from "./ui/AppHeader.jsx";

/**
 * EditorApp — EY-mode shell for MarketLens.
 *
 * Auth guard (v18e): this shell REQUIRES an `editor` role specifically.
 * A client-role user accessing /editor is redirected to / (the client
 * view) rather than /login — they're authenticated, just not authorized
 * for this surface. Unauthenticated users go to /login.
 *
 * [...]
 */
function getScreenFromUrl() {
  if (typeof window === "undefined") return "diagnosis";
  const params = new URLSearchParams(window.location.search);
  const s = params.get("screen");
  if (s === "hub" || s === "tools" || s === "dashboard") return "hub";
  if (s === "engagements" || s === "engagement") return "engagements";
  if (s === "plan") return "plan";
  if (s === "scenarios") return "scenarios";
  if (s === "channels" || s === "channel") return "channels";
  if (s === "market" || s === "market-context") return "market";
  return "diagnosis";
}

function getChannelFromUrl() {
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  return params.get("channel");
}

function redirectToLogin() {
  if (typeof window !== "undefined") window.location.href = "/login";
}

function redirectToClient() {
  if (typeof window !== "undefined") window.location.href = "/";
}

export default function EditorApp() {
  const screen = getScreenFromUrl();
  const [state, setState] = useState({ status: "loading", data: null, error: null });
  const [suppressTarget, setSuppressTarget] = useState(null);
  const [commentaryTarget, setCommentaryTarget] = useState(null);
  const [toast, setToast] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [auth, setAuth] = useState(null);
  // Active engagement meta for the header chip. Fetched once on mount
  // and refreshed after the Engagements screen switches active. If the
  // fetch fails (demo backend not ready yet), fall back to default copy.
  const [activeEngagement, setActiveEngagement] = useState(null);
  // Bayesian MMM status (polled). The chip in AppHeader shows this live.
  // Null until first fetch. See the polling useEffect below for semantics.
  const [bayesStatus, setBayesStatus] = useState(null);

  const reload = useCallback(async () => {
    // Hub and Engagements manage their own state — they don't need the
    // full analysis pipeline to render.
    if (screen === "hub" || screen === "engagements") {
      setState({ status: "ready", data: null, error: null });
      return;
    }
    let dataResult;
    if (screen === "channels") {
      const channelSlug = getChannelFromUrl();
      dataResult = await ensureChannelDetailReady(channelSlug);
    } else if (screen === "market") {
      dataResult = await ensureMarketContextReady();
    } else {
      const loader =
        screen === "plan" ? ensurePlanReady :
        screen === "scenarios" ? ensureScenarioReady :
        ensureDiagnosisReady;
      dataResult = await loader("editor");
    }
    const { data, error } = dataResult;
    if (data) {
      setState({ status: "ready", data, error: null });
    } else {
      setState({ status: "error", data: null, error });
    }
  }, [screen]);

  useEffect(() => {
    // Auth guard: editor shell requires `editor` role specifically.
    // Unauthenticated → /login. Authenticated as client → / (the
    // client view, where they belong). Authenticated as editor → boot.
    const stored = getStoredAuth();
    if (!stored?.token) {
      redirectToLogin();
      return;
    }
    if (stored.role !== "editor") {
      redirectToClient();
      return;
    }
    setAuth(stored);
    setUnauthorizedHandler(redirectToLogin);
    reload();

    // Fetch active engagement for the header chip. Runs once on mount
    // (re-runs when user comes back from the Engagements screen since
    // screen is a dep). Failure is non-fatal — header falls back to
    // default copy.
    fetchEngagements().then(({ data }) => {
      if (!data) return;
      const active = (data.engagements || []).find(
        (e) => e.id === data.active_engagement_id
      );
      if (active) setActiveEngagement(active);
    });
  }, [reload, screen]);

  // Bayesian MMM status polling. Fast polls (5s) while pending/running,
  // slow polls (30s) otherwise. Separate from screen-change effects so
  // the chip keeps pulsing across navigation.
  useEffect(() => {
    // Kick an immediate fetch on mount so the chip hydrates without
    // waiting for the first interval tick.
    let cancelled = false;
    const poll = async () => {
      const { data } = await fetchBayesStatus();
      if (!cancelled && data) {
        setBayesStatus(data);
      }
    };
    poll();

    // Adaptive interval: bayesStatus.state drives speed.
    const currentState = bayesStatus?.state;
    const isActive = currentState === "pending" || currentState === "running" || currentState == null;
    const intervalMs = isActive ? 5000 : 30000;

    const id = setInterval(poll, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [bayesStatus?.state]);

  // Manual Bayesian refresh handler (bound to the chip's click when ready)
  const handleBayesRefresh = useCallback(async () => {
    const { data } = await refitBayes();
    if (data) setBayesStatus(data);
  }, []);

  // ── Editor action handlers ──
  //
  // Each handler: sets submitting, calls the API, shows a toast on the
  // outcome, reloads the diagnosis (so the updated override is visible),
  // and resets submitting. On errors we return the error up to the
  // calling component (commentary editor, suppression modal) so they can
  // surface it inline without losing the user's unsaved input.

  async function handleSaveCommentary(findingKey, text) {
    setSubmitting(true);
    const { error } = await saveCommentary(findingKey, text, "ey.editor");
    setSubmitting(false);
    if (error) {
      setToast({ message: error.message || "Couldn't save commentary", kind: "error" });
      return { error };
    }
    setToast({ message: "Commentary saved", kind: "success" });
    await reload();
    return { ok: true };
  }

  async function handleDeleteCommentary(findingKey) {
    setSubmitting(true);
    const { error } = await deleteCommentary(findingKey, "ey.editor");
    setSubmitting(false);
    if (error) {
      setToast({ message: error.message || "Couldn't delete commentary", kind: "error" });
      return { error };
    }
    setToast({ message: "Commentary removed", kind: "success" });
    await reload();
    return { ok: true };
  }

  async function handleConfirmSuppress(reason) {
    if (!suppressTarget) return { error: "No target" };
    setSubmitting(true);
    const { error } = await suppressFinding(suppressTarget.key, reason, "ey.editor");
    setSubmitting(false);
    if (error) {
      setToast({ message: error.message || "Couldn't hide finding", kind: "error" });
      return { error };
    }
    setSuppressTarget(null);
    setToast({ message: "Finding hidden from client view", kind: "success" });
    await reload();
    return { ok: true };
  }

  async function handleUnsuppress(findingKey) {
    setSubmitting(true);
    const { error } = await unsuppressFinding(findingKey, "ey.editor");
    setSubmitting(false);
    if (error) {
      setToast({ message: error.message || "Couldn't restore finding", kind: "error" });
      return { error };
    }
    setToast({ message: "Finding restored to client view", kind: "success" });
    await reload();
    return { ok: true };
  }

  const counts = state.data?.ey_overrides?.counts;
  // Unified suppress toggle — Diagnosis/Plan call onSuppressToggle(f)
  // regardless of current state. Dispatch based on whether f is
  // already suppressed.
  function handleSuppressToggle(target) {
    if (target?.suppressed) {
      // Unsuppress is one-click — no modal needed since it's restorative
      handleUnsuppress(target.key);
    } else {
      // Suppress requires a reason — open modal
      setSuppressTarget(target);
    }
  }

  // Commentary edit entry point — opens the modal
  function handleCommentaryEdit(target) {
    setCommentaryTarget(target);
  }

  // Shared editor-callback props — prop names match what Diagnosis and
  // Plan expect (onCommentaryEdit, onSuppressToggle). Internal handler
  // names in this file stay descriptive (handleSaveCommentary etc).
  const editorProps = {
    editorMode: true,
    onCommentaryEdit: handleCommentaryEdit,
    onSuppressToggle: handleSuppressToggle,
  };

  // While auth check is resolving (or redirect in flight), render nothing.
  // Avoids a flash of editor chrome before the redirect lands.
  if (!auth) return null;

  return (
    <div style={{ minHeight: "100vh", background: t.color.canvas, fontFamily: t.font.body }}>
      <GlobalStyle />
      <AppHeader
        currentScreen={screen}
        auth={auth}
        editorMode={true}
        engagementMeta={
          activeEngagement
            ? {
                client: activeEngagement.client,
                period: activeEngagement.period,
                updated: activeEngagement.last_updated || "",
              }
            : { client: "Acme Retail", period: "FY 2025", updated: "" }
        }
        bayesStatus={bayesStatus}
        onBayesRefresh={handleBayesRefresh}
        onSignOut={() => { logout(); redirectToLogin(); }}
        onShare={() => {
          const url = window.location.href;
          if (navigator.clipboard) {
            navigator.clipboard.writeText(url).then(
              () => setToast({ message: "Link copied to clipboard.", kind: "success" }),
              () => setToast({ message: `Copy failed. URL: ${url}`, kind: "error" })
            );
          } else {
            setToast({ message: `URL: ${url}`, kind: "info" });
          }
        }}
      />

      {state.status === "loading" && <LoadingView />}
      {state.status === "error" && <ErrorView error={state.error} />}
      {state.status === "ready" && screen === "diagnosis" && (
        <Diagnosis data={state.data} {...editorProps} />
      )}
      {state.status === "ready" && screen === "plan" && (
        <Plan data={state.data} {...editorProps} />
      )}
      {state.status === "ready" && screen === "scenarios" && (
        <Scenarios data={state.data} view="editor" />
      )}
      {state.status === "ready" && screen === "hub" && (
        <AnalystHub onAnalysisComplete={() => reload()} />
      )}
      {state.status === "ready" && screen === "engagements" && (
        <Engagements
          onNavigateToWorkspace={() => {
            window.location.search = "?screen=hub";
          }}
        />
      )}
      {state.status === "ready" && screen === "channels" && (
        <Suspense fallback={<LoadingView />}>
          <ChannelDetail data={state.data} />
        </Suspense>
      )}
      {state.status === "ready" && screen === "market" && (
        <MarketContext data={state.data} />
      )}

      <Footer />

      {suppressTarget && (
        <SuppressionModal
          finding={suppressTarget}
          onConfirm={handleConfirmSuppress}
          onCancel={() => setSuppressTarget(null)}
          submitting={submitting}
        />
      )}

      {commentaryTarget && (
        <CommentaryModal
          target={commentaryTarget}
          existingText={commentaryTarget.ey_commentary || commentaryTarget.commentary || ""}
          onSave={async (text) => {
            const result = await handleSaveCommentary(commentaryTarget.key, text);
            if (result?.ok) setCommentaryTarget(null);
            return result;
          }}
          onDelete={async () => {
            const result = await handleDeleteCommentary(commentaryTarget.key);
            if (result?.ok) setCommentaryTarget(null);
            return result;
          }}
          onCancel={() => setCommentaryTarget(null)}
          submitting={submitting}
        />
      )}

      {toast && (
        <Toast
          message={toast.message}
          kind={toast.kind}
          onDismiss={() => setToast(null)}
        />
      )}
    </div>
  );
}

/**
 * EditorHeader — distinct, unambiguously editor-mode.
 *
 * Uses a darker-than-canvas background band with an accent left border so
 * at-a-glance scanning tells you which mode you're in. The "EY Editor"
 * pill and override counts make the mode status persistent — a user who
 * tabs away and comes back instantly sees "I'm editing, and I have X
 * overrides in place."
 *
 * The "Preview as Client" link doesn't do a mode switch inside this app —
 * it opens the client entry point in a new tab. That's deliberate: a
 * single-page mode toggle risks accidentally publishing unsaved edits
 * or confusing the author about which surface they're in.
 */
function Footer() {
  return (
    <footer
      style={{
        maxWidth: t.layout.gridWidth,
        margin: "0 auto",
        padding: `${t.space[12]} ${t.space[8]}`,
        borderTop: `1px solid ${t.color.borderFaint}`,
        fontFamily: t.font.body,
        fontSize: t.size.xs,
        color: t.color.textTertiary,
        textAlign: "center",
      }}
    >
      EY Editor · Edits are saved immediately and visible to the client view. Draft / publish workflow lands in a later release.
    </footer>
  );
}

function LoadingView() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: `${t.space[24]} ${t.space[8]}`,
        gap: t.space[6],
      }}
    >
      <div
        style={{
          width: "28px",
          height: "28px",
          border: `2px solid ${t.color.border}`,
          borderTopColor: t.color.accent,
          borderRadius: "50%",
          animation: "spin 700ms linear infinite",
        }}
      />
      <div
        style={{
          fontFamily: t.font.body,
          fontSize: t.size.sm,
          color: t.color.textSecondary,
          textAlign: "center",
          maxWidth: "360px",
          lineHeight: t.leading.normal,
        }}
      >
        Loading the diagnosis and any saved EY overrides…
      </div>
    </div>
  );
}

function ErrorView({ error }) {
  const isNetwork = error?.kind === "network";
  return (
    <div
      style={{
        maxWidth: "560px",
        margin: `${t.space[20]} auto`,
        padding: `${t.space[8]} ${t.space[8]}`,
        background: t.color.surface,
        border: `1px solid ${t.color.border}`,
        borderLeft: `3px solid ${t.color.warning}`,
        borderRadius: t.radius.md,
        boxShadow: t.shadow.card,
      }}
    >
      <div
        style={{
          fontFamily: t.font.body,
          fontSize: t.size.xs,
          fontWeight: t.weight.semibold,
          color: t.color.warning,
          textTransform: "uppercase",
          letterSpacing: t.tracking.wider,
          marginBottom: t.space[3],
        }}
      >
        {isNetwork ? "Connection issue" : "Couldn't load editor"}
      </div>
      <p
        style={{
          fontFamily: t.font.body,
          fontSize: t.size.md,
          color: t.color.textPrimary,
          lineHeight: t.leading.relaxed,
          margin: 0,
        }}
      >
        {isNetwork
          ? "MarketLens couldn't reach the analysis server. Verify the backend is running and try again."
          : error?.message || "An unexpected error occurred."}
      </p>
    </div>
  );
}
