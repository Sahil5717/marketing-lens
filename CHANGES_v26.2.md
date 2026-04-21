# MarketLens v26.2 — Frontend integration + auth on YI routes

**Release date:** April 21, 2026
**Previous version:** v26.1 (Dockerfile hotfix that removed broken `docs/` COPY)
**Scope:** Wire the 3 Yield Intelligence screens (Executive Summary, Channel Performance, Budget Optimization) into the live frontend app and protect the new backend routes with the same auth gate as the rest of the API.

## What broke in v26

v26 shipped the backend routes, the currency formatter, the engagement model, and 114 passing tests — but **none of the new React screens were wired into any entry point the Vite build reads.** The files were on disk; they weren't in the bundle. Pushing to Railway produced the same UI as v24 because the deployed bundle knew nothing about the new screens. Engagement selector, AppShell, ExecutiveSummaryScreen, BudgetOptimizationScreen, ChannelPerformanceScreen — all orphaned.

On top of that, the new backend routes were unauthenticated while the existing MarketLens endpoints used `require_editor` / `get_current_user` guards. Clients hitting `/api/executive-summary` would have worked without a JWT, which is both inconsistent and wrong.

v26.2 fixes both problems together.

## Changes

### Backend: auth on every new route

Added `Depends(require_client_or_editor)` to every route in:

- `routes_executive_summary.py` — `GET /api/executive-summary`
- `routes_budget_optimization.py` — `GET /api/budget-optimization` and `POST /api/budget-optimization/override`
- `routes_channel_performance.py` — `GET /api/channel-performance`
- `routes_macro_baseline.py` — `GET /api/macro-baseline/freshness` and `GET /api/market-context`

Engagements CRUD uses a split: **reads** allow client+editor, **writes** require editor.

- `GET /api/engagements` → `require_client_or_editor`
- `GET /api/engagements/{id}` → `require_client_or_editor`
- `POST /api/engagements` → `require_editor`
- `PATCH /api/engagements/{id}` → `require_editor`
- `DELETE /api/engagements/{id}` → `require_editor`

This matches the existing API's pattern where mutation requires editor.

**Test fixture: `backend/conftest.py`** — new `AuthedTestClient` subclass of FastAPI's `TestClient` that auto-injects a Bearer token on every request. Role defaults to `"client"`; tests that need editor permissions pass `role="editor"`. Three test files (`test_executive_summary.py`, `test_budget_optimization.py`, `test_channel_performance.py`) updated to use it with a two-line sed. `test_engagements.py` uses editor because most of its tests are CRUD.

All 114 tests still pass after the auth addition.

### Frontend: Vite wiring + authed fetch

**`frontend/client/api.js`** — `apiRequest()` is now exported (was module-private). It automatically attaches `Authorization: Bearer <token>` from `localStorage` and forwards 401s to the existing unauthorized handler that redirects to `/login`.

**4 hook files rewritten to use `apiRequest`:**
- `useExecutiveSummary.js`
- `useBudgetOptimization.js` (both the GET and the override POST)
- `useChannelPerformance.js`
- `useMarketContext.js`

They no longer take an `apiBase` prop (unused after switching to `apiRequest`, which has its own `API_BASE` constant). The screen composers still pass `apiBase` for compatibility; it's a harmless no-op.

**`DiagnosisApp.jsx`** — wired in the 3 YI screens. Changes:

1. Three new `?screen=` URL values: `executive-summary`, `budget-optimization`, `channel-performance`
2. Lazy imports for the screen components (keeps YI code out of the initial bundle for users who never navigate there)
3. `useEffect` early-returns for YI screens — they self-fetch via their hooks, no `ensureXReady` loader needed
4. Full-viewport render branch at the top of the component return: YI screens render inside `<AppShell>` (sidebar + main + Atlas rail), bypassing the `AppHeader`/`Footer` chrome that wraps the MarketLens screens. This was the architectural call we made explicitly — YI is a distinct product tier and owns its own shell.
5. `handleNavigate` callback maps `AppShell` sidebar clicks (screen numbers 1/3/6) back into the `?screen=` URL params so the sidebar navigation works

### Navigation URLs after v26.2

```
/?screen=diagnosis                 — existing MarketLens Diagnosis (unchanged)
/?screen=plan                      — existing Plan
/?screen=scenarios                 — existing Scenarios
/?screen=channels&channel=search   — existing Channel Detail
/?screen=market                    — existing Market Context
/?screen=executive-summary         — NEW: YI Screen 01 (Executive Summary)
/?screen=channel-performance       — NEW: YI Screen 03 (Channel Performance)
/?screen=budget-optimization       — NEW: YI Screen 06 (Budget Optimization)
```

Demo credentials for local testing: `client.cmo` / `demo1234` (client role — can view all YI screens but can't create/edit engagements). For engagement CRUD, use `editor.analyst` / `demo1234`.

## What's NOT in this release

1. **Engagement management UI** — you can pick from existing engagements via the sidebar selector, but creating/editing/deleting engagements still requires the REST API. A settings page is follow-up work.

2. **Atlas narration on the YI sidebar rail** — the `AtlasRail` inside `DiagnosisApp`'s YI render path currently passes an empty narration stub. Each YI screen sets its own narration inline (via the `atlasInline` prop on the screen composers). Wiring the sidebar rail to show the current screen's narration is a small follow-up.

3. **Sharing the engagement selection across a session** — we use `localStorage` which is tab-local. If you open a second tab, it'll default to the same engagement, but changing it in one tab doesn't broadcast to the other.

## Migration notes

No API contract breaks in v26.2. The only contract change was in v26 itself (the override endpoint switched from Cr-specific to native-currency-unit — if you have external consumers of `/api/budget-optimization/override`, see CHANGES_v26.md §4).

## File inventory

Modified backend (auth added):
```
backend/routes_executive_summary.py
backend/routes_budget_optimization.py
backend/routes_channel_performance.py
backend/routes_macro_baseline.py
backend/routes_engagements.py
backend/test_executive_summary.py     (uses AuthedTestClient)
backend/test_budget_optimization.py   (uses AuthedTestClient)
backend/test_channel_performance.py   (uses AuthedTestClient)
backend/test_engagements.py           (uses AuthedTestClient with editor role)
```

New backend:
```
backend/conftest.py                    (AuthedTestClient + auth_headers helper)
```

Modified frontend:
```
frontend/client/api.js                 (exports apiRequest)
frontend/client/DiagnosisApp.jsx       (wires 3 YI screens)
frontend/client/screens/executive_summary/useExecutiveSummary.js  (rewritten)
frontend/client/screens/budget_optimization/useBudgetOptimization.js  (rewritten)
frontend/client/screens/channel_performance/useChannelPerformance.js  (rewritten)
frontend/client/screens/market_context/useMarketContext.js  (rewritten)
```

No files deleted.
