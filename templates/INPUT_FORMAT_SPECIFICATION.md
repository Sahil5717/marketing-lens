# Input Data Format Specification
## Yield Intelligence Platform — v2.0

---

## Critical: Data Duration Requirements

This tool uses **two different time windows** from the same dataset:

| Purpose | Time Window | Why |
|---------|-------------|-----|
| **ROI, KPIs, diagnostics, recommendations** | Last 12 months (current FY) | Shows current performance, not historical averages |
| **MMM, response curves, adstock, forecasting** | Full 3–5 years | Statistical models need enough observations for reliable parameter estimation |

**You upload ONE file.** The system automatically splits it:
- Last 12 months → performance reporting
- Full history → model training

### What happens with insufficient data

| Data uploaded | ROI/KPIs | Response Curves | MMM (Bayesian) | Forecasting | Optimizer |
|---------------|----------|-----------------|----------------|-------------|-----------|
| 12 months | ✅ Correct | ⚠️ Overfitting risk | ❌ Unreliable (12 points for MCMC) | ❌ Can't detect seasonality | ⚠️ Based on weak curves |
| 24 months | ✅ Correct | ✅ Acceptable | ⚠️ Minimum viable | ✅ 2 seasonal cycles | ✅ Acceptable |
| 36 months | ✅ Correct | ✅ Good | ✅ Reliable | ✅ Good | ✅ Reliable |
| 48–60 months | ✅ Correct | ✅ Strong | ✅ Strong (convergent posteriors) | ✅ Strong | ✅ Strong |

**Recommendation: Upload 36+ months of data.** 48 months is ideal.

---

## Input Files

| File | Required? | Purpose | Rows expected |
|------|-----------|---------|---------------|
| **Campaign Performance** | Yes | All KPIs, ROI, models, optimization | 5K–500K (monthly × channels × campaigns × regions × 3–5 years) |
| **User Journeys** | Optional (for multi-touch attribution) | Markov chain, Shapley, position-based attribution | 50K–5M touchpoints |
| **Offline Activity** | Optional (for offline channels) | TV/radio/OOH/events/dealer metrics not captured in digital platforms | 500–50K rows |
| **Budget Plan** | Optional (for next-year scenarios) | Baseline plan to compare against optimizer output | 50–500 rows |

If only Campaign Performance is provided, the tool uses last-touch attribution and treats offline channels based on spend-revenue correlation.

---

## File 1: Campaign Performance (Required)

**Grain:** One row per Month × Channel × Campaign × Region
**Date range:** 3–5 years (minimum 24 months, ideal 48 months)
**Encoding:** UTF-8 CSV or XLSX

### Required Columns (5)

| Column | Type | Format | Example | Used By |
|--------|------|--------|---------|---------|
| `date` | Date | YYYY-MM-DD or YYYY-MM | 2022-01-01 | All engines — time axis. **Must span 3+ years for models** |
| `channel` | String | Free text | paid_search, tv_national, events | All engines — primary dimension |
| `campaign` | String | Free text | PS_Brand_Q1, TV_Launch_2023 | Deep dive, campaign-level diagnostics |
| `spend` | Numeric | No currency symbols | 15000.00 | ROI, ROAS, CAC, optimizer, leakage |
| `revenue` | Numeric | No currency symbols | 48000.00 | ROI, ROAS, response curves, optimizer |

### Recommended Columns (unlock more features)

| Column | Type | Example | Unlocks |
|--------|------|---------|---------|
| `channel_type` | String: online / offline | online | Online vs offline split, cross-channel analysis |
| `region` | String | North, South, West | Regional leakage, geo-lift testing |
| `product` | String | Product_A | Product-level ROI |
| `impressions` | Integer | 85000 | CTR, funnel top. **Set 0 for offline channels** |
| `clicks` | Integer | 3800 | CPC, CTR, CVR. **Set 0 for offline** |
| `leads` | Integer | 266 | CPL, funnel analysis |
| `mqls` | Integer | 120 | Funnel bottleneck detection |
| `sqls` | Integer | 46 | Lead quality analysis |
| `conversions` | Integer | 14 | CAC, CVR, payback period |
| `bounce_rate` | Decimal 0–1 | 0.42 | CX suppression analysis |
| `avg_session_duration_sec` | Numeric | 145 | Engagement quality |
| `form_completion_rate` | Decimal 0–1 | 0.12 | Conversion friction detection |
| `nps_score` | Integer 0–100 | 38 | Experience pillar |

### Offline-Specific Columns (optional, for offline channels)

| Column | Type | Example | Unlocks |
|--------|------|---------|---------|
| `grps` | Numeric | 250.5 | TV/radio reach measurement |
| `reach` | Integer | 1500000 | Offline audience reach |
| `store_visits` | Integer | 3400 | Offline-to-store conversion |
| `calls_generated` | Integer | 890 | Call center attribution |
| `event_attendees` | Integer | 450 | Event ROI calculation |
| `dealer_enquiries` | Integer | 120 | Dealer/partner attribution |
| `coupon_redemptions` | Integer | 2300 | Promo effectiveness |

**Rules for offline channels:**
- Set `impressions`, `clicks`, `bounce_rate`, `form_completion_rate` to 0
- Use `reach` or `grps` instead of `impressions` for awareness measurement
- `conversions` can be offline sales attributed to the campaign

---

## File 2: User Journeys (Optional)

**Grain:** One row per touchpoint in a user journey
**Purpose:** Enables multi-touch attribution (Markov, Shapley, position-based)
**If not provided:** Only last-touch attribution is available

### Required Columns

| Column | Type | Example | Purpose |
|--------|------|---------|---------|
| `journey_id` | String | J_00001 | Groups touchpoints into journeys |
| `touchpoint_order` | Integer | 1, 2, 3... | Sequence within the journey |
| `channel` | String | paid_search | Must match campaign performance channels |
| `campaign` | String | PS_Brand | Must match campaign performance campaigns |
| `converted` | Boolean | TRUE / FALSE | Whether this journey converted |
| `conversion_revenue` | Numeric | 850.00 | Revenue from conversion (0 if not converted) |
| `total_touchpoints` | Integer | 4 | Total touchpoints in this journey |

---

## File 3: Offline Activity Detail (Optional)

For offline channels where the campaign performance file doesn't capture enough detail.

### Columns

| Column | Type | Example | Purpose |
|--------|------|---------|---------|
| `date` | Date | 2024-03-01 | Activity date |
| `channel` | String | events | Must match campaign performance |
| `campaign` | String | TradeShow_CES_2024 | Activity name |
| `region` | String | West | Region |
| `activity_type` | String | trade_show / webinar / dealer_activation | Type |
| `attendees` | Integer | 450 | Participants |
| `qualified_leads` | Integer | 68 | Qualified outcomes |
| `pipeline_generated` | Numeric | 340000 | Pipeline $ value |
| `cost` | Numeric | 85000 | Total activity cost |
| `follow_up_meetings` | Integer | 23 | Sales follow-up |

---

## File 4: Budget Plan (Optional)

For next-year scenario comparison.

| Column | Type | Example | Purpose |
|--------|------|---------|---------|
| `scenario` | String | baseline / growth / efficiency | Scenario name |
| `channel` | String | paid_search | Channel |
| `campaign` | String | PS_Brand | Campaign (optional) |
| `planned_spend` | Numeric | 180000 | Planned annual spend |
| `min_spend` | Numeric | 50000 | Minimum constraint |
| `max_spend` | Numeric | 300000 | Maximum constraint |

---

## How the Data Flows Through the System

```
Upload (3-5 years)
    │
    ├── Data Splitter
    │   ├── Last 12 months ──→ ROI / KPIs / Diagnostics / Recommendations / Pillars
    │   └── Full history ───→ Response Curves / MMM / Adstock / Forecasting
    │
    ├── User Journeys ────→ Multi-touch Attribution (Markov, Shapley)
    │
    └── Budget Plan ──────→ Scenario Comparison / Constraint Setup
         │
         └── Optimizer uses model params (from full history)
             applied to current-year budget
```

---

## Data Quality Requirements

| Check | Rule | Consequence if violated |
|-------|------|------------------------|
| Date completeness | No month gaps in the date range | Models may produce spurious seasonality |
| Spend positivity | All spend values ≥ 0 | Negative spend breaks response curves |
| Revenue positivity | All revenue values ≥ 0 | Negative revenue breaks ROI calculations |
| Channel consistency | Same channel names across all years | Mismatched names → channels treated as separate |
| No future dates | All dates ≤ today | Future dates confuse train/report split |
| Minimum 24 months | Date range spans 24+ months | Models flagged as unreliable if less |

---

## Naming Conventions

Use consistent channel names across all years. The system auto-maps common variations:

| Standard Name | Accepted Variations |
|---------------|-------------------|
| paid_search | Paid Search, Google Ads, SEM, PPC |
| organic_search | Organic Search, SEO, Natural Search |
| social_paid | Social Paid, Meta Ads, Facebook Ads, Social Media Paid |
| display | Display, Programmatic, GDN, Display Advertising |
| email | Email, Email Marketing, eDM |
| video_youtube | Video, YouTube, OLV, Online Video |
| events | Events, Trade Shows, Conferences, Webinars |
| tv_national | TV, Television, TV National, Broadcast TV |
| radio | Radio, Radio Advertising |
| ooh | OOH, Out of Home, Billboard, Outdoor |
| direct_mail | Direct Mail, DM, Mail, Postal |
| call_center | Call Center, Telemarketing, Outbound Calls |
