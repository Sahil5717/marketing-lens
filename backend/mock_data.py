"""
Mock Data Generator for Marketing ROI & Budget Optimization Engine
Generates realistic multi-channel marketing data including:
- Campaign-level performance (spend, impressions, clicks, leads, conversions, revenue)
- User-level journey data (touchpoints per conversion for attribution)
- CX signals (bounce rate, session depth, NPS, unsubscribe rate)
- Monthly granularity across 12 months, 8 channels, ~30 campaigns
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import json

np.random.seed(42)

# --- Channel & Campaign Definitions ---

CHANNELS = {
    "paid_search":    {"type": "online",  "base_cpc": 2.5,  "base_cvr": 0.035, "saturation_point": 150000,
                       "attribution_basis": "click",    "primary_metric": "clicks"},
    "organic_search": {"type": "online",  "base_cpc": 0,    "base_cvr": 0.042, "saturation_point": None,
                       "attribution_basis": "click",    "primary_metric": "clicks"},
    "social_paid":    {"type": "online",  "base_cpc": 1.8,  "base_cvr": 0.018, "saturation_point": 120000,
                       "attribution_basis": "click",    "primary_metric": "clicks"},
    "display":        {"type": "online",  "base_cpc": 0.9,  "base_cvr": 0.008, "saturation_point": 80000,
                       "attribution_basis": "click",    "primary_metric": "clicks"},
    "email":          {"type": "online",  "base_cpc": 0.15, "base_cvr": 0.055, "saturation_point": 40000,
                       "attribution_basis": "click",    "primary_metric": "clicks"},
    "video_youtube":  {"type": "online",  "base_cpc": 3.2,  "base_cvr": 0.012, "saturation_point": 100000,
                       "attribution_basis": "click",    "primary_metric": "clicks"},
    # Direct-response offline — has a native conversion signal (event attendees,
    # dealer enquiries from mailers). No clicks but a strong funnel proxy.
    "events":      {"type": "offline", "base_cpc": 45,  "base_cvr": 0.08,  "saturation_point": 200000,
                    "attribution_basis": "direct_response", "primary_metric": "event_attendees"},
    "direct_mail": {"type": "offline", "base_cpc": 5.5, "base_cvr": 0.025, "saturation_point": 60000,
                    "attribution_basis": "direct_response", "primary_metric": "dealer_enquiries"},
    # Broadcast offline — reach-based, no clicks. GRPs are the primary unit.
    # Saturation is structural (you can't reach >100% of population) AND
    # diminishing (the 4th exposure to a viewer is much less effective than
    # the 1st). Saturation point here is in spend terms for the power-law
    # funnel — the real reach-basis curve is in engines/response_curves.
    "tv_national": {"type": "offline", "base_cpc": 0, "base_cvr": 0.004, "saturation_point": 400000,
                    "attribution_basis": "reach", "primary_metric": "grps"},
    "radio":       {"type": "offline", "base_cpc": 0, "base_cvr": 0.003, "saturation_point": 90000,
                    "attribution_basis": "reach", "primary_metric": "grps"},
    "ooh":         {"type": "offline", "base_cpc": 0, "base_cvr": 0.002, "saturation_point": 150000,
                    "attribution_basis": "reach", "primary_metric": "reach"},
    # Direct-response offline — inbound calls for a call_center.
    "call_center": {"type": "offline", "base_cpc": 0, "base_cvr": 0.035, "saturation_point": 80000,
                    "attribution_basis": "direct_response", "primary_metric": "calls_generated"},
}


# Target channel mix for a realistic mid-market/enterprise B2B portfolio.
# Without this calibration, the raw funnel math produces wildly-uneven channel
# ROAS (events at 125x, display at 0.07x) because the underlying CTR / CVR /
# AOV constants were set for visual differentiation rather than balance.
#
# The calibration works by applying a per-channel revenue multiplier after
# the funnel runs. Funnel numbers (clicks, leads, conversions) remain
# realistic and interconnected -- only the final revenue gets scaled so the
# portfolio looks like a plausible real-world channel mix.
#
# Target ROAS is what a CMO would consider healthy for each channel:
#   - paid_search: 4-6x, steady workhorse
#   - organic_search: very high ROAS because spend is mostly SEO labor
#   - email: 10-15x, low cost relative to revenue (mature list)
#   - events: 2-4x, big absolute spend with long sales cycle
#   - display: 1.5-3x, awareness channel
#   - direct_mail: 2-4x, declining but still present in B2B
TARGET_CHANNEL_MIX = {
    "paid_search":    {"target_roas": 5.0},
    "organic_search": {"target_roas": 40.0},
    "social_paid":    {"target_roas": 3.5},
    "display":        {"target_roas": 2.2},
    "email":          {"target_roas": 13.0},
    "video_youtube":  {"target_roas": 2.5},
    "events":         {"target_roas": 3.0},
    "direct_mail":    {"target_roas": 3.0},
    # Offline broadcast — weaker ROAS is realistic; these are brand/awareness
    # channels with indirect attribution paths. Client expects to justify
    # them on reach and halo, not short-term ROAS alone.
    "tv_national":    {"target_roas": 2.0},
    "radio":          {"target_roas": 2.4},
    "ooh":            {"target_roas": 1.8},
    # Call center — direct response, higher ROAS than broadcast
    "call_center":    {"target_roas": 4.0},
}


# Measured at generation time from a single representative run with
# np.random.seed(42). Dividing target_roas by baseline_roas gives the
# scalar that brings each channel's revenue from raw-funnel output to
# target. Updated by running _measure_baseline_roas() below.
#
# These are the "as-generated" ROAS values from the raw funnel before
# any calibration. The calibration multiplier is target / baseline.
BASELINE_UNCALIBRATED_ROAS = {
    "paid_search":    6.4,
    "organic_search": 3.9,
    "social_paid":    0.6,
    "display":        0.07,
    "email":          33.5,
    "video_youtube":  0.11,
    "events":         125.0,
    "direct_mail":    2.1,
    # Measured values for new offline channels from a first generation run
    # with the current parameters. Updating here makes the calibration
    # multiplier produce on-target ROAS.
    "tv_national":    0.51,
    "radio":          0.45,
    "ooh":            0.09,
    "call_center":    103.71,
}


def _channel_revenue_calibration(channel: str) -> float:
    """Revenue calibration factor for a channel.

    Scales raw funnel revenue to hit TARGET_CHANNEL_MIX[channel]['target_roas'].
    Applied multiplicatively at the end of the funnel after all other noise.
    Returns 1.0 for channels not in the calibration table (no rescaling).
    """
    if channel not in TARGET_CHANNEL_MIX or channel not in BASELINE_UNCALIBRATED_ROAS:
        return 1.0
    target = TARGET_CHANNEL_MIX[channel]["target_roas"]
    baseline = BASELINE_UNCALIBRATED_ROAS[channel]
    if baseline <= 0:
        return 1.0  # avoid div-zero; channel would need different approach
    return target / baseline

CAMPAIGNS_PER_CHANNEL = {
    "paid_search": ["PS_Brand", "PS_Generic", "PS_Competitor", "PS_Product"],
    "organic_search": ["SEO_Blog", "SEO_Product_Pages"],
    "social_paid": ["Social_Meta_Awareness", "Social_Meta_Retargeting", "Social_LinkedIn_LeadGen", "Social_TikTok_Brand"],
    "display": ["Display_Programmatic", "Display_Retargeting", "Display_Native"],
    "email": ["Email_Newsletter", "Email_Nurture", "Email_Promo", "Email_Winback"],
    "video_youtube": ["YT_PreRoll", "YT_Discovery", "YT_Shorts"],
    "events": ["Events_TradeShow", "Events_Webinar", "Events_Conference"],
    "direct_mail": ["DM_Catalog", "DM_PostCard"],
    # Broadcast offline — a small number of large campaigns (networks, stations)
    "tv_national": ["TV_Primetime", "TV_Daytime", "TV_Sports"],
    "radio":       ["Radio_Morning", "Radio_Evening"],
    "ooh":         ["OOH_Billboards", "OOH_Transit"],
    # Call center — inbound response programs tied to other media
    "call_center": ["CC_InboundSales", "CC_Retention"],
}

REGIONS = ["North", "South", "East", "West"]
PRODUCTS = ["Product_A", "Product_B", "Product_C"]

MONTHS = pd.date_range("2022-01-01", periods=48, freq="MS")  # 4 years for model training

# Shared macro-seasonality — a mild signal that affects every channel (consumer
# attention rises in Q4, dips in summer). Kept modest (±20%) so it doesn't
# dominate channel-specific patterns.
SEASONALITY = [0.85, 0.80, 0.95, 1.05, 1.10, 1.00, 0.90, 0.88, 1.05, 1.15, 1.25, 1.30]


# Channel-specific temporal signatures. Each channel's monthly spend is shaped
# by ITS OWN pattern, not the shared SEASONALITY. This is what gives MMM
# enough independent variation across channels to actually identify separate
# betas — without this, channel spend columns correlate at ~0.99 and no
# statistical method (OLS, MLE, Bayesian) can tell them apart.
#
# Each entry describes one channel's behavior over a 12-month cycle:
#   phase_shift:   offset (in months) of that channel's peak
#   amplitude:     how strong the seasonal swing is (0 = flat, 0.4 = ±40%)
#   base_trend_yr: annual linear growth factor applied to all months
#                  (positive = channel growing over 4 years, negative = declining)
#   noise_pct:     intra-month noise -- offline channels are noisier
#   flight_months: specific months of the year (0-11) where this channel is
#                  mostly OFF. Empty list = always-on.
#   spike_months:  (year_month_of_year) tuples where a specific launch event
#                  occurred. Spend is 2-3x normal.
#
# These are modeled on roughly-plausible B2B/mid-market spend patterns.
CHANNEL_PATTERNS: Dict[str, dict] = {
    "paid_search": {
        # Always-on but with budget reallocations: mild seasonality plus
        # two spike months per year (competitive events, launches). Without
        # some variation, MMM absorbs paid_search into baseline.
        "phase_shift": 10,  # peak in Nov
        "amplitude": 0.25,
        "base_trend_yr": 0.08,
        "noise_pct": 0.10,
        "flight_months": [],
        "spike_months": [
            (2022, 5), (2022, 11),
            (2023, 5), (2023, 11),
            (2024, 5), (2024, 11),
            (2025, 5), (2025, 11),
        ],
    },
    "organic_search": {
        # Near-flat spend (SEO is mostly labor), but grows ~15%/yr as content compounds.
        "phase_shift": 0,
        "amplitude": 0.05,
        "base_trend_yr": 0.15,
        "noise_pct": 0.05,
        "flight_months": [],
        "spike_months": [],
    },
    "social_paid": {
        # Summer campaign focus (CMO-driven), less in Q4 when display takes over.
        "phase_shift": 6,  # peak in Jul
        "amplitude": 0.35,
        "base_trend_yr": 0.12,
        "noise_pct": 0.12,
        "flight_months": [],
        "spike_months": [(2023, 9), (2024, 3)],  # product-launch pushes
    },
    "display": {
        # Campaign-flighted: heavy in holiday run-up, minimal in Feb/Mar/Jul/Aug.
        "phase_shift": 10,  # peak in Nov
        "amplitude": 0.45,
        "base_trend_yr": -0.05,  # declining as programmatic gets expensive
        "noise_pct": 0.10,
        "flight_months": [1, 2, 6, 7],  # off in Feb, Mar, Jul, Aug
        "spike_months": [],
    },
    "email": {
        # Strong Q4 push (Black Friday, EOY) plus mid-year promo flights.
        "phase_shift": 11,  # peak in Dec
        "amplitude": 0.55,
        "base_trend_yr": 0.05,
        "noise_pct": 0.08,
        "flight_months": [],
        "spike_months": [
            (2022, 11), (2023, 6), (2023, 11), (2024, 6), (2024, 11), (2025, 6),
        ],
    },
    "video_youtube": {
        # Two big quarterly campaign pushes, quiet in between.
        "phase_shift": 3,  # peak in Apr
        "amplitude": 0.30,
        "base_trend_yr": 0.10,
        "noise_pct": 0.12,
        "flight_months": [0, 1, 7, 8],  # quiet Jan-Feb, Aug-Sep
        "spike_months": [(2022, 6), (2023, 6), (2024, 6), (2025, 6)],  # annual summer push
    },
    "events": {
        # Pure spike behavior: trade shows happen in specific months. Mostly off.
        "phase_shift": 4,  # nominal peak in May
        "amplitude": 0.20,
        "base_trend_yr": 0.05,
        "noise_pct": 0.15,
        "flight_months": [0, 1, 6, 7, 11],  # off outside event season
        "spike_months": [
            (2022, 3), (2022, 9),
            (2023, 3), (2023, 9), (2023, 10),
            (2024, 3), (2024, 9),
            (2025, 3), (2025, 9), (2025, 10),
        ],
    },
    "direct_mail": {
        # Holiday-heavy catalog drops, flat through most of the year.
        "phase_shift": 10,  # peak in Nov
        "amplitude": 0.50,
        "base_trend_yr": -0.08,  # declining channel
        "noise_pct": 0.12,
        "flight_months": [1, 2, 3, 5, 6, 7],  # only active Aug-Dec and Jan/Apr
        "spike_months": [],
    },
    # TV is classic flighted buying — big Q4 holiday push, big spring launch
    # window, mostly dark in summer.
    "tv_national": {
        "phase_shift": 10,  # peak in Nov
        "amplitude": 0.60,
        "base_trend_yr": -0.04,  # slowly shifting to digital
        "noise_pct": 0.18,  # offline buys are lumpier than digital
        "flight_months": [6, 7],  # dark Jul-Aug
        "spike_months": [
            (2022, 10), (2023, 10), (2024, 10), (2025, 10),  # annual Q4 push
            (2023, 3), (2024, 3),  # spring launches
        ],
    },
    "radio": {
        # Drive-time buys that correlate with retail promotions
        "phase_shift": 9,  # peak in Oct
        "amplitude": 0.45,
        "base_trend_yr": -0.06,
        "noise_pct": 0.15,
        "flight_months": [6, 7],
        "spike_months": [(2022, 10), (2023, 10), (2024, 10), (2025, 10)],
    },
    "ooh": {
        # Quarterly billboard/transit creative refresh. Steady-ish but dark
        # in periods without active creative.
        "phase_shift": 5,  # peak in Jun
        "amplitude": 0.35,
        "base_trend_yr": 0.02,  # modest growth (programmatic OOH)
        "noise_pct": 0.20,
        "flight_months": [0, 1],  # quiet Jan-Feb
        "spike_months": [(2023, 5), (2024, 5), (2025, 5)],
    },
    # Call center scales with other channels' lead flow — its "spikes" mirror
    # paid search and direct mail peak months.
    "call_center": {
        "phase_shift": 10,  # peak in Nov
        "amplitude": 0.30,
        "base_trend_yr": 0.03,
        "noise_pct": 0.10,
        "flight_months": [],  # always-on
        "spike_months": [
            (2022, 11), (2023, 11), (2024, 11), (2025, 11),
        ],
    },
}


def _channel_spend_multiplier(channel: str, month_idx: int, month) -> float:
    """Compute a channel-specific spend multiplier for a given month.

    Returns a value typically in [0.1, 2.5] that should multiply the channel's
    base spend. Combines channel-specific seasonality, growth trend, campaign
    flighting, and launch-event spikes. Intentionally NOT a function of the
    shared SEASONALITY array -- that's the whole point.
    """
    pattern = CHANNEL_PATTERNS.get(channel)
    if pattern is None:
        # Fallback: use shared seasonality if channel has no custom pattern.
        return SEASONALITY[month_idx % 12]

    month_of_year = month_idx % 12
    years_elapsed = month_idx / 12.0

    # Channel-specific sinusoidal seasonality, peaked at phase_shift month.
    # cos(0) = 1 at peak, so (month - phase) should be 0 at peak.
    phase_rad = 2 * np.pi * ((month_of_year - pattern["phase_shift"]) % 12) / 12
    seasonal = 1.0 + pattern["amplitude"] * np.cos(phase_rad)

    # Growth trend over the 4-year span.
    trend = 1.0 + pattern["base_trend_yr"] * years_elapsed

    # Flight: is this a month the channel is mostly off? If so, reduce to 10-20%.
    if month_of_year in pattern["flight_months"]:
        flight_mult = np.random.uniform(0.1, 0.25)
    else:
        flight_mult = 1.0

    # Event spikes. Check (year, month_of_year_1indexed) tuples.
    year_actual = month.year
    month_actual = month.month
    spike_mult = 1.0
    for yr, mo in pattern["spike_months"]:
        if year_actual == yr and month_actual == mo:
            spike_mult = np.random.uniform(2.0, 3.0)
            break

    return seasonal * trend * flight_mult * spike_mult


def _diminishing_returns(spend: float, saturation: float, alpha: float = 0.45) -> float:
    """Power-law diminishing returns: response = spend^alpha, scaled by saturation.
    alpha=0.45 gives visible diminishing returns: doubling spend only gives ~1.37x output."""
    if saturation is None or saturation == 0:
        return spend
    normalized = spend / saturation
    return saturation * (normalized ** alpha)


def _add_noise(value: float, noise_pct: float = 0.1) -> float:
    return max(0, value * (1 + np.random.normal(0, noise_pct)))


def generate_campaign_performance() -> pd.DataFrame:
    """Generate monthly campaign-level performance data."""
    rows = []

    for month_idx, month in enumerate(MONTHS):
        # Shared macro-seasonality applied MILDLY — most of the channel
        # variation comes from CHANNEL_PATTERNS, not this. Softened to
        # [0.92, 1.08] so it's a faint background signal, not the driver.
        macro_season = 1.0 + 0.08 * (SEASONALITY[month_idx % 12] - 1.0) / 0.3

        for channel_name, channel_props in CHANNELS.items():
            campaigns = CAMPAIGNS_PER_CHANNEL[channel_name]

            # Channel-specific temporal signature -- the key to identifiability.
            channel_mult = _channel_spend_multiplier(channel_name, month_idx, month)

            for campaign in campaigns:
                for region in REGIONS:
                    base_spend = _get_base_spend(channel_name, campaign)
                    regional_mult = {"North": 1.1, "South": 0.9, "East": 1.0, "West": 1.05}[region]

                    # Combine channel-specific pattern (primary) + mild macro (secondary).
                    monthly_spend = _add_noise(
                        base_spend * channel_mult * macro_season * regional_mult,
                        CHANNEL_PATTERNS.get(channel_name, {}).get("noise_pct", 0.12),
                    )

                    if channel_name == "organic_search":
                        # SEO is a near-fixed labor cost, independent of the
                        # above pattern except for the mild growth trend.
                        sk_trend = 1.0 + 0.15 * (month_idx / 12.0)  # ~15%/yr growth
                        monthly_spend = _add_noise(2000 * regional_mult * sk_trend, 0.05)

                    # Apply diminishing returns to get effective output
                    effective_output = _diminishing_returns(
                        monthly_spend, channel_props["saturation_point"]
                    )

                    # Calculate funnel metrics — diminishing returns flow through
                    impressions = _add_noise(effective_output * _get_impression_mult(channel_name), 0.15)
                    clicks = _add_noise(impressions * _get_ctr(channel_name, campaign), 0.12)
                    leads = _add_noise(clicks * _get_lead_rate(channel_name), 0.15)
                    mqls = _add_noise(leads * np.random.uniform(0.3, 0.6), 0.1)
                    sqls = _add_noise(mqls * np.random.uniform(0.25, 0.5), 0.1)
                    # Conversions: DO NOT re-apply season — it's already in spend→effective_output
                    # This ensures high spend months show lower ROI (diminishing returns)
                    conversions = _add_noise(sqls * channel_props["base_cvr"] * 10, 0.18)

                    # Revenue per conversion varies by product mix
                    avg_order_value = _add_noise(_get_aov(channel_name), 0.1)
                    revenue = conversions * avg_order_value

                    # Calibrate to target channel ROAS. Without this, the raw
                    # funnel produces wildly-uneven ROAS across channels
                    # (events at 125x, display at 0.07x) because the original
                    # CTR/CVR/AOV constants were set for visual differentiation
                    # rather than portfolio balance. The calibration preserves
                    # all funnel counts (clicks, leads, conversions) — only
                    # the final revenue is scaled.
                    revenue = revenue * _channel_revenue_calibration(channel_name)

                    # Offline-specific metrics. For digital channels these
                    # are 0 (the column exists for schema stability, but the
                    # data is not meaningful). For offline channels, compute
                    # based on spend and channel basis:
                    #   - TV/radio: GRPs (gross rating points); 1 GRP ≈ 1%
                    #     of target audience reached once. Buying power varies
                    #     by daypart and network; rough rule: $400-$1000 per GRP.
                    #   - OOH: reach — number of unique people passing the
                    #     location/transit line in the month; store_visits
                    #     as a direct offline response signal.
                    #   - Events: attendees — direct count.
                    #   - Direct mail: dealer_enquiries — inbound inquiries
                    #     from mailer recipients.
                    #   - Call center: calls_generated — inbound calls handled.
                    grps = 0.0
                    reach = 0.0
                    store_visits = 0.0
                    calls_generated = 0.0
                    event_attendees = 0.0
                    dealer_enquiries = 0.0

                    if channel_name == "tv_national":
                        grps = _add_noise(monthly_spend / 800, 0.15)
                        reach = _add_noise(min(grps * 1_000_000 * 0.008, 50_000_000), 0.10)
                    elif channel_name == "radio":
                        grps = _add_noise(monthly_spend / 400, 0.18)
                        reach = _add_noise(min(grps * 1_000_000 * 0.006, 30_000_000), 0.12)
                    elif channel_name == "ooh":
                        reach = _add_noise(monthly_spend / 0.80, 0.20)
                        store_visits = _add_noise(reach * 0.002, 0.25)
                    elif channel_name == "call_center":
                        calls_generated = _add_noise(monthly_spend / 18, 0.10)
                    elif channel_name == "events":
                        event_attendees = _add_noise(monthly_spend / 120, 0.20)
                    elif channel_name == "direct_mail":
                        pieces_mailed = monthly_spend / 0.50
                        dealer_enquiries = _add_noise(pieces_mailed * 0.008, 0.15)

                    # CX signals
                    bounce_rate = _get_bounce_rate(channel_name, campaign)
                    avg_session_duration = _add_noise(_get_session_duration(channel_name), 0.2)
                    form_completion_rate = _add_noise(_get_form_rate(channel_name, campaign), 0.1)
                    unsubscribe_rate = _get_unsub_rate(channel_name) if channel_name == "email" else 0
                    nps = _add_noise(_get_nps(channel_name), 0.05)

                    # Confidence tier
                    confidence = "High" if channel_props["type"] == "online" else "Medium"
                    if channel_name in ("events", "direct_mail", "tv_national", "radio", "ooh", "call_center"):
                        confidence = "Model-Estimated"

                    rows.append({
                        "date": month,
                        "month": month.strftime("%Y-%m"),
                        "channel": channel_name,
                        "channel_type": channel_props["type"],
                        # New taxonomy columns — every downstream engine that
                        # cares about offline handling reads these.
                        "attribution_basis": channel_props.get("attribution_basis", "click"),
                        "primary_metric": channel_props.get("primary_metric", "clicks"),
                        "campaign": campaign,
                        "region": region,
                        "product": np.random.choice(PRODUCTS, p=[0.45, 0.35, 0.20]),
                        "spend": round(monthly_spend, 2),
                        "impressions": int(max(0, impressions)),
                        "clicks": int(max(0, clicks)),
                        "leads": int(max(0, leads)),
                        "mqls": int(max(0, mqls)),
                        "sqls": int(max(0, sqls)),
                        "conversions": int(max(0, conversions)),
                        "revenue": round(max(0, revenue), 2),
                        "bounce_rate": round(min(1, max(0, bounce_rate)), 3),
                        "avg_session_duration_sec": round(max(0, avg_session_duration), 1),
                        "form_completion_rate": round(min(1, max(0, form_completion_rate)), 3),
                        "unsubscribe_rate": round(min(0.1, max(0, unsubscribe_rate)), 4),
                        "nps_score": round(min(100, max(-100, nps)), 1),
                        "confidence_tier": confidence,
                        # Offline-specific. Zero for digital channels; populated
                        # for the offline channels that use each metric.
                        "grps": round(max(0, grps), 2),
                        "reach": int(max(0, reach)),
                        "store_visits": int(max(0, store_visits)),
                        "calls_generated": int(max(0, calls_generated)),
                        "event_attendees": int(max(0, event_attendees)),
                        "dealer_enquiries": int(max(0, dealer_enquiries)),
                    })
    
    return pd.DataFrame(rows)


def generate_user_journeys(campaign_df: pd.DataFrame, n_journeys: int = 5000) -> pd.DataFrame:
    """
    Generate user-level journey data for attribution modeling.
    Each journey has 1-7 touchpoints across channels before conversion.
    """
    # Weight channels by their share of conversions
    channel_conv = campaign_df.groupby("channel")["conversions"].sum()
    channel_weights = (channel_conv / channel_conv.sum()).to_dict()
    channels = list(channel_weights.keys())
    weights = [channel_weights[c] for c in channels]
    
    journeys = []
    
    for journey_id in range(n_journeys):
        # Number of touchpoints: weighted toward 2-4
        n_touchpoints = np.random.choice([1, 2, 3, 4, 5, 6, 7], p=[0.1, 0.25, 0.3, 0.2, 0.08, 0.05, 0.02])
        
        # Pick channels for each touchpoint (with some sequential logic)
        journey_channels = []
        for tp in range(n_touchpoints):
            if tp == 0:
                # First touch biased toward awareness channels
                awareness_weights = _adjust_weights_for_stage(weights, channels, "awareness")
                ch = np.random.choice(channels, p=awareness_weights)
            elif tp == n_touchpoints - 1:
                # Last touch biased toward conversion channels
                conv_weights = _adjust_weights_for_stage(weights, channels, "conversion")
                ch = np.random.choice(channels, p=conv_weights)
            else:
                ch = np.random.choice(channels, p=weights)
            journey_channels.append(ch)
        
        # Assign campaigns from each channel
        base_date = pd.Timestamp(np.random.choice(MONTHS))
        converted = np.random.random() < 0.35  # 35% conversion rate for journeys
        revenue = _add_noise(np.random.choice([500, 1200, 2500, 5000]), 0.3) if converted else 0
        
        for tp_idx, ch in enumerate(journey_channels):
            campaigns = CAMPAIGNS_PER_CHANNEL[ch]
            campaign = np.random.choice(campaigns)
            
            tp_date = base_date + timedelta(days=int(tp_idx) * int(np.random.randint(1, 14)))
            
            journeys.append({
                "journey_id": f"J{journey_id:05d}",
                "touchpoint_order": tp_idx + 1,
                "total_touchpoints": n_touchpoints,
                "date": tp_date,
                "channel": ch,
                "campaign": campaign,
                "converted": converted,
                "conversion_revenue": round(revenue, 2) if tp_idx == n_touchpoints - 1 and converted else 0,
            })
    
    return pd.DataFrame(journeys)


# --- Helper functions ---

def _get_base_spend(channel: str, campaign: str) -> float:
    base_spends = {
        "paid_search": 35000, "social_paid": 28000, "display": 18000,
        "email": 5000, "video_youtube": 22000, "events": 45000, "direct_mail": 15000,
        "organic_search": 2000,
        # Offline broadcast — large per-buy spends
        "tv_national": 85000, "radio": 22000, "ooh": 35000,
        # Call center — operational cost, moderate scale
        "call_center": 18000,
    }
    # Vary by campaign within channel
    campaign_mult = 0.6 + hash(campaign) % 100 / 100 * 0.8
    return base_spends.get(channel, 10000) * campaign_mult


def _get_impression_mult(channel: str) -> float:
    return {"paid_search": 8, "organic_search": 12, "social_paid": 15,
            "display": 25, "email": 3, "video_youtube": 10,
            "events": 0.5, "direct_mail": 0.8,
            # Offline: we still compute an "impressions" equivalent for
            # reporting parity — for TV/radio/OOH this is essentially
            # reach × frequency. Large multipliers reflect mass reach.
            "tv_national": 60, "radio": 45, "ooh": 80,
            "call_center": 0.3}.get(channel, 5)


def _get_ctr(channel: str, campaign: str) -> float:
    # For offline channels, "CTR" is a proxy — it's the rate at which
    # an impression produces some measurable engagement (a call, a visit).
    # Kept small because mass-reach impressions don't individually drive
    # action — they build brand awareness that pays off through other channels.
    base = {"paid_search": 0.045, "organic_search": 0.035, "social_paid": 0.012,
            "display": 0.004, "email": 0.22, "video_youtube": 0.008,
            "events": 0.5, "direct_mail": 0.15,
            "tv_national": 0.0015, "radio": 0.0025, "ooh": 0.0008,
            "call_center": 0.85}.get(channel, 0.02)  # most "impressions" for call center are actual calls
    return _add_noise(base, 0.15)


def _get_lead_rate(channel: str) -> float:
    return {"paid_search": 0.08, "organic_search": 0.06, "social_paid": 0.05,
            "display": 0.02, "email": 0.12, "video_youtube": 0.03,
            "events": 0.35, "direct_mail": 0.08,
            # Offline: broadcast drives brand consideration (lower conversion
            # from impressions to leads), call center converts inbound calls
            # at high rate.
            "tv_national": 0.08, "radio": 0.10, "ooh": 0.06,
            "call_center": 0.55}.get(channel, 0.05)


def _get_aov(channel: str) -> float:
    return {"paid_search": 1800, "organic_search": 2200, "social_paid": 1200,
            "display": 900, "email": 1500, "video_youtube": 1100,
            "events": 5500, "direct_mail": 2000,
            # Offline AOVs — broadcast drives premium branded purchases;
            # call center handles larger considered transactions
            "tv_national": 2400, "radio": 1800, "ooh": 1600,
            "call_center": 3200}.get(channel, 1500)


def _get_bounce_rate(channel: str, campaign: str) -> float:
    base = {"paid_search": 0.38, "organic_search": 0.42, "social_paid": 0.55,
            "display": 0.65, "email": 0.30, "video_youtube": 0.50,
            "events": 0.15, "direct_mail": 0.45,
            # Offline doesn't have web bounces — these are proxy values for
            # reporting consistency only (the downstream UI can hide them)
            "tv_national": 0.50, "radio": 0.50, "ooh": 0.55,
            "call_center": 0.20}.get(channel, 0.45)
    # Some campaigns have deliberately bad landing pages (for diagnostics)
    if "Retargeting" in campaign:
        base *= 0.75  # retargeting bounces less
    if "Awareness" in campaign or "Brand" in campaign:
        base *= 1.15  # awareness traffic bounces more
    return _add_noise(base, 0.1)


def _get_session_duration(channel: str) -> float:
    return {"paid_search": 145, "organic_search": 195, "social_paid": 85,
            "display": 55, "email": 165, "video_youtube": 70,
            "events": 300, "direct_mail": 120,
            "tv_national": 90, "radio": 75, "ooh": 60,
            "call_center": 240}.get(channel, 100)


def _get_form_rate(channel: str, campaign: str) -> float:
    base = {"paid_search": 0.12, "organic_search": 0.09, "social_paid": 0.06,
            "display": 0.025, "email": 0.18, "video_youtube": 0.04,
            "events": 0.45, "direct_mail": 0.10,
            "tv_national": 0.05, "radio": 0.06, "ooh": 0.04,
            "call_center": 0.40}.get(channel, 0.08)
    # Deliberately create good-engagement-poor-conversion signals for some
    if campaign in ("Social_TikTok_Brand", "Display_Native"):
        base *= 0.4  # high CTR but poor form completion
    return base


def _get_unsub_rate(channel: str) -> float:
    return _add_noise(0.004, 0.3)


def _get_nps(channel: str) -> float:
    return {"paid_search": 35, "organic_search": 52, "social_paid": 28,
            "display": 18, "email": 42, "video_youtube": 30,
            "events": 65, "direct_mail": 25,
            "tv_national": 40, "radio": 35, "ooh": 30,
            "call_center": 55}.get(channel, 30)


def _adjust_weights_for_stage(weights, channels, stage):
    """Adjust channel weights based on funnel stage."""
    adjusted = np.array(weights, dtype=float)
    for i, ch in enumerate(channels):
        if stage == "awareness":
            if ch in ("display", "social_paid", "video_youtube"):
                adjusted[i] *= 2.0
            elif ch in ("email", "direct_mail"):
                adjusted[i] *= 0.4
        elif stage == "conversion":
            if ch in ("paid_search", "email", "organic_search"):
                adjusted[i] *= 2.5
            elif ch in ("display", "video_youtube"):
                adjusted[i] *= 0.5
    adjusted = adjusted / adjusted.sum()
    return adjusted


def generate_market_events() -> pd.DataFrame:
    """
    Generate a realistic forward-looking events calendar.

    For a pitch demo, we want a mix:
      - 1-2 big positive upcoming events (holiday, product launch)
      - 1 negative risk event (competitor action)
      - 1-2 recent-past events for context

    Dates are relative to today so the demo always looks current.
    """
    today = pd.Timestamp.now().normalize()
    rows = [
        # Big upcoming positive — next ~30-60 days
        {
            "event_date": (today + pd.Timedelta(days=45)).date(),
            "event_end_date": (today + pd.Timedelta(days=47)).date(),
            "event_type": "holiday", "event_name": "Diwali 2026",
            "impact_direction": "positive", "impact_magnitude": "high",
            "impact_pct": 22.0,
            "affected_channels": "paid_search;social_paid;tv_national",
            "confidence": "high",
        },
        # Medium upcoming
        {
            "event_date": (today + pd.Timedelta(days=75)).date(),
            "event_end_date": (today + pd.Timedelta(days=76)).date(),
            "event_type": "campaign", "event_name": "Black Friday 2026",
            "impact_direction": "positive", "impact_magnitude": "high",
            "impact_pct": 18.0,
            "affected_channels": "paid_search;social_paid;email",
            "confidence": "high",
        },
        # Negative upcoming risk
        {
            "event_date": (today + pd.Timedelta(days=20)).date(),
            "event_end_date": (today + pd.Timedelta(days=30)).date(),
            "event_type": "competitor", "event_name": "Competitor IPL Sponsorship",
            "impact_direction": "negative", "impact_magnitude": "medium",
            "impact_pct": -8.0,
            "affected_channels": "tv_national;ooh",
            "confidence": "estimated",
        },
        # Recent past (context, not acted on)
        {
            "event_date": (today - pd.Timedelta(days=20)).date(),
            "event_end_date": (today - pd.Timedelta(days=18)).date(),
            "event_type": "holiday", "event_name": "Independence Day 2026",
            "impact_direction": "positive", "impact_magnitude": "medium",
            "impact_pct": 12.0,
            "affected_channels": "tv_national;paid_search",
            "confidence": "high",
        },
    ]
    return pd.DataFrame(rows)


def generate_market_trends() -> pd.DataFrame:
    """
    Generate realistic CPC/CPM trend data for key channels over the
    past 12 months. Shows rising costs on search (competitive pressure),
    stable social, declining display.
    """
    today = pd.Timestamp.now().normalize()
    rows = []

    # Paid search CPC — rising steadily
    base_cpc_ps = 1.85
    for i in range(12, -1, -1):
        d = today - pd.Timedelta(days=30 * i)
        inflation = 1.0 + (12 - i) * 0.018  # ~22% over 12 months
        rows.append({
            "metric_type": "cpc_trend", "channel": "paid_search",
            "date": d.date(), "value": round(base_cpc_ps * inflation, 2),
            "yoy_change_pct": 22.0,
        })

    # Social paid CPC — modest rise
    base_cpc_sp = 0.85
    for i in range(12, -1, -1):
        d = today - pd.Timedelta(days=30 * i)
        inflation = 1.0 + (12 - i) * 0.006  # ~8% over 12 months
        rows.append({
            "metric_type": "cpc_trend", "channel": "social_paid",
            "date": d.date(), "value": round(base_cpc_sp * inflation, 2),
            "yoy_change_pct": 8.0,
        })

    # Display CPM — declining (oversupply)
    base_cpm_d = 4.20
    for i in range(12, -1, -1):
        d = today - pd.Timedelta(days=30 * i)
        deflation = 1.0 - (12 - i) * 0.011  # ~-13% over 12 months
        rows.append({
            "metric_type": "cpm_trend", "channel": "display",
            "date": d.date(), "value": round(base_cpm_d * deflation, 2),
            "yoy_change_pct": -13.0,
        })

    # Video YouTube CPM — flat
    base_cpm_yt = 9.50
    for i in range(12, -1, -1):
        d = today - pd.Timedelta(days=30 * i)
        rows.append({
            "metric_type": "cpm_trend", "channel": "video_youtube",
            "date": d.date(), "value": round(base_cpm_yt * (1.0 + (12-i)*0.002), 2),
            "yoy_change_pct": 2.5,
        })

    return pd.DataFrame(rows)


def generate_competitive_data(campaign_df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate competitive intelligence data — estimated competitor spend
    per channel per quarter. Creates a scenario where:
      - We have LOW SOV on tv_national (dominant competitor)
      - We have LOW SOV on ooh (also losing ground)
      - We have STRONG SOV on paid_search and events (winning)
      - Neutral elsewhere
    """
    today = pd.Timestamp.now().normalize()
    our_spend = campaign_df.groupby("channel")["spend"].sum().to_dict()

    # Competitor spend multipliers — higher = we're losing SOV
    competitor_mult = {
        "tv_national": 3.5,   # they spend 3.5x what we do → our SOV ~22%
        "ooh": 2.8,            # → our SOV ~26%
        "paid_search": 0.5,    # we dominate → SOV ~67%
        "events": 0.4,         # we dominate → SOV ~71%
        "social_paid": 1.2,    # slightly behind → SOV ~45%
        "tv_regional": 1.5,
        "direct_mail": 1.0,
        "radio": 1.8,
        "display": 1.1,
        "video_youtube": 1.3,
        "email": 0.3,
        "call_center": 0.6,
        "organic_search": 0.8,
    }

    rows = []
    # Two time points for growth calculation
    for days_back in [365, 0]:
        date = today - pd.Timedelta(days=days_back)
        for channel, spend in our_spend.items():
            mult = competitor_mult.get(channel, 1.0)
            # Competitor growth pattern: TV and OOH competitors growing fast
            growth = 1.0
            if days_back == 0 and channel in ("tv_national", "ooh"):
                growth = 1.15  # 15% growth
            elif days_back == 0:
                growth = 1.05  # 5% baseline market growth
            competitor_spend = spend * mult * growth
            rows.append({
                "date": date.date(),
                "channel": channel,
                "estimated_spend": round(competitor_spend, 0),
                "source": "SimilarWeb estimate",
            })

    return pd.DataFrame(rows)


def generate_all_data() -> Dict[str, pd.DataFrame]:
    """Generate all mock datasets and return as dict of DataFrames."""
    print("Generating campaign performance data...")
    campaign_df = generate_campaign_performance()
    
    print("Generating user journey data...")
    journey_df = generate_user_journeys(campaign_df)

    print("Generating market events...")
    events_df = generate_market_events()

    print("Generating market trends...")
    trends_df = generate_market_trends()

    print("Generating competitive data...")
    competitive_df = generate_competitive_data(campaign_df)
    
    print(f"Campaign data: {len(campaign_df)} rows")
    print(f"Journey data: {len(journey_df)} rows")
    print(f"Channels: {campaign_df['channel'].nunique()}")
    print(f"Campaigns: {campaign_df['campaign'].nunique()}")
    print(f"Date range: {campaign_df['date'].min()} to {campaign_df['date'].max()}")
    print(f"Total spend: ${campaign_df['spend'].sum():,.0f}")
    print(f"Total revenue: ${campaign_df['revenue'].sum():,.0f}")
    print(f"Overall ROI: {(campaign_df['revenue'].sum() - campaign_df['spend'].sum()) / campaign_df['spend'].sum():.2f}x")
    print(f"Events: {len(events_df)} · Trends: {len(trends_df)} · Competitive: {len(competitive_df)} rows")
    
    return {
        "campaign_performance": campaign_df,
        "user_journeys": journey_df,
        "market_events": events_df,
        "market_trends": trends_df,
        "competitive_data": competitive_df,
    }


def export_to_csv(data: Dict[str, pd.DataFrame], output_dir: str = "./data"):
    """Export all datasets to CSV files."""
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    for name, df in data.items():
        path = os.path.join(output_dir, f"{name}.csv")
        df.to_csv(path, index=False)
        print(f"Exported {name} to {path} ({len(df)} rows)")


if __name__ == "__main__":
    data = generate_all_data()
    export_to_csv(data)
