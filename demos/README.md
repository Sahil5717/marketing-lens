# Visual demos (v26)

Self-contained HTML previews rendering each screen against USD-scale sample
data. Open in a browser — no server required.

- `screen_01_executive_summary_demo.html` — Screen 01 (Executive Summary)
- `screen_03_channel_performance_demo.html` — Screen 03 (Channel Performance)
- `screen_06_budget_optimization_demo.html` — Screen 06 (Budget Optimization)
  - Click "Show me how Atlas would reallocate this budget" to reveal
  - Click "Override recommendation" to see the currency-aware edit mode
- `market_context_panels_demo.html` — just the bottom-row panels

All demos show the default USD engagement. To see INR rendering:
1. Start the backend (`uvicorn api:app --reload`)
2. Create an INR engagement: `POST /api/engagements {id: "acme-in", name: "Acme India", currency: "INR"}`
3. Click the engagement selector in the sidebar footer, switch to "Acme India"

Demos use React + Babel Standalone from jsdelivr CDN. Production uses Vite.
