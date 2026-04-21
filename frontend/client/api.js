/**
 * MarketLens API client.
 *
 * Thin fetch wrapper around the backend. Lives separately from the existing
 * analyst app's API layer so the two don't accidentally share assumptions
 * (the client app has stricter error UX -- we can't just console.warn and
 * render a half-broken screen in front of a Partner).
 *
 * Conventions:
 * - All calls are async, return { data, error } rather than throwing.
 * - Error states carry a human-readable message suitable for UI display.
 * - Network errors and HTTP errors are reported distinctly so the UI can
 *   differentiate "can't reach server" vs "server returned 400."
 *
 * Auth (v18e): every request attaches the stored JWT as
 * `Authorization: Bearer <token>` if a token is present. Token lives in
 * localStorage under `marketlens:auth:v1` as a JSON blob with
 * { token, username, role, expiresAt }. A 401 response anywhere clears
 * the token and (via a pluggable onUnauthorized callback set by the app
 * shell) redirects to /login. A 403 indicates wrong role — surfaced as a
 * normal error, not a logout trigger, because the token is still valid.
 */

const API_BASE = "/api";
const AUTH_STORAGE_KEY = "marketlens:auth:v1";

// The app shell sets this callback (see DiagnosisApp / EditorApp / LoginApp)
// so api.js can trigger a redirect to /login without knowing about React
// routing. Kept as a simple module-level variable rather than a more
// elaborate event bus; there's one React tree at a time.
let _onUnauthorized = null;

export function setUnauthorizedHandler(fn) {
  _onUnauthorized = fn;
}

// ─── Auth token storage ───
//
// localStorage is intentionally used rather than sessionStorage: a pitch
// demo often involves showing the tool, closing the tab, coming back a
// few minutes later. Keeping the token in localStorage survives that.
// The JWT has a 24-hour expiry enforced server-side regardless.

export function getStoredAuth() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    // Don't hand back clearly expired tokens; treat as no auth.
    if (parsed.expiresAt && parsed.expiresAt < Date.now()) {
      clearStoredAuth();
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function setStoredAuth(auth) {
  // auth = { token, username, role }  — we add expiresAt client-side as
  // a best-effort (23h window; server enforces the real 24h expiry)
  const enriched = { ...auth, expiresAt: Date.now() + 23 * 60 * 60 * 1000 };
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(enriched));
}

export function clearStoredAuth() {
  localStorage.removeItem(AUTH_STORAGE_KEY);
}

async function apiRequest(endpoint, options = {}) {
  const auth = getStoredAuth();
  const headers = {
    "Content-Type": "application/json",
    ...(auth?.token ? { Authorization: `Bearer ${auth.token}` } : {}),
    ...options.headers,
  };
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
    if (!res.ok) {
      let detail = `Request failed with status ${res.status}`;
      try {
        const body = await res.json();
        if (body.detail) detail = body.detail;
      } catch {
        // Response wasn't JSON. Stick with the status-code message.
      }
      // 401 → token missing/expired/invalid. Clear local auth and notify
      // the app shell (which will redirect to /login).
      if (res.status === 401) {
        clearStoredAuth();
        if (_onUnauthorized) _onUnauthorized();
      }
      return { data: null, error: { kind: "http", status: res.status, message: detail } };
    }
    const data = await res.json();
    return { data, error: null };
  } catch (e) {
    return {
      data: null,
      error: { kind: "network", message: e.message || "Network error" },
    };
  }
}

// ─── Auth endpoints ───

export async function fetchDemoUsers() {
  return apiRequest("/auth/demo-users");
}

export async function login(username, password) {
  const result = await apiRequest("/auth/login-v2", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  if (result.data) {
    setStoredAuth({
      token: result.data.token,
      username: result.data.username,
      role: result.data.role,
    });
  }
  return result;
}

export function logout() {
  clearStoredAuth();
  if (_onUnauthorized) _onUnauthorized();
}

export async function fetchDiagnosis(view = "client") {
  return apiRequest(`/diagnosis?view=${encodeURIComponent(view)}`);
}

/**
 * Fetch the Plan screen payload. Like fetchDiagnosis, supports view switching.
 *
 * Optional params:
 *   totalBudget — if provided, re-optimizes at this budget before returning
 *     the plan. If omitted, the backend picks a sensible default (current
 *     spend + 5%). This matters because the Plan is the action-side of the
 *     diagnosis: there's always an implicit "at what budget level?" question,
 *     and leaving it implicit on first load is the right default.
 *   objective — optimizer objective ("balanced" | "max_revenue" | "max_roi").
 *     Defaults to "balanced" which the backend understands.
 */
export async function fetchPlan(view = "client", opts = {}) {
  const params = new URLSearchParams({ view });
  if (opts.totalBudget != null) params.set("total_budget", String(opts.totalBudget));
  if (opts.objective) params.set("objective", opts.objective);
  return apiRequest(`/plan?${params.toString()}`);
}

export async function loadMockData() {
  return apiRequest("/load-mock-data", { method: "POST" });
}

export async function runAnalysis() {
  return apiRequest("/run-analysis", { method: "POST" });
}

// ─── Editor overlay endpoints ───
//
// These mutate state in the persistence layer. Only the editor entry
// point calls them; the client app never does. No auth yet — the split
// relies on the editor entry point being the only caller.

export async function saveCommentary(findingKey, text, author = null) {
  return apiRequest("/editor/commentary", {
    method: "POST",
    body: JSON.stringify({ finding_key: findingKey, text, author }),
  });
}

export async function deleteCommentary(findingKey, author = null) {
  const qs = author ? `?author=${encodeURIComponent(author)}` : "";
  return apiRequest(
    `/editor/commentary/${encodeURIComponent(findingKey)}${qs}`,
    { method: "DELETE" },
  );
}

export async function suppressFinding(findingKey, reason, author = null) {
  return apiRequest("/editor/suppress", {
    method: "POST",
    body: JSON.stringify({ finding_key: findingKey, reason, author }),
  });
}

export async function unsuppressFinding(findingKey, author = null) {
  const qs = author ? `?author=${encodeURIComponent(author)}` : "";
  return apiRequest(
    `/editor/suppress/${encodeURIComponent(findingKey)}${qs}`,
    { method: "DELETE" },
  );
}

export async function fetchAuditLog(limit = 50) {
  return apiRequest(`/editor/audit-log?limit=${limit}`);
}

/**
 * Combined "cold-start" helper: ensures mock data is loaded and analysis
 * has run, then fetches the diagnosis. Used when the client app boots
 * against a fresh backend (e.g., a dev environment or a demo deploy that
 * doesn't have a persisted analysis yet).
 *
 * In the real product, data loading happens on the EY-editor side before
 * the client ever sees the surface; the client-side fetchDiagnosis() call
 * alone is sufficient.
 */
export async function ensureDiagnosisReady(view = "client") {
  // Try diagnosis first — if it works, no cold-start needed.
  let { data, error } = await fetchDiagnosis(view);
  if (data) return { data, error: null };

  // Diagnosis failed because analysis hasn't run. Cold-start.
  if (error && error.kind === "http" && error.status === 400) {
    const mock = await loadMockData();
    if (mock.error) return { data: null, error: mock.error };
    const analysis = await runAnalysis();
    if (analysis.error) return { data: null, error: analysis.error };
    return await fetchDiagnosis(view);
  }

  return { data: null, error };
}

/**
 * Plan screen equivalent of ensureDiagnosisReady. Handles the same
 * cold-start path (load mock → run analysis → retry) and passes through
 * budget/objective opts to fetchPlan.
 */
export async function ensurePlanReady(view = "client", opts = {}) {
  let { data, error } = await fetchPlan(view, opts);
  if (data) return { data, error: null };

  if (error && error.kind === "http" && error.status === 400) {
    const mock = await loadMockData();
    if (mock.error) return { data: null, error: mock.error };
    const analysis = await runAnalysis();
    if (analysis.error) return { data: null, error: analysis.error };
    return await fetchPlan(view, opts);
  }

  return { data: null, error };
}

// ─── Scenarios screen ───

/**
 * Fetch the list of scenario presets the backend offers (Current,
 * Cut 20%, Increase 25%, Optimizer recommended). Computed dynamically
 * from current spend, so they always make sense for whatever data is
 * loaded.
 */
export async function fetchScenarioPresets() {
  return apiRequest("/scenario/presets");
}

/**
 * Fetch a scenario at a specific budget level. Returns the same payload
 * shape as fetchPlan plus a `comparison` block (scenario vs. baseline).
 */
export async function fetchScenario(opts = {}) {
  const params = new URLSearchParams();
  if (opts.totalBudget != null) params.set("total_budget", String(opts.totalBudget));
  if (opts.objective) params.set("objective", opts.objective);
  if (opts.view) params.set("view", opts.view);
  return apiRequest(`/scenario?${params.toString()}`);
}

/**
 * Cold-start variant: ensure analysis has run, fetch the current-spend
 * baseline scenario as the screen's initial state. Subsequent preset
 * clicks call fetchScenario directly.
 */
export async function ensureScenarioReady(view = "client", opts = {}) {
  let { data, error } = await fetchScenario({ ...opts, view });
  if (data) return { data, error: null };

  if (error && error.kind === "http" && error.status === 400) {
    const mock = await loadMockData();
    if (mock.error) return { data: null, error: mock.error };
    const analysis = await runAnalysis();
    if (analysis.error) return { data: null, error: analysis.error };
    return await fetchScenario({ ...opts, view });
  }

  return { data: null, error };
}

// ─── Market Context screen ───

/**
 * Fetch full market-context payload (events, trends, competitive).
 */
export async function fetchMarketContext() {
  return apiRequest("/market-context");
}

/**
 * Cold-start variant — ensures analysis has run, then fetches market
 * context. Safe to call before any external data is uploaded; the
 * backend returns empty sections with a helpful headline.
 */
export async function ensureMarketContextReady() {
  const { data, error } = await fetchMarketContext();
  if (data) return { data, error: null };
  if (error && error.kind === "http" && error.status === 400) {
    const mock = await loadMockData();
    if (mock.error) return { data: null, error: mock.error };
    const analysis = await runAnalysis();
    if (analysis.error) return { data: null, error: analysis.error };
    return await fetchMarketContext();
  }
  return { data: null, error };
}

// ─── Market adjustments (Week 7) ───

/**
 * Fetch the current market adjustments overlay for the Plan screen.
 * Returns { data: {adjustments, baseline_total_revenue_delta,
 * adjusted_total_revenue_delta, summary}, error }.
 *
 * `summary.has_market_data` is false when no external data was uploaded.
 * UI should hide the section in that case.
 */
export async function fetchMarketAdjustments() {
  return apiRequest("/market-adjustments");
}

/**
 * Fetch market adjustments for a specific scenario budget. Unlike the
 * plain /market-adjustments endpoint (which uses the default plan),
 * this computes adjustments for the scenario's specific budget — so
 * changing presets on the Scenarios screen surfaces different moves
 * and different adjustment magnitudes.
 */
export async function fetchScenarioMarketAdjustments({ totalBudget, objective } = {}) {
  const q = new URLSearchParams();
  if (totalBudget != null) q.set("total_budget", String(totalBudget));
  if (objective) q.set("objective", objective);
  const suffix = q.toString() ? `?${q.toString()}` : "";
  return apiRequest(`/market-adjustments/scenario${suffix}`);
}

/**
 * Toggle a single adjustment on/off. Editor-only.
 */
export async function overrideMarketAdjustment(adjustmentId, applied) {
  return apiRequest("/market-adjustments/override", {
    method: "POST",
    body: JSON.stringify({ adjustment_id: adjustmentId, applied }),
  });
}

// ─── Bayesian MMM ───

/**
 * Fetch the current Bayesian fit lifecycle state. Safe to poll.
 * Returns { data: { state, started_at, finished_at, elapsed_s, r_hat_max,
 * ess_min, n_channels, message }, error }.
 *
 * `state` is one of: "idle", "pending", "running", "ready", "failed",
 * "non_converged". UI should show a spinner chip while pending/running,
 * an error note for failed/non_converged, and live HDI data for ready.
 */
export async function fetchBayesStatus() {
  return apiRequest("/bayes-status");
}

/**
 * Fetch the full Bayesian fit result. Only succeeds when state=="ready".
 * Returns { data: { method, contributions, model_diagnostics, ... }, error }.
 *
 * Each contribution carries: contribution, contribution_hdi_90,
 * mmm_roas, mmm_roas_hdi_90, decay_mean, half_saturation, confidence.
 */
export async function fetchBayesResult() {
  return apiRequest("/bayes-result");
}

/**
 * Trigger a fresh Bayesian fit. No-op if one is already running.
 */
export async function refitBayes() {
  return apiRequest("/bayes-refit", { method: "POST" });
}

// ─── Engagements ───

/**
 * List engagements. Returns { data: { engagements, active_engagement_id }, error }.
 */
export async function fetchEngagements() {
  return apiRequest("/engagements");
}

/**
 * Create an engagement. Payload: { client, engagement_name, period, status?, owner?, summary? }.
 */
export async function createEngagement(payload) {
  return apiRequest("/engagements", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

/**
 * Delete an engagement. Backend rejects deletion of the active one.
 */
export async function deleteEngagement(engagementId) {
  return apiRequest(`/engagements/${encodeURIComponent(engagementId)}`, {
    method: "DELETE",
  });
}

/**
 * Set an engagement as active.
 */
export async function activateEngagement(engagementId) {
  return apiRequest(`/engagements/${encodeURIComponent(engagementId)}/activate`, {
    method: "POST",
  });
}

// ─── Analyst Tools Hub screen ───
/**
 * Fetch the analyst-status payload: what data sources are loaded, how
 * many rows each, next-step hint, KPI stats for the dashboard cards.
 */
export async function fetchAnalystStatus() {
  return apiRequest("/analyst-status");
}

/**
 * Upload a CSV file to the specified data endpoint.
 * kind values map to the five upload endpoints:
 *   - "campaign"     → /api/upload
 *   - "journeys"     → /api/upload-journeys
 *   - "competitive"  → /api/upload-competitive
 *   - "events"       → /api/upload-events
 *   - "trends"       → /api/upload-trends
 *
 * Returns { data: {filename, rows, ...}, error } — the shape matches
 * what the upload endpoints return so the UI can show a summary
 * (filename, row count, validation warnings).
 */
export async function uploadDataFile(kind, file) {
  const endpointMap = {
    campaign:    "/upload",
    journeys:    "/upload-journeys",
    competitive: "/upload-competitive",
    events:      "/upload-events",
    trends:      "/upload-trends",
  };
  const path = endpointMap[kind];
  if (!path) {
    return {
      data: null,
      error: { kind: "client", message: `Unknown upload kind: ${kind}` },
    };
  }

  const form = new FormData();
  form.append("file", file);

  try {
    const auth = getStoredAuth();
    const headers = {};
    if (auth?.token) headers.Authorization = `Bearer ${auth.token}`;

    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      body: form,
      headers,
    });
    if (!res.ok) {
      const text = await res.text();
      return {
        data: null,
        error: { kind: "http", status: res.status, message: text || `${res.status}` },
      };
    }
    return { data: await res.json(), error: null };
  } catch (err) {
    return {
      data: null,
      error: { kind: "network", message: err?.message || "Upload failed" },
    };
  }
}

/**
 * URL to download a template CSV for a given data kind. Used as the
 * href on the "Download template" link in the Upload UI.
 */
export function templateDownloadUrl(kind) {
  return `${API_BASE}/download-template?kind=${encodeURIComponent(kind)}`;
}

/**
 * Kick off a fresh analysis run. Called after the analyst uploads new
 * data to refresh all screens.
 */
export async function runFullAnalysis() {
  return apiRequest("/run-analysis", { method: "POST" });
}

export async function ensureAnalystHubReady() {
  const { data, error } = await fetchAnalystStatus();
  if (data) return { data, error: null };
  return { data: null, error };
}

// ─── Channel Detail screen ───

/**
 * Fetch the list of channels with current/optimal spend + action.
 * Powers the Channel Detail picker dropdown and the default-channel
 * resolution when user hits the Channels nav without a specific slug.
 */
export async function fetchChannelsList() {
  return apiRequest("/channels");
}

/**
 * Fetch the per-channel deep dive payload. Includes monthly trend,
 * regional breakdown, funnel, CX signals, response curve points,
 * optimizer context, campaign-level rows, and summary KPI stats.
 */
export async function fetchChannelDeepDive(channel) {
  return apiRequest(`/deep-dive/${encodeURIComponent(channel)}`);
}

/**
 * Cold-start variant: ensure analysis has run, then fetch the
 * requested channel's deep dive. If no channel specified, resolves
 * to the backend's default (largest absolute change from optimizer).
 * Returns { deepDive, channels } so the picker has options.
 */
export async function ensureChannelDetailReady(channelSlug) {
  if (!channelSlug) {
    const listFirst = await fetchChannelsList();
    if (listFirst.error && listFirst.error.kind === "http" && listFirst.error.status === 400) {
      const mock = await loadMockData();
      if (mock.error) return { data: null, error: mock.error };
      const analysis = await runAnalysis();
      if (analysis.error) return { data: null, error: analysis.error };
      const retry = await fetchChannelsList();
      if (retry.error) return { data: null, error: retry.error };
      channelSlug = retry.data.default;
    } else if (listFirst.data) {
      channelSlug = listFirst.data.default;
    } else {
      return { data: null, error: listFirst.error };
    }
  }

  const [deepRes, listRes] = await Promise.all([
    fetchChannelDeepDive(channelSlug),
    fetchChannelsList(),
  ]);

  if (deepRes.error) return { data: null, error: deepRes.error };

  return {
    data: {
      deepDive: deepRes.data,
      channels: listRes.data?.channels || [],
    },
    error: null,
  };
}
