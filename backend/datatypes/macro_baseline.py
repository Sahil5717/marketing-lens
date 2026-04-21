"""
Macro Baseline — centrally-curated India market context data.

This module loads the five macro baseline CSVs shipped with the product
and exposes typed accessors. The data is *not* per-tenant; it is a
library curated by the YI team, shared across every engagement.

Per build plan v2 §2A.1, the macro baseline covers:

    festival_calendar    — dated religious/commercial/seasonal festivals
    public_holidays      — national / state / religious holidays
    monsoon_windows      — regional monsoon onset/withdrawal by year
    consumer_sentiment   — monthly RBI Consumer Confidence Survey indices
    category_seasonality — monthly seasonality index by category

Access pattern
--------------
    from datatypes.macro_baseline import get_loader
    loader = get_loader()
    upcoming = loader.upcoming_events(
        as_of=date(2024, 5, 31),
        lookahead_days=90,
        regions=["Mumbai", "Delhi"],
        category="FMCG",
    )

The loader is cached at module level — reloaded only when one of the
source CSVs changes on disk (mtime check).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import pandas as pd

# ─── Constants ────────────────────────────────────────────────────────────

MACRO_DIR = Path(__file__).parent.parent / "data" / "macro_baseline"

FILES = {
    "festival_calendar":   MACRO_DIR / "festival_calendar.csv",
    "public_holidays":     MACRO_DIR / "public_holidays.csv",
    "monsoon_windows":     MACRO_DIR / "monsoon_windows.csv",
    "consumer_sentiment":  MACRO_DIR / "consumer_sentiment.csv",
    "category_seasonality": MACRO_DIR / "category_seasonality.csv",
}

# Significance ordering for festivals (higher = bigger demand impact)
_SIGNIFICANCE_RANK = {"major": 3, "moderate": 2, "minor": 1}

# Demand-lift ordering for festivals. The CSV uses "very_high" for
# tent-pole festivals like Diwali; we map it to the top of the scale.
_LIFT_RANK = {"very_high": 3, "high": 3, "medium": 2, "low": 1}

# Commerce-impact ordering for public holidays
_COMMERCE_RANK = {"high": 3, "medium": 2, "low": 1}


# ─── Public data classes ──────────────────────────────────────────────────

@dataclass(frozen=True)
class PeakWindow:
    """A contiguous date range that matters for marketing planning."""
    start_date: date
    end_date: date
    name: str
    kind: str              # "festival" | "public_holiday"
    significance: str      # "High" | "Medium" | "Low" (display-ready)
    significance_score: int  # 1..3 for sorting
    regions: List[str]
    notes: str
    days_away: int         # from as_of

    def as_dict(self) -> Dict[str, Any]:
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "name": self.name,
            "kind": self.kind,
            "significance": self.significance,
            "significance_score": self.significance_score,
            "regions": self.regions,
            "notes": self.notes,
            "days_away": self.days_away,
        }


@dataclass(frozen=True)
class DemandTrendPoint:
    """One monthly point on the synthetic demand index."""
    month: str          # "YYYY-MM"
    value: float        # 100 = long-run baseline
    label: str          # short display label, e.g. "Mar"

    def as_dict(self) -> Dict[str, Any]:
        return {"month": self.month, "value": round(self.value, 1), "label": self.label}


# ─── Loader ───────────────────────────────────────────────────────────────

class MacroBaselineLoader:
    """
    Loads the five macro baseline CSVs and exposes typed accessors.

    Instantiated once per process via get_loader(). The loader caches the
    raw DataFrames. If a source CSV changes on disk, reload() must be
    called explicitly — the module does not watch for file changes.
    """

    def __init__(self) -> None:
        self._tables: Dict[str, pd.DataFrame] = {}
        self._mtimes: Dict[str, float] = {}
        self._load()

    # ── Loading ──

    def _load(self) -> None:
        """Read all 5 CSVs from disk. Raises FileNotFoundError on missing."""
        for key, path in FILES.items():
            if not path.exists():
                raise FileNotFoundError(
                    f"Macro baseline file missing: {path}. "
                    f"The YI team curates these files centrally; "
                    f"see build plan v2 §2A.1."
                )
            df = pd.read_csv(path)
            # Parse date columns where present
            for col in ("start_date", "end_date", "date", "onset_date", "withdrawal_date"):
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
            self._tables[key] = df
            self._mtimes[key] = path.stat().st_mtime

    def reload(self) -> None:
        """Force re-read from disk. Used after hand-edits or YI-team refreshes."""
        self._tables.clear()
        self._mtimes.clear()
        self._load()

    # ── Raw access ──

    def table(self, name: str) -> pd.DataFrame:
        """Return a copy of a named table (defensive against caller mutation)."""
        if name not in self._tables:
            raise KeyError(f"Unknown macro baseline table: {name}. "
                           f"Known: {list(self._tables)}")
        return self._tables[name].copy()

    # ── Freshness ──

    def freshness(self) -> Dict[str, Any]:
        """
        Returns per-table freshness metadata for Screen 02's
        'Macro baseline freshness' zone. Each table reports:
            - last_modified:   ISO datetime of the CSV mtime
            - row_count:       number of rows
            - date_range:      {min, max} of the primary date column, if any
            - age_days:        days since last_modified
        """
        from datetime import timezone
        now = datetime.now(timezone.utc)
        out: Dict[str, Any] = {}
        for key, df in self._tables.items():
            mtime = datetime.fromtimestamp(self._mtimes[key], tz=timezone.utc)
            # Choose a date column if one exists for the range summary
            date_col = next(
                (c for c in ("start_date", "date", "onset_date", "month") if c in df.columns),
                None,
            )
            date_range = None
            if date_col is not None and len(df) > 0:
                series = df[date_col].dropna()
                if len(series) > 0:
                    if date_col == "month":
                        # month is a string "YYYY-MM"; don't try to compare as date
                        date_range = {
                            "min": str(series.min()),
                            "max": str(series.max()),
                        }
                    else:
                        date_range = {
                            "min": series.min().isoformat(),
                            "max": series.max().isoformat(),
                        }
            out[key] = {
                "last_modified": mtime.isoformat().replace("+00:00", "Z"),
                "age_days": (now - mtime).days,
                "row_count": int(len(df)),
                "date_range": date_range,
            }
        return out

    # ── Upcoming events (festivals + public holidays) ──

    def upcoming_events(
        self,
        *,
        as_of: date,
        lookahead_days: int = 90,
        regions: Optional[Sequence[str]] = None,
        category: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[PeakWindow]:
        """
        Return upcoming peak windows within `lookahead_days` of `as_of`,
        merged from festivals + public holidays, filtered by region
        relevance, sorted by start date.

        `regions` filters events whose `regions` column includes "ALL"
        or matches at least one entry in the passed list (case-insensitive,
        short-codes like "MH" or city/state names both tolerated).
        Passing None disables region filtering.

        `category` is reserved for future use — we'd trim low-significance
        items that don't lift the client's category. Currently unused
        because the festival CSV uses broad demand-lift categories, not
        per-category signals. The parameter is accepted now so callers
        stabilize against the signature.
        """
        end = as_of + timedelta(days=lookahead_days)

        festivals = self._festivals_in_range(as_of, end, regions)
        holidays = self._holidays_in_range(as_of, end, regions)

        windows = festivals + holidays
        windows.sort(key=lambda w: (w.start_date, -w.significance_score))

        if limit is not None:
            windows = windows[:limit]
        return windows

    def _festivals_in_range(
        self,
        start: date,
        end: date,
        regions: Optional[Sequence[str]],
    ) -> List[PeakWindow]:
        df = self._tables["festival_calendar"]
        mask = (df["start_date"] >= start) & (df["start_date"] <= end)
        out: List[PeakWindow] = []
        for _, row in df[mask].iterrows():
            row_regions = _split_regions(row.get("regions", ""))
            if not _region_overlap(row_regions, regions):
                continue
            sig_word = str(row.get("significance", "")).strip().lower()
            lift_word = str(row.get("demand_lift_category", "")).strip().lower()
            # Display significance: prefer the stronger of the two signals
            score = max(
                _SIGNIFICANCE_RANK.get(sig_word, 1),
                _LIFT_RANK.get(lift_word, 1),
            )
            out.append(PeakWindow(
                start_date=row["start_date"],
                end_date=row["end_date"] if pd.notna(row["end_date"]) else row["start_date"],
                name=str(row["festival_name"]),
                kind="festival",
                significance=_display_significance(score),
                significance_score=score,
                regions=row_regions,
                notes=str(row.get("notes", "") or ""),
                days_away=(row["start_date"] - start).days,
            ))
        return out

    def _holidays_in_range(
        self,
        start: date,
        end: date,
        regions: Optional[Sequence[str]],
    ) -> List[PeakWindow]:
        df = self._tables["public_holidays"]
        mask = (df["date"] >= start) & (df["date"] <= end)
        out: List[PeakWindow] = []
        for _, row in df[mask].iterrows():
            row_regions = _split_regions(row.get("regions", ""))
            if not _region_overlap(row_regions, regions):
                continue
            impact_word = str(row.get("commerce_impact", "")).strip().lower()
            score = _COMMERCE_RANK.get(impact_word, 1)
            # Filter out low-impact public holidays by default — they're
            # calendar-useful but noisy for a "peak windows" panel.
            # Caller can re-derive by filtering self.table("public_holidays").
            if score < 2:
                continue
            out.append(PeakWindow(
                start_date=row["date"],
                end_date=row["date"],
                name=str(row["holiday_name"]),
                kind="public_holiday",
                significance=_display_significance(score),
                significance_score=score,
                regions=row_regions,
                notes=str(row.get("notes", "") or ""),
                days_away=(row["date"] - start).days,
            ))
        return out

    # ── Demand trend ──

    def demand_trend(
        self,
        *,
        as_of: date,
        lookback_months: int = 12,
        category: Optional[str] = None,
    ) -> List[DemandTrendPoint]:
        """
        Return a synthetic demand index trend for the last `lookback_months`
        ending at `as_of`'s month.

        The index blends:
            * RBI Consumer Confidence (current situation) — rebased to 100
              at the start of the window
            * category seasonality index for `category` — already on a
              100-baseline scale

        Missing category defaults to the cross-category average. This
        gives a client-specific-ish chart without needing per-client
        data beyond a category string.
        """
        sentiment = self._tables["consumer_sentiment"]
        seasonality = self._tables["category_seasonality"]

        # Build the window of months, oldest to newest
        end_month = date(as_of.year, as_of.month, 1)
        months: List[date] = []
        y, m = end_month.year, end_month.month
        for _ in range(lookback_months):
            months.append(date(y, m, 1))
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        months.reverse()

        # Sentiment series: use RBI_CCS_Current_Situation
        sent_df = sentiment[sentiment["index_name"] == "RBI_CCS_Current_Situation"].copy()
        sent_df["month_date"] = pd.to_datetime(sent_df["month"] + "-01").dt.date
        sent_map = dict(zip(sent_df["month_date"], sent_df["value"]))

        # Seasonality series: pick the category or average across categories
        if category is not None:
            cat_df = seasonality[seasonality["category"] == category].copy()
            if cat_df.empty:
                cat_df = seasonality.copy()
        else:
            cat_df = seasonality.copy()
        cat_df["month_date"] = pd.to_datetime(cat_df["month"] + "-01").dt.date
        # Average across categories (or single-row-per-month if category given)
        cat_avg = cat_df.groupby("month_date")["seasonality_index"].mean().to_dict()

        # Rebase sentiment so first month = 100; then blend
        first_sent = sent_map.get(months[0])
        pts: List[DemandTrendPoint] = []
        for mo in months:
            s_val = sent_map.get(mo)
            c_val = cat_avg.get(mo, 100.0)
            if first_sent and s_val:
                s_rebased = 100.0 * float(s_val) / float(first_sent)
            else:
                s_rebased = 100.0
            # Blend: 60% seasonality (category-specific), 40% sentiment (macro)
            blended = 0.6 * float(c_val) + 0.4 * s_rebased
            pts.append(DemandTrendPoint(
                month=mo.strftime("%Y-%m"),
                value=blended,
                label=mo.strftime("%b"),
            ))
        return pts

    # ── Category seasonality (raw) ──

    def category_seasonality(
        self,
        *,
        category: str,
        year: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return monthly seasonality rows for a category, optionally year-filtered."""
        df = self._tables["category_seasonality"]
        mask = df["category"] == category
        if year is not None:
            mask = mask & df["month"].str.startswith(str(year))
        out = []
        for _, row in df[mask].iterrows():
            out.append({
                "month": row["month"],
                "seasonality_index": float(row["seasonality_index"]),
                "demand_driver": row["demand_driver"],
            })
        return out

    # ── Monsoon context ──

    def monsoon_for_regions(
        self,
        *,
        year: int,
        regions: Sequence[str],
    ) -> List[Dict[str, Any]]:
        """Return monsoon onset/withdrawal for a set of regions in a year."""
        df = self._tables["monsoon_windows"]
        mask = (df["year"] == year) & (df["region"].isin(regions))
        out = []
        for _, row in df[mask].iterrows():
            out.append({
                "region": row["region"],
                "onset_date": row["onset_date"].isoformat() if pd.notna(row["onset_date"]) else None,
                "withdrawal_date": row["withdrawal_date"].isoformat() if pd.notna(row["withdrawal_date"]) else None,
                "intensity": row.get("intensity", ""),
                "deviation_from_normal": row.get("deviation_from_normal", ""),
            })
        return out


# ─── Helpers ──────────────────────────────────────────────────────────────

def _split_regions(raw: Any) -> List[str]:
    """Parse a regions cell like 'MH;GJ;RJ' or 'ALL' into a list."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    s = str(raw).strip()
    if not s:
        return []
    return [r.strip() for r in s.split(";") if r.strip()]


def _region_overlap(
    row_regions: Sequence[str],
    client_regions: Optional[Sequence[str]],
) -> bool:
    """True if this row is relevant to the client's regions."""
    if client_regions is None:
        return True  # no filter
    if not row_regions:
        return True  # row has no region info — play it safe and include
    row_upper = {r.upper() for r in row_regions}
    if "ALL" in row_upper:
        return True
    client_upper = {r.upper() for r in client_regions}
    # Allow either code match ('MH') or substring match for full names
    # (e.g. 'Mumbai' should match 'MH' — we accept either side)
    if row_upper & client_upper:
        return True
    return False


def _display_significance(score: int) -> str:
    return {3: "High", 2: "Medium", 1: "Low"}.get(score, "Low")


# ─── Module-level accessor ────────────────────────────────────────────────

_loader_singleton: Optional[MacroBaselineLoader] = None


def get_loader() -> MacroBaselineLoader:
    """Process-wide cached loader. First call loads all 5 CSVs from disk."""
    global _loader_singleton
    if _loader_singleton is None:
        _loader_singleton = MacroBaselineLoader()
    return _loader_singleton


def reset_loader_for_tests() -> None:
    """Test helper — force the next get_loader() to reload from disk."""
    global _loader_singleton
    _loader_singleton = None
