"""
Tests for routes_executive_summary.

Focuses on the two cases that matter for a walkthrough demo:
  - cold start: no data uploaded yet, endpoint returns renderable empty state
  - populated: all engine outputs present, endpoint returns the right shape
"""
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Fresh app with just the executive-summary router — no api.py."""
    from routes_executive_summary import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ─── Cold start ──────────────────────────────────────────────────────────

def test_cold_start_returns_200_with_empty_state(client):
    """With no state at all, endpoint must still return a renderable payload."""
    with patch("routes_executive_summary._read_state", return_value={}):
        r = client.get("/api/executive-summary")
    assert r.status_code == 200
    body = r.json()
    assert body["has_data"] is False
    # Structural keys must always be present
    assert {"hero", "kpis", "pillars", "opportunities", "top_actions", "atlas"} <= set(body)


def test_cold_start_kpis_have_5_cells(client):
    with patch("routes_executive_summary._read_state", return_value={}):
        body = client.get("/api/executive-summary").json()
    assert len(body["kpis"]) == 5
    labels = [k["label"] for k in body["kpis"]]
    assert labels == ["Total Revenue", "ROI", "Marketing Spend", "CAC", "Pipeline Influence"]


def test_cold_start_pillars_have_3_items(client):
    with patch("routes_executive_summary._read_state", return_value={}):
        body = client.get("/api/executive-summary").json()
    assert len(body["pillars"]["pillars"]) == 3
    ids = [p["id"] for p in body["pillars"]["pillars"]]
    assert ids == ["leak", "drop", "avoid"]
    # All zero in cold start
    for p in body["pillars"]["pillars"]:
        assert p["amount"] == 0


def test_cold_start_atlas_explains_absence(client):
    with patch("routes_executive_summary._read_state", return_value={}):
        body = client.get("/api/executive-summary").json()
    assert len(body["atlas"]["paragraphs"]) >= 1
    # Should mention no data being loaded
    text = " ".join(p["text"] for p in body["atlas"]["paragraphs"])
    assert "data" in text.lower() or "load" in text.lower()


# ─── Populated state ─────────────────────────────────────────────────────

@pytest.fixture
def populated_state():
    """A realistic state dict as it would look after all engines have run."""
    return {
        "campaign_data": "stub",  # truthy — signals data loaded
        "pillars": {
            "revenue_leakage": {"total_leakage": 24_300_000},
            "experience_suppression": {"total_suppression": 8_300_000},
            "avoidable_cost": {"total_avoidable_cost": 3_200_000},
            "correction_potential": {
                "reallocation_uplift": 14_580_000,
                "cx_fix_recovery": 3_320_000,
                "cost_savings": 2_240_000,
                "total_recoverable": 20_140_000,
            },
        },
        "optimization": {
            "summary": {
                "current_revenue": 2_480_000_000,
                "total_budget": 685_000_000,
            },
            "channels": [
                {"channel": "Search", "current_spend": 20_000_000, "optimized_spend": 30_000_000},
                {"channel": "Display", "current_spend": 10_000_000, "optimized_spend": 4_000_000},
            ],
        },
        "mmm_result": {"r_squared": 0.87},
    }


def test_populated_state_hero_headline_mentions_loss_and_recovery(client, populated_state):
    with patch("routes_executive_summary._read_state", return_value=populated_state):
        body = client.get("/api/executive-summary").json()
    hero = body["hero"]
    assert "Cr" in hero["headline"]["loss"]
    assert "Cr" in hero["headline"]["gain"]
    assert "recoverable" in hero["headline"]["gain"].lower()


def test_populated_state_kpi_revenue_formatted_as_crore(client, populated_state):
    with patch("routes_executive_summary._read_state", return_value=populated_state):
        body = client.get("/api/executive-summary").json()
    revenue_kpi = body["kpis"][0]
    assert "Cr" in revenue_kpi["value"]


def test_populated_state_pillars_match_engine_output(client, populated_state):
    with patch("routes_executive_summary._read_state", return_value=populated_state):
        body = client.get("/api/executive-summary").json()
    pillars = {p["id"]: p for p in body["pillars"]["pillars"]}
    assert pillars["leak"]["amount"] == 24_300_000
    assert pillars["drop"]["amount"] == 8_300_000
    assert pillars["avoid"]["amount"] == 3_200_000
    assert body["pillars"]["total_cost"]["amount"] == 24_300_000 + 8_300_000 + 3_200_000


def test_populated_state_opportunities_have_3_levers(client, populated_state):
    with patch("routes_executive_summary._read_state", return_value=populated_state):
        body = client.get("/api/executive-summary").json()
    opps = body["opportunities"]
    assert len(opps) == 3
    names = [o["name"] for o in opps]
    assert "Reallocate spend" in names
    assert "Cut waste" in names
    assert "Fix conversion" in names


def test_populated_state_top_actions_from_optimizer_fallback(client, populated_state):
    """When smart_recs is absent, actions derive from optimizer deltas."""
    with patch("routes_executive_summary._read_state", return_value=populated_state):
        body = client.get("/api/executive-summary").json()
    actions = body["top_actions"]
    assert len(actions) >= 1
    # Lead action is Search (largest positive delta)
    assert "Search" in actions[0]["text"]


def test_populated_state_atlas_has_suggested_questions(client, populated_state):
    with patch("routes_executive_summary._read_state", return_value=populated_state):
        body = client.get("/api/executive-summary").json()
    atlas = body["atlas"]
    assert len(atlas["paragraphs"]) >= 2
    assert len(atlas["suggested_questions"]) >= 3


def test_populated_state_has_data_flag(client, populated_state):
    with patch("routes_executive_summary._read_state", return_value=populated_state):
        body = client.get("/api/executive-summary").json()
    assert body["has_data"] is True


# ─── Formatter helpers ───────────────────────────────────────────────────

def test_fmt_cr_handles_zero_and_negatives():
    from routes_executive_summary import _fmt_cr, _fmt_impact
    assert _fmt_cr(0) == "₹0 Cr"
    assert "Cr" in _fmt_cr(10_000_000)
    # Sub-crore shows lakhs
    assert "L" in _fmt_cr(500_000)
    # Impact formatter signs
    assert _fmt_impact(10_000_000).startswith("+")
    assert _fmt_impact(-10_000_000).startswith("−")


def test_smart_recs_takes_priority_over_optimizer_fallback(client, populated_state):
    populated_state["smart_recs"] = [
        {
            "title": "Shift 15% budget to Search",
            "impact_display": "+₹5.2 Cr",
            "reasoning": "Search is your highest marginal-ROI channel.",
        },
    ]
    with patch("routes_executive_summary._read_state", return_value=populated_state):
        body = client.get("/api/executive-summary").json()
    actions = body["top_actions"]
    assert actions[0]["text"] == "Shift 15% budget to Search"
    assert actions[0]["impact"] == "+₹5.2 Cr"
    assert "Search" in actions[0]["why"]["text"]
