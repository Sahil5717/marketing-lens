import { useState, useEffect, Suspense, lazy } from "react";
import { tokens as t } from "./tokens.js";
import { ensureDiagnosisReady, ensurePlanReady, ensureScenarioReady, ensureChannelDetailReady, ensureMarketContextReady, getStoredAuth, setUnauthorizedHandler, logout } from "./api.js";
import { Diagnosis } from "./screens/Diagnosis.jsx";
import { Plan } from "./screens/Plan.jsx";
import { Scenarios } from "./screens/Scenarios.jsx";
import { MarketContext } from "./screens/MarketContext.jsx";
// ChannelDetail is lazy-loaded to keep Recharts (~350KB) out of the
// main bundle. Most users land on Diagnosis and never touch Channels
// on a first session; no reason to pay for the chart library upfront.
const ChannelDetail = lazy(() =>
  import("./screens/ChannelDetail.jsx").then((m) => ({ default: m.ChannelDetail }))
);
import { GlobalStyle } from "./globalStyle.js";
import { AppHeader } from "./ui/AppHeader.jsx";

/**
 * DiagnosisApp — client-mode shell for MarketLens.
 *
 * Loads the published diagnosis (with any EY edits already layered in by
 * the backend when it receives view=client) and renders it read-only.
 * No editor affordances, no mutation endpoints ever called. A client
 * view cannot accidentally edit anything because it has no edit handlers
 * to pass to the screen.
 *
 * Auth guard (v18e): on mount, checks localStorage for a valid auth
 * token. If none exists, redirects to /login. Both `editor` and `client`
 * roles are permitted to view this shell — editors use it for preview.
 * If the backend ever returns 401 (expired token, revoked user), the
 * api layer clears storage and triggers a redirect via the handler
 * registered in setUnauthorizedHandler.
 *
 * Screen routing: reads ?screen= from the URL. Values: "diagnosis"
 * (default), "plan".
 *
 * For the EY-facing editor version, see EditorApp.jsx.
 */
function getScreenFromUrl() {
  if (typeof window === "undefined") return "diagnosis";
  const params = new URLSearchParams(window.location.search);
  const s = params.get("screen");
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
  if (typeof window !== "undefined") {
    // Preserve the intended screen as a post-login hint, wire-in later
    window.location.href = "/login";
  }
}

export default function DiagnosisApp() {
  const screen = getScreenFromUrl();
  const [state, setState] = useState({ status: "loading", data: null, error: null });
  const [auth, setAuth] = useState(null);

  useEffect(() => {
    // Auth guard: require any valid token. Both editor and client roles
    // are allowed on this shell (editor uses it for "Preview as client").
    const stored = getStoredAuth();
    if (!stored?.token) {
      redirectToLogin();
      return;
    }
    setAuth(stored);

    // Register 401 handler so expired-token responses redirect cleanly
    setUnauthorizedHandler(redirectToLogin);

    (async () => {
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
        dataResult = await loader("client");
      }
      const { data, error } = dataResult;
      if (data) {
        setState({ status: "ready", data, error: null });
      } else {
        setState({ status: "error", data: null, error });
      }
    })();
  }, [screen]);

  // While redirecting, render nothing (avoids a flash of the shell chrome
  // before window.location.href takes effect).
  if (!auth) return null;

  return (
    <div style={{ minHeight: "100vh", background: t.color.canvas, fontFamily: t.font.body }}>
      <GlobalStyle />
      <AppHeader
        currentScreen={screen}
        auth={auth}
        engagementMeta={{ client: "Acme Retail", period: "FY 2025", updated: "12 Apr 2026" }}
        onSignOut={() => { logout(); redirectToLogin(); }}
        onShare={() => {
          // Simple "copy current URL to clipboard" — the v1 Share action.
          // Full shareable snapshot links with permissions are post-v1.
          const url = window.location.href;
          if (navigator.clipboard) {
            navigator.clipboard.writeText(url).then(
              () => alert("Link copied to clipboard."),
              () => alert(`Copy failed. URL: ${url}`)
            );
          } else {
            alert(`URL: ${url}`);
          }
        }}
      />

      {state.status === "loading" && <LoadingView />}
      {state.status === "error" && <ErrorView error={state.error} />}
      {state.status === "ready" && screen === "diagnosis" && (
        <Diagnosis data={state.data} editorMode={false} />
      )}
      {state.status === "ready" && screen === "plan" && (
        <Plan data={state.data} editorMode={false} />
      )}
      {state.status === "ready" && screen === "scenarios" && (
        <Scenarios data={state.data} view="client" />
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
    </div>
  );
}

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
      MarketLens · All estimates are directional; validate with incrementality tests before major commits.
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
        Running your analysis. This may take a moment on first load while the models fit.
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
        {isNetwork ? "Connection issue" : "Couldn't load analysis"}
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

