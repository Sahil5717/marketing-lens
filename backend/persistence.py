"""
Persistent State Manager — SQLite Backend
==========================================
Replaces in-memory _state dict with SQLite-backed storage.
Supports per-user sessions, server restart survival, and scenario management.
"""
import sqlite3
import json
import os
import time
import numpy as np
import pandas as pd
from typing import Dict, Optional, Any
from pathlib import Path
import logging
logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("YIELD_DB_PATH", "yield_intelligence.db")


class NumpyEncoder(json.JSONEncoder):
    """Handle numpy types in JSON serialization."""
    def default(self, obj):
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, (np.bool_,)): return bool(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        if isinstance(obj, pd.Timestamp): return str(obj)
        return super().default(obj)


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'analyst',
            created_at REAL DEFAULT (strftime('%s','now'))
        );
        
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            state_json TEXT,
            updated_at REAL DEFAULT (strftime('%s','now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        
        CREATE TABLE IF NOT EXISTS scenarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_id TEXT,
            name TEXT NOT NULL,
            description TEXT,
            parameters TEXT,
            results TEXT,
            created_at REAL DEFAULT (strftime('%s','now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        
        CREATE TABLE IF NOT EXISTS external_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            data_type TEXT NOT NULL,
            filename TEXT,
            data_json TEXT,
            uploaded_at REAL DEFAULT (strftime('%s','now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        -- ═══ EY EDITOR OVERLAY TABLES (v18a) ═══
        --
        -- Four override capabilities are designed at the schema level even
        -- though only two (commentary, suppression) are wired to the frontend
        -- in v18a. The other two (headline/narrative rewrite, prescribed
        -- action rewrite) land in v18b as pure UI work on this same schema.
        --
        -- Keying: all overrides key by (engagement_id, finding_key). The
        -- finding_key is a stable identifier derived from the finding's
        -- semantic content (channel + type + metric), NOT its array index
        -- in the diagnosis payload. This way, when the backend re-runs
        -- analysis on fresh data, existing overrides stay pinned to the
        -- right finding even if findings reorder.
        --
        -- engagement_id is currently always "default" (single-tenant pitch
        -- tool). When multi-tenancy comes, this becomes the real FK.

        -- Commentary: EY adds a note alongside a finding. The note shows up
        -- as a separate "EY's Take" panel in the client view.
        CREATE TABLE IF NOT EXISTS editor_commentary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engagement_id TEXT NOT NULL DEFAULT 'default',
            finding_key TEXT NOT NULL,
            commentary_text TEXT NOT NULL,
            author TEXT,
            updated_at REAL DEFAULT (strftime('%s','now')),
            UNIQUE(engagement_id, finding_key)
        );

        -- Suppression: EY hides a finding from the client view. Requires a
        -- reason (stored for audit, not shown to client). The client view's
        -- diagnosis endpoint filters out suppressed findings when
        -- ?view=client; editor view returns them with a "suppressed" flag.
        CREATE TABLE IF NOT EXISTS editor_suppressions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engagement_id TEXT NOT NULL DEFAULT 'default',
            finding_key TEXT NOT NULL,
            reason TEXT NOT NULL,
            author TEXT,
            suppressed_at REAL DEFAULT (strftime('%s','now')),
            UNIQUE(engagement_id, finding_key)
        );

        -- Text rewrites: EY edits the generated prose of a finding's
        -- headline, narrative, or prescribed action. Numbers stay locked
        -- (enforced by the edit UI, not at the schema level). The "field"
        -- column identifies which piece of text was rewritten.
        -- Wired to UI in v18b.
        CREATE TABLE IF NOT EXISTS editor_rewrites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engagement_id TEXT NOT NULL DEFAULT 'default',
            finding_key TEXT NOT NULL,
            field TEXT NOT NULL CHECK (field IN ('headline', 'narrative', 'prescribed_action')),
            original_text TEXT NOT NULL,
            rewritten_text TEXT NOT NULL,
            author TEXT,
            updated_at REAL DEFAULT (strftime('%s','now')),
            UNIQUE(engagement_id, finding_key, field)
        );

        -- Audit log. Every write to any of the override tables appends
        -- an immutable row here. Supports the compliance story ("show me
        -- every edit EY made on this engagement") and lets us show a
        -- revision history per finding in a future session.
        CREATE TABLE IF NOT EXISTS editor_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engagement_id TEXT NOT NULL DEFAULT 'default',
            finding_key TEXT,
            action TEXT NOT NULL,
            payload_json TEXT,
            author TEXT,
            at REAL DEFAULT (strftime('%s','now'))
        );

        -- Publish state. Every engagement has a single "published" version
        -- pointer. EY edits in draft; when they publish, the current
        -- overrides snapshot becomes the published version that the client
        -- view reads. Wired to UI in v18b.
        CREATE TABLE IF NOT EXISTS engagement_publish_state (
            engagement_id TEXT PRIMARY KEY DEFAULT 'default',
            published_snapshot_json TEXT,
            published_at REAL,
            published_by TEXT
        );

        -- Indexes for query performance
        CREATE INDEX IF NOT EXISTS idx_commentary_engagement ON editor_commentary(engagement_id);
        CREATE INDEX IF NOT EXISTS idx_suppressions_engagement ON editor_suppressions(engagement_id);
        CREATE INDEX IF NOT EXISTS idx_rewrites_engagement ON editor_rewrites(engagement_id);
        CREATE INDEX IF NOT EXISTS idx_audit_engagement ON editor_audit_log(engagement_id);
    """)
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {DB_PATH}")


def save_session(session_id: str, state: Dict, user_id: int = None):
    """Save session state to database. Strips DataFrames (stored as JSON-safe dicts)."""
    # Convert state to JSON-safe format (strip DataFrames, numpy)
    safe_state = {}
    skip_keys = {"campaign_data", "journey_data", "reporting_data", "training_data",
                 "attribution", "attribution_roi", "_attr_dicts",
                 "external_competitive", "external_events", "external_trends"}
    
    for k, v in state.items():
        if k in skip_keys:
            # Store metadata only (not full DataFrames)
            if v is not None and hasattr(v, 'shape'):
                safe_state[f"_meta_{k}"] = {"rows": len(v), "columns": list(v.columns)}
            elif v is not None and isinstance(v, dict) and any(hasattr(vv, 'shape') for vv in v.values()):
                safe_state[f"_meta_{k}"] = {"keys": list(v.keys())}
            continue
        try:
            json.dumps(v, cls=NumpyEncoder)
            safe_state[k] = v
        except (TypeError, ValueError):
            logger.debug(f"Skipping non-serializable key: {k}")
    
    conn = _get_conn()
    state_json = json.dumps(safe_state, cls=NumpyEncoder)
    conn.execute(
        "INSERT OR REPLACE INTO sessions (id, user_id, state_json, updated_at) VALUES (?, ?, ?, ?)",
        (session_id, user_id, state_json, time.time())
    )
    conn.commit()
    conn.close()


def load_session(session_id: str) -> Optional[Dict]:
    """Load session state from database."""
    conn = _get_conn()
    row = conn.execute("SELECT state_json FROM sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    if row and row["state_json"]:
        return json.loads(row["state_json"])
    return None


def save_scenario(user_id: int, session_id: str, name: str, description: str,
                  parameters: Dict, results: Dict) -> int:
    """Save an optimizer scenario."""
    conn = _get_conn()
    cursor = conn.execute(
        "INSERT INTO scenarios (user_id, session_id, name, description, parameters, results) VALUES (?,?,?,?,?,?)",
        (user_id, session_id, name, description,
         json.dumps(parameters, cls=NumpyEncoder),
         json.dumps(results, cls=NumpyEncoder))
    )
    conn.commit()
    scenario_id = cursor.lastrowid
    conn.close()
    return scenario_id


def list_scenarios(user_id: int = None, session_id: str = None) -> list:
    """List saved scenarios."""
    conn = _get_conn()
    if user_id:
        rows = conn.execute(
            "SELECT id, name, description, parameters, created_at FROM scenarios WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()
    elif session_id:
        rows = conn.execute(
            "SELECT id, name, description, parameters, created_at FROM scenarios WHERE session_id = ? ORDER BY created_at DESC",
            (session_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, name, description, parameters, created_at FROM scenarios ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
    conn.close()
    return [{"id": r["id"], "name": r["name"], "description": r["description"],
             "parameters": json.loads(r["parameters"]) if r["parameters"] else {},
             "created_at": r["created_at"]} for r in rows]


def load_scenario(scenario_id: int) -> Optional[Dict]:
    """Load a saved scenario."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM scenarios WHERE id = ?", (scenario_id,)
    ).fetchone()
    conn.close()
    if row:
        return {
            "id": row["id"], "name": row["name"], "description": row["description"],
            "parameters": json.loads(row["parameters"]) if row["parameters"] else {},
            "results": json.loads(row["results"]) if row["results"] else {},
            "created_at": row["created_at"],
        }
    return None


def compare_scenarios(ids: list) -> list:
    """Load multiple scenarios for comparison."""
    conn = _get_conn()
    placeholders = ",".join(["?"] * len(ids))
    rows = conn.execute(
        f"SELECT * FROM scenarios WHERE id IN ({placeholders})", ids
    ).fetchall()
    conn.close()
    return [{
        "id": r["id"], "name": r["name"],
        "parameters": json.loads(r["parameters"]) if r["parameters"] else {},
        "results": json.loads(r["results"]) if r["results"] else {},
    } for r in rows]


# ── Auth helpers ──

def create_user(username: str, password_hash: str, role: str = "analyst") -> int:
    conn = _get_conn()
    try:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, password_hash, role)
        )
        conn.commit()
        user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError(f"Username '{username}' already exists")
    conn.close()
    return user_id


def get_user(username: str) -> Optional[Dict]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if row:
        return {"id": row["id"], "username": row["username"],
                "password_hash": row["password_hash"], "role": row["role"]}
    return None


def get_user_by_id(user_id: int) -> Optional[Dict]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if row:
        return {"id": row["id"], "username": row["username"], "role": row["role"]}
    return None


# ── EY Editor Overlay ──
#
# These functions are the full persistence API for the overlay. The
# frontend editor calls these via new /api/editor/* endpoints; the client
# view calls get_published_overrides() to layer EY edits onto generated
# findings before rendering.


def _log_audit(engagement_id: str, finding_key: Optional[str], action: str,
               payload: Optional[Dict] = None, author: Optional[str] = None) -> None:
    """Append an immutable audit row. Called internally by every write."""
    conn = _get_conn()
    conn.execute(
        "INSERT INTO editor_audit_log (engagement_id, finding_key, action, payload_json, author) "
        "VALUES (?, ?, ?, ?, ?)",
        (engagement_id, finding_key, action,
         json.dumps(payload, cls=NumpyEncoder) if payload else None, author),
    )
    conn.commit()
    conn.close()


# ── Commentary ──

def set_commentary(engagement_id: str, finding_key: str, text: str,
                   author: Optional[str] = None) -> None:
    """Create or replace EY commentary for a finding."""
    conn = _get_conn()
    conn.execute(
        "INSERT INTO editor_commentary (engagement_id, finding_key, commentary_text, author, updated_at) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(engagement_id, finding_key) DO UPDATE SET "
        "  commentary_text = excluded.commentary_text, "
        "  author = excluded.author, "
        "  updated_at = excluded.updated_at",
        (engagement_id, finding_key, text, author, time.time()),
    )
    conn.commit()
    conn.close()
    _log_audit(engagement_id, finding_key, "commentary_set",
               {"text_length": len(text)}, author)


def delete_commentary(engagement_id: str, finding_key: str,
                      author: Optional[str] = None) -> bool:
    """Remove commentary for a finding. Returns True if a row was deleted."""
    conn = _get_conn()
    cursor = conn.execute(
        "DELETE FROM editor_commentary WHERE engagement_id = ? AND finding_key = ?",
        (engagement_id, finding_key),
    )
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    if deleted:
        _log_audit(engagement_id, finding_key, "commentary_deleted", None, author)
    return deleted


def get_all_commentary(engagement_id: str) -> Dict[str, Dict]:
    """Return all commentary for an engagement as {finding_key: {text, author, updated_at}}."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT finding_key, commentary_text, author, updated_at FROM editor_commentary "
        "WHERE engagement_id = ?",
        (engagement_id,),
    ).fetchall()
    conn.close()
    return {
        r["finding_key"]: {
            "text": r["commentary_text"],
            "author": r["author"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    }


# ── Suppression ──

def suppress_finding(engagement_id: str, finding_key: str, reason: str,
                     author: Optional[str] = None) -> None:
    """Mark a finding as suppressed (hidden from client view)."""
    if not reason or not reason.strip():
        raise ValueError("Suppression reason is required for audit compliance")
    conn = _get_conn()
    conn.execute(
        "INSERT INTO editor_suppressions (engagement_id, finding_key, reason, author, suppressed_at) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(engagement_id, finding_key) DO UPDATE SET "
        "  reason = excluded.reason, "
        "  author = excluded.author, "
        "  suppressed_at = excluded.suppressed_at",
        (engagement_id, finding_key, reason, author, time.time()),
    )
    conn.commit()
    conn.close()
    _log_audit(engagement_id, finding_key, "finding_suppressed",
               {"reason": reason}, author)


def unsuppress_finding(engagement_id: str, finding_key: str,
                        author: Optional[str] = None) -> bool:
    """Restore a previously suppressed finding. Returns True if a row was deleted."""
    conn = _get_conn()
    cursor = conn.execute(
        "DELETE FROM editor_suppressions WHERE engagement_id = ? AND finding_key = ?",
        (engagement_id, finding_key),
    )
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    if deleted:
        _log_audit(engagement_id, finding_key, "finding_unsuppressed", None, author)
    return deleted


def get_all_suppressions(engagement_id: str) -> Dict[str, Dict]:
    """Return all suppressions for an engagement as {finding_key: {reason, author, suppressed_at}}."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT finding_key, reason, author, suppressed_at FROM editor_suppressions "
        "WHERE engagement_id = ?",
        (engagement_id,),
    ).fetchall()
    conn.close()
    return {
        r["finding_key"]: {
            "reason": r["reason"],
            "author": r["author"],
            "suppressed_at": r["suppressed_at"],
        }
        for r in rows
    }


# ── Rewrites (schema ready, wired to UI in v18b) ──

def set_rewrite(engagement_id: str, finding_key: str, field: str,
                original: str, rewritten: str,
                author: Optional[str] = None) -> None:
    """Save a text rewrite for a specific field of a finding."""
    if field not in ("headline", "narrative", "prescribed_action"):
        raise ValueError(f"Invalid rewrite field: {field}")
    conn = _get_conn()
    conn.execute(
        "INSERT INTO editor_rewrites (engagement_id, finding_key, field, original_text, "
        "  rewritten_text, author, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(engagement_id, finding_key, field) DO UPDATE SET "
        "  rewritten_text = excluded.rewritten_text, "
        "  author = excluded.author, "
        "  updated_at = excluded.updated_at",
        (engagement_id, finding_key, field, original, rewritten, author, time.time()),
    )
    conn.commit()
    conn.close()
    _log_audit(engagement_id, finding_key, f"rewrite_{field}",
               {"original_length": len(original), "new_length": len(rewritten)}, author)


def delete_rewrite(engagement_id: str, finding_key: str, field: str,
                    author: Optional[str] = None) -> bool:
    """Revert a rewrite back to the generated text."""
    conn = _get_conn()
    cursor = conn.execute(
        "DELETE FROM editor_rewrites WHERE engagement_id = ? AND finding_key = ? AND field = ?",
        (engagement_id, finding_key, field),
    )
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    if deleted:
        _log_audit(engagement_id, finding_key, f"rewrite_{field}_deleted", None, author)
    return deleted


def get_all_rewrites(engagement_id: str) -> Dict[str, Dict[str, str]]:
    """Return all rewrites as {finding_key: {field: rewritten_text}}."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT finding_key, field, rewritten_text FROM editor_rewrites "
        "WHERE engagement_id = ?",
        (engagement_id,),
    ).fetchall()
    conn.close()
    out: Dict[str, Dict[str, str]] = {}
    for r in rows:
        out.setdefault(r["finding_key"], {})[r["field"]] = r["rewritten_text"]
    return out


# ── Combined override loader ──

def get_all_overrides(engagement_id: str = "default") -> Dict:
    """
    Load every override for an engagement in a single shape the narrative
    engine can consume. Used by the /api/diagnosis endpoint to layer
    edits onto generated findings before returning.
    """
    return {
        "commentary": get_all_commentary(engagement_id),
        "suppressions": get_all_suppressions(engagement_id),
        "rewrites": get_all_rewrites(engagement_id),
    }


# ── Audit log ──

def get_audit_log(engagement_id: str = "default", limit: int = 100) -> list:
    """Return recent audit entries for an engagement."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT finding_key, action, payload_json, author, at FROM editor_audit_log "
        "WHERE engagement_id = ? ORDER BY at DESC LIMIT ?",
        (engagement_id, limit),
    ).fetchall()
    conn.close()
    return [
        {
            "finding_key": r["finding_key"],
            "action": r["action"],
            "payload": json.loads(r["payload_json"]) if r["payload_json"] else None,
            "author": r["author"],
            "at": r["at"],
        }
        for r in rows
    ]


# Initialize on import
init_db()
