"""Tests for routes_channel_performance."""
import os
import tempfile
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from conftest import AuthedTestClient


@pytest.fixture
def isolated_db(monkeypatch):
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    monkeypatch.setenv("YIELD_DB_PATH", db_path)

    import importlib
    import persistence, engagements, routes_channel_performance
    importlib.reload(persistence)
    importlib.reload(engagements)
    importlib.reload(routes_channel_performance)
    persistence.init_db()
    engagements.init_engagements_table()
    yield engagements
    for name in os.listdir(tmpdir):
        os.remove(os.path.join(tmpdir, name))
    os.rmdir(tmpdir)


@pytest.fixture
def client(isolated_db):
    import importlib, routes_channel_performance
    importlib.reload(routes_channel_performance)
    app = FastAPI()
    app.include_router(routes_channel_performance.router)
    return AuthedTestClient(app)


@pytest.fixture
def populated_state():
    """USD-scale realistic channel performance dataset."""
    return {
        "channel_performance": [
            {"channel": "Search",   "spend": 24_600_000, "revenue": 120_800_000,
             "conversions": 98_300,  "trend_pct": 12.0},
            {"channel": "Meta Ads", "spend": 18_200_000, "revenue": 75_400_000,
             "conversions": 63_100,  "trend_pct": 4.2},
            {"channel": "LinkedIn", "spend": 9_600_000,  "revenue": 22_400_000,
             "conversions": 18_200,  "trend_pct": 18.6},
            {"channel": "Display",  "spend": 6_800_000,  "revenue": 11_000_000,
             "conversions": 16_800,  "trend_pct": -7.3},
            {"channel": "YouTube",  "spend": 5_500_000,  "revenue": 11_200_000,
             "conversions": 9_900,   "trend_pct": 3.1},
            {"channel": "Others",   "spend": 3_800_000,  "revenue": 7_200_000,
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
    assert {"engagement", "kpis", "summary", "contribution", "top_insight",
            "channel_shift", "atlas"} <= set(body)


def test_cold_start_kpis_show_dashes(client):
    with patch("routes_channel_performance._read_state", return_value={}):
        body = client.get("/api/channel-performance").json()
    for kpi in body["kpis"]:
        assert kpi["value"] == "—"


def test_cold_start_uses_default_engagement(client):
    with patch("routes_channel_performance._read_state", return_value={}):
        body = client.get("/api/channel-performance").json()
    assert body["engagement"]["id"] == "default"
    assert body["engagement"]["currency"] == "USD"


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


def test_channel_shift_series_has_all_channels(client, populated_state):
    with patch("routes_channel_performance._read_state", return_value=populated_state):
        body = client.get("/api/channel-performance").json()
    shift = body["channel_shift"]
    assert len(shift["series"]) == 6
    for s in shift["series"]:
        assert len(s["points"]) == shift["lookback_months"]


def test_channel_shift_source_flagged_as_synthetic(client, populated_state):
    with patch("routes_channel_performance._read_state", return_value=populated_state):
        body = client.get("/api/channel-performance").json()
    assert body["channel_shift"]["source"].startswith("synthetic")


def test_channel_shift_uses_real_history_when_present(client, populated_state):
    populated_state["channel_monthly_history"] = [
        {"month": f"2024-{m:02d}", "channel": ch, "spend": spend}
        for m in range(1, 7)
        for ch, spend in [("Search", 2_000_000), ("Meta Ads", 1_500_000), ("Display", 1_000_000)]
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
    state = {
        "optimization": {
            "channels": [
                {"channel": "Search", "current_spend": 24_600_000, "current_roi": 4.9,
                 "current_revenue": 120_000_000},
                {"channel": "Display", "current_spend": 6_800_000, "current_roi": 1.6,
                 "current_revenue": 11_000_000},
            ],
        },
    }
    with patch("routes_channel_performance._read_state", return_value=state):
        body = client.get("/api/channel-performance").json()
    assert body["has_data"] is True


# ─── Currency behaviour ────────────────────────────────────────────────

def test_default_engagement_formats_as_usd(client, populated_state):
    with patch("routes_channel_performance._read_state", return_value=populated_state):
        body = client.get("/api/channel-performance").json()
    # Total spend KPI should use $
    spend_value = body["kpis"][0]["value"]
    assert spend_value.startswith("$")
    # Summary table rows
    for row in body["summary"]:
        assert row["spend_display"].startswith("$")
        assert row["revenue_display"].startswith("$")
    # No rupee symbols anywhere
    payload_str = str(body)
    assert "₹" not in payload_str
    assert " Cr" not in payload_str


def test_inr_engagement_formats_as_crore(client, populated_state, isolated_db):
    isolated_db.create_engagement(id="acme-inr", name="Acme India", currency="INR")
    with patch("routes_channel_performance._read_state", return_value=populated_state):
        body = client.get("/api/channel-performance?engagement_id=acme-inr").json()
    assert body["engagement"]["currency"] == "INR"
    for row in body["summary"]:
        assert row["spend_display"].startswith("₹")
        assert row["revenue_display"].startswith("₹")


def test_eur_engagement_formats_with_euro_symbol(client, populated_state, isolated_db):
    isolated_db.create_engagement(id="eu-co", name="EU Co", currency="EUR")
    with patch("routes_channel_performance._read_state", return_value=populated_state):
        body = client.get("/api/channel-performance?engagement_id=eu-co").json()
    assert body["engagement"]["currency"] == "EUR"
    assert body["kpis"][0]["value"].startswith("€")
    assert body["contribution"]["total_display"].startswith("€")
