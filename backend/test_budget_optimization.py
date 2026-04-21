"""Tests for routes_budget_optimization."""
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
    import persistence, engagements, routes_budget_optimization
    importlib.reload(persistence)
    importlib.reload(engagements)
    importlib.reload(routes_budget_optimization)
    persistence.init_db()
    engagements.init_engagements_table()
    yield engagements
    for name in os.listdir(tmpdir):
        os.remove(os.path.join(tmpdir, name))
    os.rmdir(tmpdir)


@pytest.fixture
def client(isolated_db):
    import importlib, routes_budget_optimization
    importlib.reload(routes_budget_optimization)
    app = FastAPI()
    app.include_router(routes_budget_optimization.router)
    return AuthedTestClient(app)


@pytest.fixture
def populated_state():
    """Realistic optimizer output with USD-scale numbers (millions, not crores)."""
    return {
        "optimization": {
            "summary": {
                "total_budget": 68_500_000,
                "current_revenue": 248_000_000,
                "current_roi": 3.62,
                "optimized_roi": 4.42,
                "revenue_uplift": 24_100_000,
                "uplift_pct": 22.1,
                "current_cac": 582,
                "optimized_cac": 509,
                "payback_months": 1.8,
            },
            "channels": [
                {"channel": "Search",   "current_spend": 24_600_000, "optimized_spend": 30_100_000,
                 "marginal_roi": 3.6, "confidence": 92,
                 "credible_interval_80": [16_200_000, 23_400_000]},
                {"channel": "Meta Ads", "current_spend": 18_200_000, "optimized_spend": 16_400_000,
                 "marginal_roi": 0.2, "confidence": 81},
                {"channel": "LinkedIn", "current_spend": 9_600_000,  "optimized_spend": 11_600_000,
                 "marginal_roi": 3.2, "confidence": 88},
                {"channel": "Display",  "current_spend": 6_800_000,  "optimized_spend": 3_400_000,
                 "marginal_roi": 0.62, "confidence": 94},
                {"channel": "YouTube",  "current_spend": 5_500_000,  "optimized_spend": 6_200_000,
                 "marginal_roi": 2.1, "confidence": 85},
                {"channel": "Others",   "current_spend": 3_800_000,  "optimized_spend": 800_000,
                 "marginal_roi": 0.3, "confidence": 75},
            ],
        },
    }


# ─── Cold start ─────────────────────────────────────────────────────────

def test_cold_start_returns_renderable(client):
    with patch("routes_budget_optimization._read_state", return_value={}):
        r = client.get("/api/budget-optimization")
    assert r.status_code == 200
    body = r.json()
    assert body["has_optimization"] is False
    assert {"engagement", "hero", "allocation", "moves", "impact", "atlas"} <= set(body)


def test_cold_start_returns_default_engagement(client):
    with patch("routes_budget_optimization._read_state", return_value={}):
        body = client.get("/api/budget-optimization").json()
    assert body["engagement"]["id"] == "default"
    assert body["engagement"]["currency"] == "USD"


# ─── Populated ──────────────────────────────────────────────────────────

def test_allocation_sides_align(client, populated_state):
    with patch("routes_budget_optimization._read_state", return_value=populated_state):
        body = client.get("/api/budget-optimization").json()
    alloc = body["allocation"]
    assert len(alloc["current"]) == 6
    assert len(alloc["recommended"]) == 6


def test_allocation_percentages_sum_to_100(client, populated_state):
    with patch("routes_budget_optimization._read_state", return_value=populated_state):
        body = client.get("/api/budget-optimization").json()
    for side in ("current", "recommended"):
        total = sum(s["percentage"] for s in body["allocation"][side])
        assert 99.5 <= total <= 100.5


def test_moves_limited_to_four(client, populated_state):
    with patch("routes_budget_optimization._read_state", return_value=populated_state):
        body = client.get("/api/budget-optimization").json()
    assert len(body["moves"]) == 4


def test_moves_sorted_by_absolute_spend_delta(client, populated_state):
    with patch("routes_budget_optimization._read_state", return_value=populated_state):
        body = client.get("/api/budget-optimization").json()
    deltas = [abs(m["delta_spend"]) for m in body["moves"]]
    assert deltas == sorted(deltas, reverse=True)


def test_impact_strip_has_4_metrics(client, populated_state):
    with patch("routes_budget_optimization._read_state", return_value=populated_state):
        body = client.get("/api/budget-optimization").json()
    impact = body["impact"]
    assert {"projected_roi", "incremental_revenue", "cac_improvement", "payback_period"} == set(impact)
    assert "4.42x" == impact["projected_roi"]["value"]


def test_hero_headline_mentions_same_budget_and_gain(client, populated_state):
    with patch("routes_budget_optimization._read_state", return_value=populated_state):
        body = client.get("/api/budget-optimization").json()
    hero = body["hero"]
    assert "$68.5M" in hero["headline"]["same"]
    assert "more" in hero["headline"]["gain"].lower()


# ─── Currency behaviour ────────────────────────────────────────────────

def test_default_engagement_formats_as_usd(client, populated_state):
    with patch("routes_budget_optimization._read_state", return_value=populated_state):
        body = client.get("/api/budget-optimization").json()
    total_display = body["allocation"]["total_budget_display"]
    assert total_display.startswith("$")
    payload_str = str(body)
    assert "₹" not in payload_str
    assert " Cr" not in payload_str


def test_inr_engagement_formats_as_crore(client, populated_state, isolated_db):
    isolated_db.create_engagement(id="acme-inr", name="Acme India", currency="INR")
    with patch("routes_budget_optimization._read_state", return_value=populated_state):
        body = client.get("/api/budget-optimization?engagement_id=acme-inr").json()
    assert body["engagement"]["currency"] == "INR"
    total_display = body["allocation"]["total_budget_display"]
    assert total_display.startswith("₹")


def test_atlas_narration_uses_engagement_currency(client, populated_state, isolated_db):
    isolated_db.create_engagement(id="eu-co", name="EU Co", currency="EUR")
    with patch("routes_budget_optimization._read_state", return_value=populated_state):
        body = client.get("/api/budget-optimization?engagement_id=eu-co").json()
    narration = " ".join(p["text"] for p in body["atlas"]["paragraphs"])
    # The atlas narration references the action text which contains currency,
    # plus the uplift value. Check none of the wrong symbols leaked in.
    assert "₹" not in narration
    assert "$" not in narration


# ─── Override scoring ───────────────────────────────────────────────────

def test_override_with_no_changes_is_neutral(client, populated_state):
    atlas_alloc = {
        "Search": 30_100_000, "Meta Ads": 16_400_000, "LinkedIn": 11_600_000,
        "Display": 3_400_000, "YouTube": 6_200_000, "Others": 800_000,
    }
    with patch("routes_budget_optimization._read_state", return_value=populated_state):
        r = client.post("/api/budget-optimization/override", json={"allocation": atlas_alloc})
    assert r.status_code == 200
    body = r.json()
    assert abs(body["delta_vs_atlas"]) < 10_000  # rounding drift only
    assert body["pushback"] is None


def test_override_bad_shift_triggers_pushback(client, populated_state):
    bad_alloc = {
        "Search":   15_000_000, "Meta Ads": 16_400_000, "LinkedIn": 11_600_000,
        "Display":  18_400_000, "YouTube":  6_200_000, "Others":   800_000,
    }
    with patch("routes_budget_optimization._read_state", return_value=populated_state):
        r = client.post("/api/budget-optimization/override", json={"allocation": bad_alloc})
    body = r.json()
    assert body["delta_vs_atlas"] < -100_000
    assert body["pushback"] is not None


def test_override_pushback_uses_engagement_currency(client, populated_state, isolated_db):
    isolated_db.create_engagement(id="eu-push", name="EU Co", currency="EUR")
    bad_alloc = {
        "Search": 15_000_000, "Meta Ads": 16_400_000, "LinkedIn": 11_600_000,
        "Display": 18_400_000, "YouTube": 6_200_000, "Others": 800_000,
    }
    with patch("routes_budget_optimization._read_state", return_value=populated_state):
        body = client.post(
            "/api/budget-optimization/override?engagement_id=eu-push",
            json={"allocation": bad_alloc},
        ).json()
    assert body["pushback"] is not None
    assert "€" in body["pushback"]["headline"]


def test_override_requires_allocation(client):
    r = client.post("/api/budget-optimization/override", json={})
    assert r.status_code == 400


def test_override_without_optimization_run_returns_409(client):
    with patch("routes_budget_optimization._read_state", return_value={}):
        r = client.post("/api/budget-optimization/override",
                        json={"allocation": {"Search": 30_000_000}})
    assert r.status_code == 409
