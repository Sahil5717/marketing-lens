# MarketLens v25 — Yield Intelligence screens pass

**Release date:** April 21, 2026
**Previous version:** marketlens-v24
**Scope:** Three production-grade screens (01 Executive Summary, 03 Channel Performance, 06 Budget Optimization), centrally-curated Macro Baseline data layer, shared design system.

## What's new

### Five-data-type architecture — first slice
Implements the **Macro Baseline** data type from build plan v2 §2A.1. Four other types (performance, journey, context overlay, scenario assumptions) still to land in a later release. The macro baseline is YI-team-curated, not per-tenant — 5 CSVs covering festivals, public holidays, monsoon windows, RBI consumer sentiment, and category seasonality from Jan 2022 through 2026.

```
backend/data/macro_baseline/
  festival_calendar.csv
  public_holidays.csv
  monsoon_windows.csv
  consumer_sentiment.csv
  category_seasonality.csv
```

### New backend modules

| Module | Endpoints | Tests |
|---|---|---|
| `datatypes/macro_baseline.py` | — | 20 |
| `routes_macro_baseline.py` | `GET /api/macro-baseline/freshness`, `GET /api/market-context` | (covered) |
| `routes_executive_summary.py` | `GET /api/executive-summary` | 13 |
| `routes_budget_optimization.py` | `GET /api/budget-optimization`, `POST /api/budget-optimization/override` | 12 |
| `routes_channel_performance.py` | `GET /api/channel-performance` | 14 |
| **Total** | **6 new endpoints** | **59 tests, all passing** |

Wired into `api.py` via `include_router` near line 53. The new `/api/market-context` supersedes the legacy handler lower in `api.py` because FastAPI picks the first registered match — the legacy handler becomes dead code but is not removed in this release.

### New frontend screens

All three screens render end-to-end against the real backend and were visually verified.

**Shared design system (`frontend/client/design/`)**
- `tokens.js` — colors, fonts, panel styles, hero gradient stops
- `AppShell.jsx` — 3-column shell with collapsible Atlas rail
- `AtlasRail.jsx` — collapsible right-hand rail with narration + suggested questions
- `TopBar.jsx` — screen number + title + pill slots

**Screen 01 — Executive Summary (`frontend/client/screens/executive_summary/`)**
- `HeroInsight.jsx` — dark gradient hero with coloured italic loss/gain
- `KpiStrip.jsx` — 5-cell metric row (reused on screen 03)
- `PillarsPanel.jsx` — three-pillar cost-of-bad-allocation
- `OpportunitiesAndActions.jsx` — recovery opportunities + top actions with inline "Why?" reveals
- `BridgeCard.jsx` — transition to next screen (reused across screens)
- `useExecutiveSummary.js` + `ExecutiveSummaryScreen.jsx` — data hook + root composer

**Screen 03 — Channel Performance (`frontend/client/screens/channel_performance/`)**
- `ChannelSummaryTable.jsx` — per-channel spend/revenue/ROI/conversions/trend
- `RevenueContributionCard.jsx` — donut + top insight callout
- `ChannelShiftPanel.jsx` — **new per plan v2 §3.2** — 100%-stacked area chart with macro event overlay markers
- `useChannelPerformance.js` + `ChannelPerformanceScreen.jsx`

**Screen 06 — Budget Optimization (`frontend/client/screens/budget_optimization/`)**
- `MintHeroInsight.jsx` — positive-framing hero variant
- `Donut.jsx` — reusable SVG donut (used on screens 03 and 06)
- `AllocationComparison.jsx` — earned-reveal pattern, edit mode with live override scoring, Atlas pushback callout
- `ImpactStrip.jsx` — 4-cell impact row, greys until reveal
- `FourMoves.jsx` — prioritised moves with inline "Why?" reveals + confidence bars
- `NetSummary.jsx` — closing mint-gradient summary
- `useBudgetOptimization.js` + `BudgetOptimizationScreen.jsx`

**Market Context (`frontend/client/screens/market_context/`)**
Shared bottom-row components that slot into Screen 01, and can be dropped onto screens 07 (Simulation) and 02 (Data Foundation) later.
- `MarketContextPanel.jsx` — demand trend chart
- `UpcomingPeakWindowsPanel.jsx` — festivals/holidays with impact badges
- `Screen01BottomRow.jsx` — combined drop-in
- `useMarketContext.js` — data hook

### Atlas template pattern (partial, PoC)
Each new route emits template-driven Atlas narration following build plan §5.1: concrete number, source attribution ("per the macro baseline"), bounded to 2–4 sentences, follow-up question, suggested-questions list. Full `backend/atlas/` package with dependency declarations still to land.

## Not in scope for v25

- Fresh Vite app scaffold (plan §3 Phase 0) — the new components live in the existing `frontend/client/` tree for now; rebuild into Vite is a separate release
- Other four data types (performance, journey, context overlay, scenario assumptions) as first-class modules
- Screens 02, 04, 05, 07, 08, 09, 10
- Analyst-mode dual-UI on Screen 02 (plan §2B.3)
- Full `backend/atlas/` template package
- Removing the legacy `/api/market-context` handler (deprecated but still in api.py)
- Multi-tenancy refactor (plan §4.2) — new routes read from the same legacy `_state` dict via the `_read_state()` adapter, so they inherit the existing single-tenant limitation. Adapter is a one-line change when per-engagement persistence lands.

## Integration notes

### Running the backend
```bash
cd backend
pip install -r requirements.txt
pytest test_macro_baseline.py test_executive_summary.py test_budget_optimization.py test_channel_performance.py   # 59 tests
uvicorn api:app --reload --port 8000
```

### Dropping the frontend into a page
```jsx
import ExecutiveSummaryScreen from "./screens/executive_summary/ExecutiveSummaryScreen.jsx";
import BudgetOptimizationScreen from "./screens/budget_optimization/BudgetOptimizationScreen.jsx";
import ChannelPerformanceScreen from "./screens/channel_performance/ChannelPerformanceScreen.jsx";
import AppShell from "./design/AppShell.jsx";
import AtlasRail from "./design/AtlasRail.jsx";

// Inside router:
<AppShell activeScreen={1} clientName="Acme Consumer Co." clientPeriod="Q2 2024"
          atlas={<AtlasRail narration={atlasNarration}/>}>
  <ExecutiveSummaryScreen apiBase=""/>
</AppShell>
```

Each screen fetches its own data via a `useXxx` hook. Empty and error states render the same shell so the layout doesn't jump during load.

### Sample demos
Three standalone HTML demos are included at `demos/` — each renders the corresponding screen against inlined real-backend sample payloads. Open in a browser to preview before deploying.

## Test coverage

```
test_macro_baseline.py        20 passed
test_executive_summary.py     13 passed
test_budget_optimization.py   12 passed
test_channel_performance.py   14 passed
--------------------------------------
                              59 passed
```

## Known issues / tradeoffs

1. **`ChannelShiftPanel` shows synthetic series** when `channel_monthly_history` is absent from state. Clearly flagged in-UI as "DEMO · synthesised from snapshot" so users don't over-interpret. Replace with real historical data when §2A.1 performance-data time-series storage is wired.

2. **Override scoring in `/api/budget-optimization/override` uses a linear marginal-ROI proxy**, not full response-curve re-evaluation. Fine for the "does this hurt the plan?" UX signal; replace with the real engine call when the frontend flow is validated with stakeholders.

3. **Visual demos use Babel Standalone** (CDN) to transform JSX in the browser — demo-only. Production uses Vite per build plan §3 Phase 0 when the fresh app lands.
