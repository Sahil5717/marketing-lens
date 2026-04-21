# Visual demos

Each HTML file is self-contained — open in a browser and it will render
the corresponding screen against inlined sample data from the real
backend endpoints.

- `screen_01_executive_summary_demo.html` — Screen 01 (full)
- `screen_03_channel_performance_demo.html` — Screen 03 (full)
- `screen_06_budget_optimization_demo.html` — Screen 06 (click "Show me how Atlas would reallocate" to reveal)
- `market_context_panels_demo.html` — just the bottom-row panels from Screen 01

Demo requirements: a modern browser with JS enabled. Uses React + Babel
Standalone from jsdelivr CDN to transform JSX in-browser. Demo-only —
production uses Vite per build plan §3 Phase 0.

**Note:** demos are for stakeholder preview. They are not used by the
running app; `uvicorn api:app` + the JSX components in
`frontend/client/` are the production path.
