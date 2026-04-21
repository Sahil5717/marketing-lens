# MarketLens

**Marketing ROI analytics for consulting engagements.**
Built for the analyst desk that sits between a CMO's questions and the plan a CFO will sign.

---

## What it does

MarketLens answers three questions every marketing review ends up asking:

1. **Where is value leaking today?** — diagnosis across channels with attribution, response curves, and value-at-risk quantification.
2. **What should we do about it?** — phased reallocation plan with honest lead times, per-channel execution constraints, and a calendar the client can actually execute against.
3. **How confident are you?** — Bayesian MMM credible intervals alongside frequentist point estimates, surfaced wherever a number is shown.

## Who it's for

Designed for **consulting analysts** preparing marketing effectiveness deliverables, and their **CMO/CFO audience** consuming those deliverables in a meeting room. Two surfaces:

- **Editor mode** (`/editor`) — for the analyst: data uploads, engagement management, suppressions, custom commentary, model diagnostics
- **Client mode** (`/`) — for the CXO: the polished read-out, with the analyst's edits applied

## Architecture

- **Backend**: FastAPI (Python 3.12)
- **Frontend**: React + Vite, styled-components, Recharts
- **Persistence**: SQLite (sessions, scenarios, users)
- **Auth**: JWT + RBAC (editor / client / admin roles)
- **Deployment**: Railway via Docker; cold-start ~90s including PyMC compilation

## Analysis engines

**Response curves**
- Power-law and Hill saturation fits per channel, auto-selected by R²
- Offline-aware: reach-based channels (TV, radio, OOH) fit a secondary diagnostic curve on the underlying primary metric (GRPs, reach)
- Leave-one-out cross-validation, near-linear fit detection, confidence tiering

**Marketing Mix Model**
- **Bayesian** primary path: PyMC NUTS with adstock + Hill saturation priors, 300 draws × 2 chains, convergence checked at r-hat < 1.05
- **MLE** fallback when Bayesian fails to converge
- **OLS** final fallback
- Credible intervals flow through to the UI: 80% HDI on ROAS, response curves, and plan deltas

**Optimizer**
- SLSQP constrained per-channel with realistic execution constraints:
  - TV: ±35% swing cap, 8-week lead time, $500K annual floor
  - Events: ±30% swing, 12-week lead time (trade show commitments)
  - Radio/OOH/Call center: channel-specific swing caps and lead times
  - Digital: no swing cap, 1-week lead time
- Multi-start initialization, trust-constr fallback when SLSQP fails
- Sensitivity analysis with deterministic seeding

**Attribution**
- Last-touch, linear, position-based, Markov chain

**External data**
- Competitive intelligence (SEMrush/SimilarWeb schema)
- Market events (seasonal calendar, competitor actions)
- Cost trends (CPC/CPM trajectories)
- Surfaced as honest diagnostics (Market Context screen); structured-prior integration into the MMM deferred

## Demo credentials

Four seeded users, all password `demo1234`:

| Username       | Role   | Intended use                     |
|----------------|--------|----------------------------------|
| ey.partner     | admin  | Full access, all override powers |
| ey.analyst     | editor | Analyst desk — prepare engagements |
| client.cmo     | viewer | Client CXO view                  |
| client.analyst | viewer | Client analyst view              |

## Screens

**Editor mode** (`/editor`):
- **Engagements** — list of consulting projects, active-engagement tracking, add/delete
- **Workspace** — data upload hub (5 CSV types), model controls, run-analysis trigger
- **Diagnosis** — what happened, with findings paired to recommendations
- **Plan** — what to do: Moves, Tradeoffs, Roadmap Gantt, Compare models (Bayesian vs frequentist)
- **Scenarios** — budget-sweep comparison
- **Channels** — per-channel deep-dive with response curves, Bayesian HDI band, campaigns table
- **Market** — external data: events, cost trends, competitive SOV

**Client mode** (`/`): Same screens minus upload controls and suppression tooling. Analyst overrides and commentary are visible as applied; no edit surface.

## Quick start (local)

```bash
# Backend
cd backend
pip install -r requirements.txt
JWT_SECRET=your-dev-secret uvicorn api:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run build
# Served statically by FastAPI at http://localhost:8000/editor
```

## Deploy (Railway)

`railway.toml` + `Dockerfile` handle the full build chain including PyMC's C-extension compilation. Required environment variable: `JWT_SECRET` (default is dev-only).

Demo users auto-seed on every boot — safe for Railway's ephemeral SQLite.

## Testing

- `test_integration.py` — 69 tests, full analysis pipeline
- `test_mmm_correctness.py` — 18 tests, MLE MMM correctness
- `test_optimizer_correctness.py` — 20 tests, constrained optimization
- `test_bayes_fast.py` — 44 tests, Bayesian HDI structure (~3 min, runs separately)

151 tests green as of v22. Run via `python test_integration.py` from the `backend/` directory.

## Project scope — honest version

This is a **pitch asset** — polished enough to demonstrate the product vision to an EY buyer, realistic enough to survive probing questions. It is not a production multi-tenant SaaS.

- **Engagements are shared-state in-memory** — switching active engagement is a UI affordance; the underlying data is the same mock dataset
- **Mock data is seeded** — 12 channels, 34 campaigns, 48 months, ~6,500 campaign rows + ~15,000 journey rows. Client CSV uploads are supported but the demo runs on mocks.
- **Roadmap is read-only** — drag-edit + per-user persistence deferred

What IS real: the math. Response curves actually fit, the optimizer actually converges under realistic constraints, Bayesian MMM actually samples via PyMC NUTS, credible intervals are derived from real posterior draws (not beta-CI approximations). A CMO can ask "what's your methodology?" and get a substantive answer.

## Changes

See `CHANGES.md` — full version history from v18 through v22.

## License

See `LICENSE`.
