"""
Engagement entity — client × time-period unit (per plan v2 §2B.1).

An engagement is the unit of scoping for everything the analyst does:
data uploads, scenario assumptions, client handoff state, and starting
with v26, **currency + locale**.

This module is the single source of truth for engagement config. Every
route that needs to format money calls `get_engagement(id).currency`
and passes it to `currency.format_money()`. No route hardcodes USD/INR.

Schema
------
Adds a new `engagements` table to the existing SQLite DB. A single row
with `id = 'default'` is seeded on first use so legacy code paths
that pass `engagement_id="default"` keep working — they now resolve
to a real record with a currency.

Public API
----------
    get_engagement(id)           → EngagementConfig
    list_engagements()           → list[EngagementConfig]
    create_engagement(**fields)  → EngagementConfig
    update_engagement(id, **f)   → EngagementConfig
    delete_engagement(id)        → bool
    DEFAULT_ENGAGEMENT_ID = "default"

The thin `_read_state()` pattern that routes use today stays — this
layer is purely config, not state. State refactor (plan §4.2) is
separate work.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, asdict
from typing import List, Optional

from persistence import _get_conn
from currency import CURRENCY_TABLE, DEFAULT_CURRENCY, UnsupportedCurrency


DEFAULT_ENGAGEMENT_ID = "default"
DEFAULT_ENGAGEMENT_NAME = "Default Engagement"
DEFAULT_LOCALE = "en-US"


@dataclass
class EngagementConfig:
    """
    Everything a route needs to know about an engagement to format its
    output correctly.

    Fields
    ------
    id          unique string identifier (e.g. "acme-q2-2024")
    name        display name ("Acme Consumer Co. · Q2 2024")
    currency    ISO 4217 code: USD/INR/EUR/GBP
    locale      BCP 47 tag, used for date formatting hints (en-US, en-IN, ...)
    created_at  Unix timestamp
    updated_at  Unix timestamp
    """
    id: str
    name: str
    currency: str
    locale: str
    created_at: Optional[float] = None
    updated_at: Optional[float] = None

    def as_dict(self) -> dict:
        return asdict(self)


# ─── Table bootstrap ──────────────────────────────────────────────────────

def init_engagements_table() -> None:
    """
    Create the engagements table if missing and seed the 'default' row.
    Safe to call on every boot — idempotent.

    Called from api.py's startup hook alongside init_db().
    """
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS engagements (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            currency    TEXT NOT NULL DEFAULT 'USD',
            locale      TEXT NOT NULL DEFAULT 'en-US',
            created_at  REAL DEFAULT (strftime('%s','now')),
            updated_at  REAL DEFAULT (strftime('%s','now'))
        );
    """)
    # Seed the default engagement if missing — idempotent
    conn.execute(
        "INSERT OR IGNORE INTO engagements (id, name, currency, locale) "
        "VALUES (?, ?, ?, ?)",
        (DEFAULT_ENGAGEMENT_ID, DEFAULT_ENGAGEMENT_NAME, DEFAULT_CURRENCY, DEFAULT_LOCALE),
    )
    conn.commit()
    conn.close()


# ─── CRUD ─────────────────────────────────────────────────────────────────

def get_engagement(engagement_id: str = DEFAULT_ENGAGEMENT_ID) -> EngagementConfig:
    """
    Fetch an engagement by id. If the engagement doesn't exist, falls
    back to 'default' rather than raising — so routes stay renderable
    even if a caller passes an unknown id.
    """
    conn = _get_conn()
    row = conn.execute(
        "SELECT id, name, currency, locale, created_at, updated_at "
        "FROM engagements WHERE id = ?",
        (engagement_id,),
    ).fetchone()
    if row is None and engagement_id != DEFAULT_ENGAGEMENT_ID:
        # Fall through to default
        row = conn.execute(
            "SELECT id, name, currency, locale, created_at, updated_at "
            "FROM engagements WHERE id = ?",
            (DEFAULT_ENGAGEMENT_ID,),
        ).fetchone()
    conn.close()

    if row is None:
        # Default also missing — bootstrap must have failed; return a
        # hard-coded default rather than raise
        return EngagementConfig(
            id=DEFAULT_ENGAGEMENT_ID,
            name=DEFAULT_ENGAGEMENT_NAME,
            currency=DEFAULT_CURRENCY,
            locale=DEFAULT_LOCALE,
        )
    return EngagementConfig(**dict(row))


def list_engagements() -> List[EngagementConfig]:
    """All engagements, sorted by created_at descending."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, name, currency, locale, created_at, updated_at "
        "FROM engagements ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [EngagementConfig(**dict(r)) for r in rows]


def create_engagement(
    id: str,
    name: str,
    currency: str = DEFAULT_CURRENCY,
    locale: str = DEFAULT_LOCALE,
) -> EngagementConfig:
    """
    Create a new engagement. Raises ValueError if id already exists or
    currency is not supported.
    """
    _validate_currency(currency)
    _validate_id(id)

    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO engagements (id, name, currency, locale) "
            "VALUES (?, ?, ?, ?)",
            (id, name, currency.upper(), locale),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError(f"Engagement id {id!r} already exists")
    conn.close()
    return get_engagement(id)


def update_engagement(
    engagement_id: str,
    *,
    name: Optional[str] = None,
    currency: Optional[str] = None,
    locale: Optional[str] = None,
) -> EngagementConfig:
    """
    Update mutable fields on an engagement. Only fields passed as
    non-None are changed. Raises ValueError on unknown id or unsupported
    currency.
    """
    current = get_engagement(engagement_id)
    if current.id != engagement_id:
        # get_engagement fell back to default — original id doesn't exist
        raise ValueError(f"Unknown engagement id {engagement_id!r}")

    if currency is not None:
        _validate_currency(currency)

    conn = _get_conn()
    conn.execute(
        """
        UPDATE engagements SET
            name = COALESCE(?, name),
            currency = COALESCE(?, currency),
            locale = COALESCE(?, locale),
            updated_at = strftime('%s','now')
        WHERE id = ?
        """,
        (name, currency.upper() if currency else None, locale, engagement_id),
    )
    conn.commit()
    conn.close()
    return get_engagement(engagement_id)


def delete_engagement(engagement_id: str) -> bool:
    """
    Delete an engagement. Returns True if a row was deleted. The
    'default' engagement cannot be deleted — returns False silently
    to avoid breaking legacy callers.
    """
    if engagement_id == DEFAULT_ENGAGEMENT_ID:
        return False
    conn = _get_conn()
    cur = conn.execute("DELETE FROM engagements WHERE id = ?", (engagement_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


# ─── Validation ───────────────────────────────────────────────────────────

def _validate_currency(currency: str) -> None:
    if not currency or currency.upper() not in CURRENCY_TABLE:
        raise UnsupportedCurrency(
            f"Currency {currency!r} is not supported. "
            f"Known: {sorted(CURRENCY_TABLE)}"
        )


def _validate_id(engagement_id: str) -> None:
    if not engagement_id or not engagement_id.strip():
        raise ValueError("engagement id must be non-empty")
    # Keep ids URL-safe — no slashes, whitespace, or quotes
    forbidden = set(" /\\'\"\t\n\r")
    if any(ch in forbidden for ch in engagement_id):
        raise ValueError(
            f"engagement id {engagement_id!r} contains forbidden characters"
        )
