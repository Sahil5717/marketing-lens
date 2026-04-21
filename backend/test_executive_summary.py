"""
Tests for routes_executive_summary.

Covers:
  - cold start: no data uploaded, endpoint returns renderable empty state
  - populated: all engine outputs present, endpoint returns the right shape
  - currency: USD default vs INR engagement vs EUR engagement all format
    money correctly
  - smart_recs priority over optimizer fallback
"""
import os
import tempfile
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from conftest import AuthedTestClient


@pytest.fixture
def isolated_db(monkeypatch):
    """
    Each test gets a fresh SQLite DB with the engagements table seeded.
    This is needed because the new route reads engagement config.
    """
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    monkeypatch.setenv("YIELD_DB_PATH", db_path)

    import importlib
    import persistence, engagements, routes_executive_summary
    importlib.reload(persistence)
    importlib.reload(engagements)
    importlib.reload(routes_executive_summary)
    persistence.init_db()
    engagements.init_engagements_table()
    yield engagements
    for name in os.listdir(tmpdir):
        os.remove(os.path.join(tmpdir, name))
    os.rmdir(tmpdir)


@pytest.fixture
def client(isolated_db):
    """Fresh app with just the executive-summary router."""
    import importlib, routes_executive_summary
    importlib.reload(routes_executive_summary)
    app = FastAPI()
    app.include_router(routes_executive_summary.router)
    return AuthedTestClient(app)


# ─── Cold start ──────────────────────────────────────────────────────────

def test_cold_start_returns_200_with_empty_state(client):
    """With no state at all, endpoint must still return a renderable payload."""
    with patch("routes_executive_summary._read_state", return_value={}):
        r = client.get("/api/executive-summary")
    assert r.status_code == 200
    body = r.json()
    assert body["has_data"] is False
    assert {"engagement", "hero", "kpis", "pillars", "opportunities",
            "top_actions", "atlas"} <= set(body)


def test_cold_start_includes_engagement_metadata(client):
    with patch("routes_executive_summary._read_state", return_value={}):
        body = client.get("/api/executive-summary").json()
    assert body["engagement"]["id"] == "default"
    assert body["engagement"]["currency"] == "USD"


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
    for p in body["pillars"]["pillars"]:
        assert p["amount"] == 0


def test_cold_start_atlas_explains_absence(client):
    with patch("routes_executive_summary._read_state", return_value={}):
        body = client.get("/api/executive-summary").json()
    assert len(body["atlas"]["paragraphs"]) >= 1
    text = " ".join(p["text"] for p in body["atlas"]["paragraphs"])
    assert "data" in text.lower() or "load" in text.lower()


# ─── Populated state ─────────────────────────────────────────────────────

@pytest.fixture
def populated_state():
    return {
        "campaign_data": "stub",
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
    # Default engagement is USD — so loss/gain should use $
    assert hero["headline"]["loss"].startswith("$")
    assert "recoverable" in hero["headline"]["gain"].lower()


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
    assert {"Reallocate spend", "Cut waste", "Fix conversion"} == set(names)


def test_populated_state_top_actions_from_optimizer_fallback(client, populated_state):
    with patch("routes_executive_summary._read_state", return_value=populated_state):
        body = client.get("/api/executive-summary").json()
    actions = body["top_actions"]
    assert len(actions) >= 1
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


def test_smart_recs_takes_priority_over_optimizer_fallback(client, populated_state):
    populated_state["smart_recs"] = [
        {
            "title": "Shift 15% budget to Search",
            "impact_display": "+$5.2M",
            "reasoning": "Search is your highest marginal-ROI channel.",
        },
    ]
    with patch("routes_executive_summary._read_state", return_value=populated_state):
        body = client.get("/api/executive-summary").json()
    actions = body["top_actions"]
    assert actions[0]["text"] == "Shift 15% budget to Search"
    assert actions[0]["impact"] == "+$5.2M"


# ─── Currency parameterisation (new in v26) ──────────────────────────────

def test_default_engagement_formats_as_usd(client, populated_state):
    """Default engagement is USD, so money strings should use $ and M/K/Cr-free."""
    with patch("routes_executive_summary._read_state", return_value=populated_state):
        body = client.get("/api/executive-summary").json()
    total_display = body["pillars"]["total_cost"]["display"]
    assert total_display.startswith("$")
    # Shouldn't contain the Indian scale words
    assert " Cr" not in total_display
    assert " L" not in total_display


def test_inr_engagement_formats_as_crore(client, populated_state, isolated_db):
    """An INR-configured engagement formats money as ₹XX Cr / ₹XX L."""
    isolated_db.create_engagement(
        id="acme-inr", name="Acme India", currency="INR", locale="en-IN",
    )
    with patch("routes_executive_summary._read_state", return_value=populated_state):
        r = client.get("/api/executive-summary?engagement_id=acme-inr")
    body = r.json()
    assert body["engagement"]["currency"] == "INR"
    total_display = body["pillars"]["total_cost"]["display"]
    assert total_display.startswith("₹")
    assert "Cr" in total_display or "L" in total_display


def test_eur_engagement_formats_with_euro_symbol(client, populated_state, isolated_db):
    isolated_db.create_engagement(
        id="eu-co", name="EU Co", currency="EUR", locale="en-GB",
    )
    with patch("routes_executive_summary._read_state", return_value=populated_state):
        body = client.get("/api/executive-summary?engagement_id=eu-co").json()
    assert body["engagement"]["currency"] == "EUR"
    assert body["pillars"]["total_cost"]["display"].startswith("€")


def test_unknown_engagement_id_falls_back_to_default(client, populated_state):
    """Per engagements.get_engagement contract — unknown id gives default."""
    with patch("routes_executive_summary._read_state", return_value=populated_state):
        body = client.get("/api/executive-summary?engagement_id=does-not-exist").json()
    assert body["engagement"]["id"] == "default"
    assert body["engagement"]["currency"] == "USD"


def test_opportunity_amounts_are_currency_formatted(client, populated_state, isolated_db):
    isolated_db.create_engagement(id="acme-inr2", name="A", currency="INR")
    with patch("routes_executive_summary._read_state", return_value=populated_state):
        body_inr = client.get("/api/executive-summary?engagement_id=acme-inr2").json()
    with patch("routes_executive_summary._read_state", return_value=populated_state):
        body_usd = client.get("/api/executive-summary").json()  # default USD
    # Same raw amount, different display format
    inr_realloc = body_inr["opportunities"][0]["display"]
    usd_realloc = body_usd["opportunities"][0]["display"]
    assert inr_realloc != usd_realloc
    assert "₹" in inr_realloc
    assert "$" in usd_realloc
    # Both signed as positive
    assert inr_realloc.startswith("+")
    assert usd_realloc.startswith("+")


def test_atlas_narration_uses_engagement_currency(client, populated_state, isolated_db):
    """Atlas's narrated numbers should respect the engagement's currency."""
    isolated_db.create_engagement(id="acme-inr3", name="A", currency="INR")
    with patch("routes_executive_summary._read_state", return_value=populated_state):
        body = client.get("/api/executive-summary?engagement_id=acme-inr3").json()
    narration = " ".join(p["text"] for p in body["atlas"]["paragraphs"])
    assert "₹" in narration
    assert "$" not in narration
