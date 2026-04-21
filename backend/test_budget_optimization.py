"""Tests for routes_budget_optimization."""
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from routes_budget_optimization import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def populated_state():
    """Realistic optimizer output matching the HTML reference's numbers."""
    return {
        "optimization": {
            "summary": {
                "total_budget": 685_000_000,
                "current_revenue": 2_480_000_000,
                "current_roi": 3.62,
                "optimized_roi": 4.42,
                "revenue_uplift": 241_000_000,
                "uplift_pct": 22.1,
                "current_cac": 582,
                "optimized_cac": 509,
                "payback_months": 1.8,
            },
            "channels": [
                {"channel": "Search",   "current_spend": 246_000_000, "optimized_spend": 301_000_000,
                 "marginal_roi": 3.6, "confidence": 92,
                 "credible_interval_80": [162_000_000, 234_000_000]},
                {"channel": "Meta Ads", "current_spend": 182_000_000, "optimized_spend": 164_000_000,
                 "marginal_roi": 0.2, "confidence": 81},
                {"channel": "LinkedIn", "current_spend": 96_000_000,  "optimized_spend": 116_000_000,
                 "marginal_roi": 3.2, "confidence": 88},
                {"channel": "Display",  "current_spend": 68_000_000,  "optimized_spend": 34_000_000,
                 "marginal_roi": 0.62, "confidence": 94},
                {"channel": "YouTube",  "current_spend": 55_000_000,  "optimized_spend": 62_000_000,
                 "marginal_roi": 2.1, "confidence": 85},
                {"channel": "Others",   "current_spend": 38_000_000,  "optimized_spend": 8_000_000,
                 "marginal_roi": 0.3, "confidence": 75},
            ],
        },
    }


# ─── Cold start ──────────────────────────────────────────────────────────

def test_cold_start_returns_renderable(client):
    with patch("routes_budget_optimization._read_state", return_value={}):
        r = client.get("/api/budget-optimization")
    assert r.status_code == 200
    body = r.json()
    assert body["has_optimization"] is False
    assert {"hero", "allocation", "moves", "impact", "atlas"} <= set(body)


# ─── Populated ──────────────────────────────────────────────────────────

def test_allocation_sides_align(client, populated_state):
    with patch("routes_budget_optimization._read_state", return_value=populated_state):
        body = client.get("/api/budget-optimization").json()
    alloc = body["allocation"]
    assert len(alloc["current"]) == 6
    assert len(alloc["recommended"]) == 6
    # Channel order matches between sides
    c_names = [s["channel"] for s in alloc["current"]]
    r_names = [s["channel"] for s in alloc["recommended"]]
    assert c_names == r_names


def test_allocation_percentages_sum_to_100(client, populated_state):
    with patch("routes_budget_optimization._read_state", return_value=populated_state):
        body = client.get("/api/budget-optimization").json()
    for side in ("current", "recommended"):
        total = sum(s["percentage"] for s in body["allocation"][side])
        assert 99.5 <= total <= 100.5, f"{side} pct sum = {total}"


def test_moves_limited_to_four(client, populated_state):
    with patch("routes_budget_optimization._read_state", return_value=populated_state):
        body = client.get("/api/budget-optimization").json()
    assert len(body["moves"]) == 4


def test_moves_sorted_by_absolute_spend_delta(client, populated_state):
    with patch("routes_budget_optimization._read_state", return_value=populated_state):
        body = client.get("/api/budget-optimization").json()
    deltas = [abs(m["delta_spend"]) for m in body["moves"]]
    assert deltas == sorted(deltas, reverse=True)


def test_moves_have_direction_and_reasoning(client, populated_state):
    with patch("routes_budget_optimization._read_state", return_value=populated_state):
        body = client.get("/api/budget-optimization").json()
    for m in body["moves"]:
        assert m["direction"] in ("up", "down")
        assert m["why"]["text"]
        assert len(m["why"]["text"]) > 20  # actual reasoning, not placeholder
        assert 0 <= m["confidence"] <= 100


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
    # Same budget phrase in the italic grey span
    assert "68.5 Cr" in hero["headline"]["same"]
    # Gain phrase in the mint italic span
    assert "more" in hero["headline"]["gain"].lower()


# ─── Override scoring ───────────────────────────────────────────────────

def test_override_with_no_changes_is_neutral(client, populated_state):
    """Submitting the Atlas plan exactly should produce ~zero delta."""
    atlas_alloc = {
        "Search": 30.1, "Meta Ads": 16.4, "LinkedIn": 11.6,
        "Display": 3.4, "YouTube": 6.2, "Others": 0.8,
    }
    with patch("routes_budget_optimization._read_state", return_value=populated_state):
        r = client.post("/api/budget-optimization/override", json={"allocation": atlas_alloc})
    assert r.status_code == 200
    body = r.json()
    # Tiny drift only from rounding
    assert abs(body["delta_vs_atlas_cr"]) < 1.5
    assert body["pushback"] is None


def test_override_bad_shift_triggers_pushback(client, populated_state):
    """Moving Cr off high-marginal Search into Display should hurt."""
    bad_alloc = {
        "Search": 15.0,   # down 15 from Atlas's 30.1
        "Meta Ads": 16.4,
        "LinkedIn": 11.6,
        "Display": 18.4,   # up 15 from Atlas's 3.4
        "YouTube": 6.2,
        "Others": 0.8,
    }
    with patch("routes_budget_optimization._read_state", return_value=populated_state):
        r = client.post("/api/budget-optimization/override", json={"allocation": bad_alloc})
    body = r.json()
    assert body["delta_vs_atlas_cr"] < -1
    assert body["pushback"] is not None
    assert "Search" in body["pushback"]["detail"] or "Display" in body["pushback"]["detail"]


def test_override_requires_allocation(client):
    r = client.post("/api/budget-optimization/override", json={})
    assert r.status_code == 400


def test_override_without_optimization_run_returns_409(client):
    with patch("routes_budget_optimization._read_state", return_value={}):
        r = client.post("/api/budget-optimization/override",
                        json={"allocation": {"Search": 30}})
    assert r.status_code == 409
