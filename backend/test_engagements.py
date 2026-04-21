"""Tests for engagements.py + routes_engagements.py."""
import os
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def isolated_db(monkeypatch):
    """
    Each test gets a fresh SQLite file. We import persistence after
    setting the env var so it picks up the temporary path.
    """
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    monkeypatch.setenv("YIELD_DB_PATH", db_path)

    # Force reimport of persistence and engagements to bind to the new DB
    import importlib
    import persistence, engagements
    importlib.reload(persistence)
    importlib.reload(engagements)
    persistence.init_db()
    engagements.init_engagements_table()
    yield engagements
    # Cleanup
    for name in os.listdir(tmpdir):
        os.remove(os.path.join(tmpdir, name))
    os.rmdir(tmpdir)


@pytest.fixture
def client(isolated_db):
    """FastAPI app with just the engagements router and isolated DB.
    Uses editor role so CRUD operations are permitted."""
    import importlib, routes_engagements
    importlib.reload(routes_engagements)
    app = FastAPI()
    app.include_router(routes_engagements.router)
    from conftest import AuthedTestClient
    return AuthedTestClient(app, role="editor")


# ─── Module-level functions ──────────────────────────────────────────────

def test_default_engagement_is_seeded(isolated_db):
    default = isolated_db.get_engagement()
    assert default.id == "default"
    assert default.currency == "USD"
    assert default.locale == "en-US"


def test_init_is_idempotent(isolated_db):
    isolated_db.init_engagements_table()
    isolated_db.init_engagements_table()
    # default is still the only row
    rows = isolated_db.list_engagements()
    assert len(rows) == 1


def test_create_and_get(isolated_db):
    e = isolated_db.create_engagement(
        id="acme-q2", name="Acme · Q2", currency="INR", locale="en-IN",
    )
    assert e.id == "acme-q2"
    assert e.currency == "INR"
    got = isolated_db.get_engagement("acme-q2")
    assert got.name == "Acme · Q2"


def test_create_rejects_duplicate_id(isolated_db):
    isolated_db.create_engagement(id="x", name="X")
    with pytest.raises(ValueError):
        isolated_db.create_engagement(id="x", name="X2")


def test_create_rejects_unsupported_currency(isolated_db):
    with pytest.raises(Exception):  # UnsupportedCurrency subclasses ValueError
        isolated_db.create_engagement(id="y", name="Y", currency="XYZ")


def test_create_rejects_bad_ids(isolated_db):
    for bad in ("", "  ", "has spaces", "slash/in/it", "quote'here"):
        with pytest.raises(ValueError):
            isolated_db.create_engagement(id=bad, name="oops")


def test_update_preserves_unchanged_fields(isolated_db):
    isolated_db.create_engagement(id="u1", name="Original", currency="USD")
    updated = isolated_db.update_engagement("u1", currency="EUR")
    assert updated.name == "Original"
    assert updated.currency == "EUR"


def test_update_rejects_unknown_id(isolated_db):
    with pytest.raises(ValueError):
        isolated_db.update_engagement("does-not-exist", name="Oops")


def test_get_unknown_falls_back_to_default(isolated_db):
    """Routes use get_engagement in read-only contexts and must not raise."""
    e = isolated_db.get_engagement("does-not-exist")
    assert e.id == "default"


def test_delete_returns_true_on_success(isolated_db):
    isolated_db.create_engagement(id="ephemeral", name="E")
    assert isolated_db.delete_engagement("ephemeral") is True
    # Re-deleting returns False
    assert isolated_db.delete_engagement("ephemeral") is False


def test_cannot_delete_default(isolated_db):
    assert isolated_db.delete_engagement("default") is False
    # Default still exists
    assert isolated_db.get_engagement("default").id == "default"


# ─── HTTP routes ─────────────────────────────────────────────────────────

def test_list_returns_default_engagement_and_catalog(client):
    r = client.get("/api/engagements")
    assert r.status_code == 200
    body = r.json()
    assert body["default_id"] == "default"
    assert "USD" in body["supported_currencies"]
    assert "INR" in body["supported_currencies"]
    ids = [e["id"] for e in body["engagements"]]
    assert "default" in ids


def test_create_via_api(client):
    r = client.post("/api/engagements", json={
        "id": "acme-q2", "name": "Acme · Q2", "currency": "INR", "locale": "en-IN",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == "acme-q2"
    assert body["currency"] == "INR"


def test_create_duplicate_returns_409(client):
    client.post("/api/engagements", json={"id": "dup", "name": "A"})
    r = client.post("/api/engagements", json={"id": "dup", "name": "B"})
    assert r.status_code == 409


def test_create_bad_currency_returns_422(client):
    r = client.post("/api/engagements", json={
        "id": "badcur", "name": "X", "currency": "XYZ",
    })
    assert r.status_code == 422


def test_patch_updates_currency(client):
    client.post("/api/engagements", json={"id": "p1", "name": "P1", "currency": "USD"})
    r = client.patch("/api/engagements/p1", json={"currency": "EUR"})
    assert r.status_code == 200
    assert r.json()["currency"] == "EUR"


def test_patch_unknown_returns_404(client):
    r = client.patch("/api/engagements/nope", json={"name": "x"})
    assert r.status_code == 404


def test_get_unknown_via_api_returns_404(client):
    r = client.get("/api/engagements/nope")
    assert r.status_code == 404


def test_delete_default_via_api_returns_400(client):
    r = client.delete("/api/engagements/default")
    assert r.status_code == 400


def test_full_crud_flow(client):
    # Create
    r = client.post("/api/engagements", json={
        "id": "flow-1", "name": "Flow 1", "currency": "GBP",
    })
    assert r.status_code == 201
    # List contains it
    ids = [e["id"] for e in client.get("/api/engagements").json()["engagements"]]
    assert "flow-1" in ids
    # Update
    r = client.patch("/api/engagements/flow-1", json={"name": "Flow One"})
    assert r.json()["name"] == "Flow One"
    # Delete
    r = client.delete("/api/engagements/flow-1")
    assert r.status_code == 204
    # List no longer contains it
    ids = [e["id"] for e in client.get("/api/engagements").json()["engagements"]]
    assert "flow-1" not in ids
