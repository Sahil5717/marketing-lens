#!/usr/bin/env python3
"""
Unit tests for market_adjustments engine.

Focus: deterministic behavior under various external data states —
no market data (should produce empty), events only, trends only,
competitive only, all three combined, override application.
"""
import sys

from engines.market_adjustments import generate_market_adjustments, apply_overrides


_pass = 0
_fail = 0


def assert_test(name, ok, detail=""):
    global _pass, _fail
    if ok:
        print(f"  PASS  {name}")
        _pass += 1
    else:
        print(f"  FAIL  {name}: {detail}")
        _fail += 1


# ── Fixtures ──

def make_moves():
    """Representative plan moves — mix of increases, decreases, and holds."""
    return [
        {"channel": "paid_search", "action": "increase", "revenue_delta": 2_500_000,
         "current_spend": 3_000_000, "optimized_spend": 5_500_000},
        {"channel": "tv_national", "action": "decrease", "revenue_delta": -1_200_000,
         "current_spend": 10_000_000, "optimized_spend": 8_000_000},
        {"channel": "events", "action": "increase", "revenue_delta": 800_000,
         "current_spend": 2_000_000, "optimized_spend": 2_800_000},
        {"channel": "email", "action": "hold", "revenue_delta": 0,
         "current_spend": 500_000, "optimized_spend": 500_000},
    ]


def make_events_upcoming():
    return {
        "events": [
            {
                "date": "2026-10-12", "end_date": "2026-10-14",
                "name": "Diwali 2026", "type": "holiday",
                "direction": "positive", "magnitude": "high",
                "impact_pct": None,
                "affected_channels": ["paid_search", "social_paid"],
                "is_upcoming": True, "days_away": 176, "confidence": "high",
            },
        ],
    }


def make_trends_rising_cpc():
    return {
        "cost_adjustments": {
            "paid_search": {
                "metric": "cpc_trend",
                "current_value": 2.45, "trend_start": 2.00,
                "inflation_factor": 1.225,
                "yoy_change_pct": 22.5,  # well above 5% noise threshold
            },
        },
    }


def make_competitive_low_sov_on_tv():
    return {
        "share_of_voice": {
            "tv_national": {
                "our_spend": 10_000_000, "competitor_spend": 35_000_000,
                "total_market": 45_000_000,
                "share_of_voice": 0.222,  # well below 0.4 threshold
                "competitive_pressure_index": 0.222,
            },
            "paid_search": {  # high SOV; should not produce adjustment
                "our_spend": 3_000_000, "competitor_spend": 2_000_000,
                "total_market": 5_000_000,
                "share_of_voice": 0.6,
            },
        },
    }


# ── Tests ──

# Empty inputs
payload = generate_market_adjustments(make_moves(), None, None, None)
assert_test(
    "No external data → empty adjustments list",
    payload["adjustments"] == [],
    f"got {len(payload['adjustments'])} adjustments",
)
assert_test(
    "No external data → has_market_data False",
    payload["summary"]["has_market_data"] is False,
    "",
)
assert_test(
    "No external data → adjusted_total equals baseline_total",
    payload["baseline_total_revenue_delta"] == payload["adjusted_total_revenue_delta"],
    "",
)

# Events only
payload = generate_market_adjustments(make_moves(), make_events_upcoming(), None, None)
assert_test(
    "Events only → at least 1 adjustment",
    len(payload["adjustments"]) >= 1,
    f"got {len(payload['adjustments'])}",
)
evt_adj = payload["adjustments"][0]
assert_test(
    "Event adjustment has correct source",
    evt_adj["source"] == "events",
    f"source={evt_adj['source']}",
)
assert_test(
    "Event adjustment is baseline_uplift kind",
    evt_adj["kind"] == "baseline_uplift",
    f"kind={evt_adj['kind']}",
)
assert_test(
    "Event adjustment has positive magnitude (direction=positive, high magnitude)",
    evt_adj["magnitude_pct"] > 0,
    f"magnitude={evt_adj['magnitude_pct']}",
)
assert_test(
    "Event adjustment carries source_ref",
    "Diwali" in evt_adj.get("source_ref", ""),
    f"source_ref={evt_adj.get('source_ref')}",
)
assert_test(
    "Event adjustment carries rationale mentioning date",
    "2026-10-12" in evt_adj.get("rationale", ""),
    "",
)
assert_test(
    "Event adjustment carries formula string",
    "%" in evt_adj.get("formula", ""),
    f"formula={evt_adj.get('formula')}",
)
assert_test(
    "Event adjustment applied=True by default",
    evt_adj.get("applied") is True,
    "",
)

# Non-upcoming events should be skipped
past_events = {
    "events": [
        {**make_events_upcoming()["events"][0], "is_upcoming": False, "days_away": -30},
    ],
}
payload = generate_market_adjustments(make_moves(), past_events, None, None)
assert_test(
    "Past events (is_upcoming=False) produce no adjustments",
    len(payload["adjustments"]) == 0,
    f"got {len(payload['adjustments'])}",
)

# Trends with rising CPC
payload = generate_market_adjustments(make_moves(), None, make_trends_rising_cpc(), None)
assert_test(
    "Rising CPC on paid_search → 1 adjustment",
    len(payload["adjustments"]) == 1,
    f"got {len(payload['adjustments'])}",
)
tr_adj = payload["adjustments"][0]
assert_test(
    "Cost-trend adjustment has source=cost_trends",
    tr_adj["source"] == "cost_trends",
    "",
)
assert_test(
    "Rising CPC produces negative magnitude (dampening)",
    tr_adj["magnitude_pct"] < 0,
    f"magnitude={tr_adj['magnitude_pct']}",
)
assert_test(
    "Rising CPC revenue_delta is negative (dampens positive base)",
    tr_adj["revenue_delta"] < 0,
    f"revenue_delta={tr_adj['revenue_delta']}",
)
assert_test(
    "Cost-trend affects paid_search only",
    tr_adj["affected_channels"] == ["paid_search"],
    f"affected_channels={tr_adj['affected_channels']}",
)

# Noise-level trends (<5%) should be skipped
quiet_trends = {
    "cost_adjustments": {
        "paid_search": {
            "metric": "cpc_trend", "inflation_factor": 1.03,
            "yoy_change_pct": 3.0,  # below noise threshold
        },
    },
}
payload = generate_market_adjustments(make_moves(), None, quiet_trends, None)
assert_test(
    "Sub-5% CPC trends are filtered as noise",
    len(payload["adjustments"]) == 0,
    f"got {len(payload['adjustments'])}",
)

# Competitive: low SOV on reach channel
payload = generate_market_adjustments(make_moves(), None, None, make_competitive_low_sov_on_tv())
assert_test(
    "Low-SOV TV → 1 competitive adjustment (paid_search SOV ignored, no move on TV issue)",
    # tv_national has a move (decrease), so dampening applies
    len(payload["adjustments"]) == 1,
    f"got {len(payload['adjustments'])}: {[a['id'] for a in payload['adjustments']]}",
)
if payload["adjustments"]:
    comp_adj = payload["adjustments"][0]
    assert_test(
        "Competitive adjustment source=competitive",
        comp_adj["source"] == "competitive",
        "",
    )
    assert_test(
        "Competitive adjustment kind=reach_dampening",
        comp_adj["kind"] == "reach_dampening",
        "",
    )
    assert_test(
        "Competitive adjustment affects tv_national",
        comp_adj["affected_channels"] == ["tv_national"],
        "",
    )
    assert_test(
        "Competitive adjustment magnitude is negative",
        comp_adj["magnitude_pct"] < 0,
        "",
    )

# Digital channels should NOT be adjusted by competitive SOV
digital_only_sov = {
    "share_of_voice": {
        "paid_search": {"share_of_voice": 0.2},  # low but digital, should be skipped
    },
}
payload = generate_market_adjustments(make_moves(), None, None, digital_only_sov)
assert_test(
    "Digital channels skipped from competitive dampening",
    len(payload["adjustments"]) == 0,
    f"got {len(payload['adjustments'])}",
)

# All three combined
payload = generate_market_adjustments(
    make_moves(),
    make_events_upcoming(),
    make_trends_rising_cpc(),
    make_competitive_low_sov_on_tv(),
)
assert_test(
    "All three sources combined → multiple adjustments",
    len(payload["adjustments"]) >= 3,
    f"got {len(payload['adjustments'])}",
)
sources_seen = {a["source"] for a in payload["adjustments"]}
assert_test(
    "All three sources represented",
    sources_seen == {"events", "cost_trends", "competitive"},
    f"sources={sources_seen}",
)
assert_test(
    "Combined payload has non-zero net_delta",
    payload["summary"]["net_delta"] != 0,
    "",
)

# Overrides
payload = generate_market_adjustments(make_moves(), None, make_trends_rising_cpc(), None)
baseline_net = payload["summary"]["net_delta"]
overrides = {payload["adjustments"][0]["id"]: False}
payload2 = apply_overrides(payload, overrides)
assert_test(
    "Override disables adjustment (applied=False)",
    payload2["adjustments"][0]["applied"] is False,
    "",
)
assert_test(
    "Override recomputes net_delta to 0 when only adj is toggled off",
    payload2["summary"]["net_delta"] == 0,
    f"net_delta={payload2['summary']['net_delta']}",
)
assert_test(
    "Override keeps adjustment in list (analyst can re-enable)",
    len(payload2["adjustments"]) == 1,
    "",
)

print()
print("=" * 60)
print(f"  PASSED: {_pass}  |  FAILED: {_fail}  |  TOTAL: {_pass+_fail}")
print("=" * 60)

if _fail > 0:
    sys.exit(1)
