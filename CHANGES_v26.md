# MarketLens v26 — Per-engagement currency + locale

**Release date:** April 21, 2026
**Previous version:** marketlens-v25
**Scope:** Global currency support. Yield Intelligence now formats all money based on each engagement's configured currency — USD (default), INR, EUR, GBP — with an extensible per-engagement config layer. Screens render correctly for any currency without code changes.

## Why this release

v25 shipped with money formatting hardcoded to INR (₹ crore / lakh). Usable in India, not usable anywhere else. v26 makes currency a first-class configuration — the tool is now genuinely global. This release is infrastructure; the macro-baseline data is still India-specific and should be replaced before a Railway ship (see "Known tradeoffs").

## What's new

### 1. Engagement entity — the unit of configuration

An **engagement** is a client × time-period record. It owns the settings that drive presentation: currency, locale, display name. This is the first step of the plan §2B.1 engagement model (full per-engagement state is still ahead).

**New table:**
```sql
CREATE TABLE engagements (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    currency    TEXT NOT NULL DEFAULT 'USD',
    locale      TEXT NOT NULL DEFAULT 'en-US',
    created_at  REAL,
    updated_at  REAL
);
```

Seeded with a `'default'` row on first boot so existing callers keep working. The seed is idempotent — safe to run on every startup.

**New module: `backend/engagements.py`** — EngagementConfig dataclass + CRUD:
```python
get_engagement(id="default") → EngagementConfig
list_engagements()           → list[EngagementConfig]
create_engagement(id, name, currency, locale)
update_engagement(id, *, name=..., currency=..., locale=...)
delete_engagement(id)        # cannot delete 'default'
```

Unknown IDs fall back to `'default'` rather than raising, so routes always stay renderable. This matters during engagement-switching races.

**New routes: `backend/routes_engagements.py`**
```
GET    /api/engagements              → list + supported_currencies catalog
GET    /api/engagements/{id}         → single
POST   /api/engagements              → create  (409 on duplicate, 422 on bad currency)
PATCH  /api/engagements/{id}         → update  (404 on unknown)
DELETE /api/engagements/{id}         → delete  (400 for 'default')
```

### 2. Currency formatter — `backend/currency.py`

Single entry point for all money display:
```python
format_money(value, currency="USD")  # "$24.6M" / "₹24.6 Cr" / "€12.4M"
format_delta(value, currency)         # "+$5.2M" / "−₹3.1 Cr" (U+2212 minus, not hyphen)
format_rate(value)                    # "3.62x" / "—" for None
format_count(value)                   # "98K" / "1.4M"
```

Supported currencies and scale conventions:
| Currency | Scales | Example | Notes |
|---|---|---|---|
| USD | B / M / K | $2.48B, $24.6M, $582K, $42 | Billion tier for large budgets |
| EUR | B / M / K | €2.48B, €24.6M | Same convention as USD |
| GBP | B / M / K | £2.48B, £24.6M | Same convention as USD |
| INR | Cr / L | ₹24.8 Cr, ₹5.0 L, ₹582 | Keeps crore/lakh — what Indian decks use natively |

Adding a new currency is a pure data change: append to `CURRENCY_TABLE` in `currency.py`. No code elsewhere touches the list.

**Design decision — zero renders at mid-tier**, not the largest tier. `$0M` / `₹0 Cr`, not `$0B`. Keeps column widths visually consistent.

### 3. All 4 routes now engagement-aware

Every endpoint accepts an optional `engagement_id` query parameter and emits currency-aware strings:

```
GET /api/executive-summary?engagement_id=acme-q2
GET /api/channel-performance?engagement_id=acme-q2&lookback_months=24
GET /api/budget-optimization?engagement_id=acme-q2
GET /api/budget-optimization/override?engagement_id=acme-q2  (POST)
GET /api/market-context?engagement_id=acme-q2&category=FMCG  (no money fields, engagement
                                                               metadata returned for
                                                               frontend consistency)
```

Responses now include an `engagement` field with the resolved config, so the frontend can display which engagement is active.

**Breaking API change**: `/api/budget-optimization/override` previously accepted allocations in Crore (INR-specific). It now accepts **native currency units** (dollars, rupees, euros, or pounds — whatever the engagement uses). Response keys changed from `delta_vs_atlas_cr` etc. to `delta_vs_atlas` with paired `delta_vs_atlas_display` strings. Any external consumer of this endpoint needs updating.

### 4. Frontend — engagement selector + hook threading

**New shared component: `frontend/client/design/EngagementSelector.jsx`**
- Dropdown rendered in the Sidebar footer
- Fetches `/api/engagements` once on mount, displays current engagement + currency pill
- Persists selection in `localStorage` under `"yi.engagementId"` so it survives page reloads
- Click to expand the list, pick another engagement, all screens re-fetch

**AppShell integration:**
- Manages engagement state internally via `getStoredEngagementId()` / `setStoredEngagementId()` helpers exported from `EngagementSelector.jsx`
- Passes `engagementId` to children (either as a prop if consumer passes it, or via render-function pattern: `<AppShell>{({engagementId}) => <Screen engagementId={engagementId}/>}</AppShell>`)

**All 4 data hooks now accept `engagementId`:**
```jsx
useExecutiveSummary({ apiBase, engagementId })
useBudgetOptimization({ apiBase, engagementId })  // also threads engagementId into scoreOverride POST
useChannelPerformance({ apiBase, engagementId, lookbackMonths })
useMarketContext({ apiBase, engagementId, asOf, category, regions, ... })
```

Default for all: `"default"` — matches the seeded engagement, so existing code paths work without changes.

### 5. Frontend bugfixes caught during v26 visual verification

Three pieces of hardcoded ₹/Cr copy would have shipped broken if we hadn't done this work:

- `AllocationComparison.jsx` reveal CTA: "these rupees" → "this budget" (currency-neutral copy)
- `AllocationComparison.jsx` edit mode: currency symbol + scale suffix now derived from the backend's `display_amount` string via a new `parseScale()` helper. Input now shows `$ 30100000 M` for USD engagements and `₹ 30.1 Cr` for INR — correct prefix and scale in both
- `AtlasRail.jsx` narration-bolding regex: only matched `₹X Cr|L`; now matches `$X M|B|K`, `€X`, `£X`, `₹X`, and signed variants (`+$5.2M` / `−₹3.1 Cr` with proper U+2212 minus sign)

## Test coverage

| Module | Tests | Notes |
|---|---|---|
| `test_currency.py`              | 23 | USD/INR/EUR/GBP formatting + B tier + signed + zero-render + unsupported-currency errors |
| `test_engagements.py`           | 20 | Isolated-DB fixture pattern; CRUD + HTTP layer + default fallback + forbidden deletion |
| `test_macro_baseline.py`        | 20 | Unchanged from v25 (no money fields) |
| `test_executive_summary.py`     | 18 | Adds 5 currency tests — USD vs INR vs EUR parameterisation + Atlas narration currency |
| `test_budget_optimization.py`   | 16 | Adds 4 currency tests including override-endpoint native-units contract |
| `test_channel_performance.py`   | 17 | Adds 3 currency tests |
| **Total**                       | **114** | All green at the time of the zip |

## Live proof

Same engine state, two engagements, completely different presentation:

```
USD (default engagement):
  Hero loss       : $35.8M
  Hero recoverable: $20.1M
  Pillar 1        : $24.3M
  Revenue         : $248M
  Opportunity 1   : +$14.6M
  Atlas narration : "The headline number — $35.8M — is the one..."

INR (acme-india engagement):
  Hero loss       : ₹3.6 Cr
  Hero recoverable: ₹2.0 Cr
  Pillar 1        : ₹2.4 Cr
  Revenue         : ₹248 Cr
  Opportunity 1   : +₹1.5 Cr
  Atlas narration : "The headline number — ₹3.6 Cr — is the one..."
```

## Integration notes

### Creating a new engagement via the API

```bash
curl -X POST http://localhost:8000/api/engagements \
  -H "Content-Type: application/json" \
  -d '{
    "id": "acme-q2-2024",
    "name": "Acme Consumer Co. · Q2 2024",
    "currency": "USD",
    "locale": "en-US"
  }'
```

### Targeting an engagement from the frontend

```jsx
// Inside any screen composer:
<ExecutiveSummaryScreen apiBase="" engagementId="acme-q2-2024" />

// Or let the AppShell manage it via the EngagementSelector + localStorage:
<AppShell activeScreen={1} ...>
  {({ engagementId }) => (
    <ExecutiveSummaryScreen engagementId={engagementId} />
  )}
</AppShell>
```

### Changing an engagement's currency at runtime

```bash
curl -X PATCH http://localhost:8000/api/engagements/acme-q2-2024 \
  -H "Content-Type: application/json" \
  -d '{"currency": "EUR"}'
```

All subsequent requests targeting that engagement use the new currency. No app restart needed.

## Known tradeoffs

1. **Macro baseline is still India-specific.** Festival calendar, monsoon windows, regions like Mumbai/Delhi — all Indian. Fine for pitch demos to Indian clients using an INR engagement; wrong for US/EU clients using a USD engagement. The Channel Shift panel's overlay markers will show Indian festivals regardless of the engagement. Replacement data (US retail calendar, EU holidays, neutral category seasonality) is separate work.

2. **The override endpoint's API contract changed.** `/api/budget-optimization/override` used to take allocations in Crore. Now it takes native currency units and returns keys without the `_cr` suffix. No frontend changes needed because the hook was updated to match, but any external consumers break.

3. **Engagement model doesn't yet own state.** Only settings (currency/locale/name). The underlying `_state` dict is still single-tenant — two users hitting the API with different `engagement_id` values currently see the **same** channel data, because that comes from `_state`, not per-engagement storage. The plan §4.2 multi-tenancy refactor is needed for real tenant isolation.

4. **B tier only for USD/EUR/GBP, not INR.** Indian convention keeps everything in crore/lakh indefinitely — ₹2,480 Cr is how Indian marketing decks present billion-rupee figures. No plan to change this.

5. **Demo HTMLs use Babel Standalone in-browser.** Same as v25 — for stakeholder preview only. Production uses Vite (build plan §3 Phase 0).

## Migration from v25

Zero-config for existing deployments:
1. Pull the zip, run the backend — the `engagements` table is created and seeded on first boot
2. Existing `/api/*` calls without `engagement_id` keep working, resolving to the `default` engagement (USD)
3. Your production data that was computed assuming INR will start rendering in USD. If that's wrong, either:
   - Create an INR engagement and switch to it from the selector: `POST /api/engagements {id: "legacy", name: "Legacy India", currency: "INR"}`, then pick "Legacy India" from the sidebar dropdown
   - Or `PATCH /api/engagements/default {currency: "INR"}` to flip the default

## File inventory — what's new or changed

New files:
```
backend/currency.py
backend/engagements.py
backend/routes_engagements.py
backend/test_currency.py
backend/test_engagements.py
frontend/client/design/EngagementSelector.jsx
```

Modified files:
```
backend/api.py                               (wired engagements router + init hook)
backend/routes_executive_summary.py          (currency + engagement threading)
backend/routes_budget_optimization.py        (currency + engagement threading + override contract)
backend/routes_channel_performance.py        (currency + engagement threading)
backend/routes_macro_baseline.py             (engagement metadata in response)
backend/test_executive_summary.py            (rewritten for engagement fixture)
backend/test_budget_optimization.py          (rewritten for USD scale + override contract)
backend/test_channel_performance.py          (rewritten for currency behaviour)
frontend/client/design/AppShell.jsx          (engagement selector integration)
frontend/client/design/AtlasRail.jsx         (multi-currency bolding regex)
frontend/client/screens/executive_summary/useExecutiveSummary.js
frontend/client/screens/executive_summary/ExecutiveSummaryScreen.jsx
frontend/client/screens/budget_optimization/useBudgetOptimization.js
frontend/client/screens/budget_optimization/BudgetOptimizationScreen.jsx
frontend/client/screens/budget_optimization/AllocationComparison.jsx  (parseScale + edit inputs)
frontend/client/screens/channel_performance/useChannelPerformance.js
frontend/client/screens/channel_performance/ChannelPerformanceScreen.jsx
frontend/client/screens/market_context/useMarketContext.js
CHANGES_v26.md                               (this file)
demos/*.html                                 (regenerated with USD sample data)
```
