"""Tests for routes_channel_performance."""
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from routes_channel_performance import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def populated_state():
    """Realistic channel performance dataset."""
    return {
        "channel_performance": [
            {"channel": "Search",   "spend": 246_000_000, "revenue": 1_208_000_000,
             "conversions": 98_300,  "trend_pct": 12.0},
            {"channel": "Meta Ads", "spend": 182_000_000, "revenue": 754_000_000,
             "conversions": 63_100,  "trend_pct": 4.2},
            {"channel": "LinkedIn", "spend": 96_000_000,  "revenue": 224_000_000,
             "conversions": 18_200,  "trend_pct": 18.6},
            {"channel": "Display",  "spend": 68_000_000,  "revenue": 110_000_000,
             "conversions": 16_800,  "trend_pct": -7.3},
            {"channel": "YouTube",  "spend": 55_000_000,  "revenue": 112_000_000,
             "conversions": 9_900,   "trend_pct": 3.1},
            {"channel": "Others",   "spend": 38_000_000,  "revenue": 72_000_000,
             "conversions": 7_700,   "trend_pct": -2.4},
        ],
    }


# ─── Cold start ──────────────────────────────────────────────────────────

def test_cold_start_returns_renderable(client):
    with patch("routes_channel_performance._read_state", return_value={}):
        r = client.get("/api/channel-performance")
    assert r.status_code == 200
    body = r.json()
    assert body["has_data"] is False
    assert {"kpis", "summary", "contribution", "top_insight",
            "channel_shift", "atlas"} <= set(body)


def test_cold_start_kpis_show_dashes(client):
    with patch("routes_channel_performance._read_state", return_value={}):
        body = client.get("/api/channel-performance").json()
    for kpi in body["kpis"]:
        assert kpi["value"] == "—"


# ─── Populated ──────────────────────────────────────────────────────────

def test_populated_kpis_have_5_cells(client, populated_state):
    with patch("routes_channel_performance._read_state", return_value=populated_state):
        body = client.get("/api/channel-performance").json()
    labels = [k["label"] for k in body["kpis"]]
    assert labels == ["Total Spend", "Revenue", "ROI", "Conversions", "CAC"]


def test_summary_sorted_by_revenue_desc(client, populated_state):
    with patch("routes_channel_performance._read_state", return_value=populated_state):
        body = client.get("/api/channel-performance").json()
    revenues = [row["revenue"] for row in body["summary"]]
    assert revenues == sorted(revenues, reverse=True)


def test_summary_has_trend_direction(client, populated_state):
    with patch("routes_channel_performance._read_state", return_value=populated_state):
        body = client.get("/api/channel-performance").json()
    directions = {row["trend_direction"] for row in body["summary"]}
    assert "up" in directions
    assert "down" in directions


def test_contribution_percentages_sum_100(client, populated_state):
    with patch("routes_channel_performance._read_state", return_value=populated_state):
        body = client.get("/api/channel-performance").json()
    total = sum(s["percentage"] for s in body["contribution"]["slices"])
    assert 99.5 <= total <= 100.5


def test_top_insight_names_top_two_channels(client, populated_state):
    with patch("routes_channel_performance._read_state", return_value=populated_state):
        body = client.get("/api/channel-performance").json()
    headline = body["top_insight"]["headline"]
    assert "Search" in headline
    assert "Meta Ads" in headline
    assert "%" in headline


def test_channel_shift_series_has_all_channels(client, populated_state):
    with patch("routes_channel_performance._read_state", return_value=populated_state):
        body = client.get("/api/channel-performance").json()
    shift = body["channel_shift"]
    assert len(shift["series"]) == 6
    # Each series has the right number of points
    for s in shift["series"]:
        assert len(s["points"]) == shift["lookback_months"]


def test_channel_shift_monthly_columns_sum_100(client, populated_state):
    """In synthetic mode each month's slices should sum to ~100%."""
    with patch("routes_channel_performance._read_state", return_value=populated_state):
        body = client.get("/api/channel-performance").json()
    shift = body["channel_shift"]
    n_months = shift["lookback_months"]
    for idx in range(n_months):
        col_sum = sum(s["points"][idx]["percentage"] for s in shift["series"])
        assert 99.0 <= col_sum <= 101.0, f"month {idx} sums to {col_sum}"


def test_channel_shift_source_flagged_as_synthetic(client, populated_state):
    """Without monthly_history, the shift must honestly flag itself as synthetic."""
    with patch("routes_channel_performance._read_state", return_value=populated_state):
        body = client.get("/api/channel-performance").json()
    assert body["channel_shift"]["source"].startswith("synthetic")


def test_channel_shift_uses_real_history_when_present(client, populated_state):
    # 3 channels × 6 months history
    populated_state["channel_monthly_history"] = [
        {"month": f"2024-{m:02d}", "channel": ch, "spend": spend}
        for m in range(1, 7)
        for ch, spend in [("Search", 20_000_000), ("Meta Ads", 15_000_000), ("Display", 10_000_000)]
    ]
    with patch("routes_channel_performance._read_state", return_value=populated_state):
        body = client.get("/api/channel-performance").json()
    shift = body["channel_shift"]
    assert shift["source"] == "historical"
    assert shift["lookback_months"] == 6


def test_atlas_narration_mentions_top_channel(client, populated_state):
    with patch("routes_channel_performance._read_state", return_value=populated_state):
        body = client.get("/api/channel-performance").json()
    text = " ".join(p["text"] for p in body["atlas"]["paragraphs"])
    assert "Search" in text


def test_lookback_query_param_respected(client, populated_state):
    with patch("routes_channel_performance._read_state", return_value=populated_state):
        body = client.get("/api/channel-performance?lookback_months=12").json()
    assert body["channel_shift"]["lookback_months"] == 12


def test_falls_back_to_optimization_channels(client):
    """When channel_performance is absent, derive from optimization.channels."""
    state = {
        "optimization": {
            "channels": [
                {"channel": "Search", "current_spend": 246_000_000, "current_roi": 4.9,
                 "current_revenue": 1_200_000_000},
                {"channel": "Display", "current_spend": 68_000_000, "current_roi": 1.6,
                 "current_revenue": 110_000_000},
            ],
        },
    }
    with patch("routes_channel_performance._read_state", return_value=state):
        body = client.get("/api/channel-performance").json()
    assert body["has_data"] is True
    channels = [row["channel"] for row in body["summary"]]
    assert "Search" in channels and "Display" in channels
