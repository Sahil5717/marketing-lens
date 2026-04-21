"""
Tests for datatypes.macro_baseline.

These tests use the real CSVs shipped in backend/data/macro_baseline/
because the whole point is to verify the shape and content of what the
YI team curates. If the CSVs are edited, these tests should catch
breaking schema changes.
"""
from datetime import date
import pytest

from datatypes.macro_baseline import (
    get_loader,
    reset_loader_for_tests,
    MacroBaselineLoader,
    PeakWindow,
    DemandTrendPoint,
)


@pytest.fixture(autouse=True)
def _fresh_loader():
    reset_loader_for_tests()
    yield
    reset_loader_for_tests()


# ─── Loading ──────────────────────────────────────────────────────────────

def test_loader_loads_all_five_tables():
    loader = get_loader()
    for name in (
        "festival_calendar",
        "public_holidays",
        "monsoon_windows",
        "consumer_sentiment",
        "category_seasonality",
    ):
        df = loader.table(name)
        assert len(df) > 0, f"{name} is empty"


def test_loader_is_singleton():
    a = get_loader()
    b = get_loader()
    assert a is b


def test_loader_reload_refreshes_mtimes():
    loader = get_loader()
    before = dict(loader._mtimes)
    loader.reload()
    # Reload should re-stat, keeping or updating mtimes
    assert set(loader._mtimes) == set(before)


# ─── Freshness ────────────────────────────────────────────────────────────

def test_freshness_reports_all_five_tables():
    loader = get_loader()
    fresh = loader.freshness()
    assert set(fresh.keys()) == {
        "festival_calendar",
        "public_holidays",
        "monsoon_windows",
        "consumer_sentiment",
        "category_seasonality",
    }
    for name, meta in fresh.items():
        assert meta["row_count"] > 0
        assert "last_modified" in meta
        assert "age_days" in meta
        assert meta["age_days"] >= 0


def test_freshness_date_ranges_are_valid():
    loader = get_loader()
    fresh = loader.freshness()
    # Festivals cover multiple years (2022–2026 per plan)
    fc = fresh["festival_calendar"]["date_range"]
    assert fc is not None
    assert fc["min"] < fc["max"]
    # Consumer sentiment is monthly strings
    cs = fresh["consumer_sentiment"]["date_range"]
    assert cs is not None
    assert cs["min"].startswith("2022")


# ─── Upcoming events ──────────────────────────────────────────────────────

def test_upcoming_events_default_returns_sorted_windows():
    loader = get_loader()
    windows = loader.upcoming_events(
        as_of=date(2024, 8, 1),
        lookahead_days=120,
    )
    assert len(windows) > 0
    # Sorted by start date ascending
    for a, b in zip(windows, windows[1:]):
        assert a.start_date <= b.start_date
    # All within the window
    for w in windows:
        assert date(2024, 8, 1) <= w.start_date <= date(2024, 11, 29)


def test_upcoming_events_respects_lookahead():
    loader = get_loader()
    narrow = loader.upcoming_events(as_of=date(2024, 8, 1), lookahead_days=30)
    wide = loader.upcoming_events(as_of=date(2024, 8, 1), lookahead_days=180)
    assert len(narrow) <= len(wide)


def test_upcoming_events_region_filter_includes_ALL():
    """Events marked 'ALL' regions must be included for any client region."""
    loader = get_loader()
    windows = loader.upcoming_events(
        as_of=date(2024, 8, 1),
        lookahead_days=180,
        regions=["Mumbai"],
    )
    # At least one ALL-region festival should come through (e.g. Diwali)
    names = {w.name for w in windows}
    assert len(names) > 0
    # Diwali is in this window and marked ALL — must appear
    assert any("Diwali" in n for n in names)


def test_upcoming_events_region_filter_excludes_mismatched():
    """Region-scoped events (e.g., MH;GJ) should be excluded for other regions."""
    loader = get_loader()
    # Makar Sankranti is MH;GJ;RJ;KA;AP;TG — should not appear for Delhi-only
    windows = loader.upcoming_events(
        as_of=date(2024, 1, 1),
        lookahead_days=60,
        regions=["DL"],  # Delhi short code
    )
    names = {w.name for w in windows}
    # Republic Day (ALL, though typically low impact so might be filtered by impact)
    # We just assert the regional festival didn't leak through
    # The Makar Sankranti row does exist for Jan 14 — should be suppressed
    has_makar = any("Makar Sankranti" in n for n in names)
    assert not has_makar, f"regional festival leaked into Delhi filter: {names}"


def test_upcoming_events_limit_caps_results():
    loader = get_loader()
    unlimited = loader.upcoming_events(as_of=date(2024, 1, 1), lookahead_days=365)
    capped = loader.upcoming_events(as_of=date(2024, 1, 1), lookahead_days=365, limit=3)
    assert len(capped) == 3
    assert len(unlimited) > 3


def test_upcoming_events_returns_PeakWindow_objects():
    loader = get_loader()
    windows = loader.upcoming_events(as_of=date(2024, 8, 1), lookahead_days=120)
    assert all(isinstance(w, PeakWindow) for w in windows)
    w = windows[0]
    d = w.as_dict()
    assert {"start_date", "end_date", "name", "kind", "significance",
            "days_away", "regions"} <= set(d.keys())


def test_upcoming_events_days_away_calculation():
    loader = get_loader()
    as_of = date(2024, 8, 1)
    windows = loader.upcoming_events(as_of=as_of, lookahead_days=180)
    for w in windows:
        expected = (w.start_date - as_of).days
        assert w.days_away == expected


def test_upcoming_events_filters_low_impact_holidays():
    """Low-commerce-impact public holidays are excluded from peak windows."""
    loader = get_loader()
    windows = loader.upcoming_events(as_of=date(2024, 1, 1), lookahead_days=365)
    # Republic Day is low impact; Independence Day is medium — only latter should appear
    names = [w.name for w in windows if w.kind == "public_holiday"]
    assert not any("Republic Day" in n for n in names)


# ─── Demand trend ─────────────────────────────────────────────────────────

def test_demand_trend_default_shape():
    loader = get_loader()
    trend = loader.demand_trend(as_of=date(2024, 6, 30), lookback_months=12)
    assert len(trend) == 12
    assert all(isinstance(p, DemandTrendPoint) for p in trend)
    # Months are in ascending order
    months = [p.month for p in trend]
    assert months == sorted(months)


def test_demand_trend_respects_lookback():
    loader = get_loader()
    short = loader.demand_trend(as_of=date(2024, 6, 30), lookback_months=3)
    assert len(short) == 3


def test_demand_trend_with_category():
    loader = get_loader()
    apparel = loader.demand_trend(as_of=date(2024, 6, 30), lookback_months=6, category="Apparel")
    fmcg = loader.demand_trend(as_of=date(2024, 6, 30), lookback_months=6, category="FMCG")
    # Different categories should produce different values
    assert [p.value for p in apparel] != [p.value for p in fmcg]


def test_demand_trend_unknown_category_falls_back_to_avg():
    loader = get_loader()
    # Should not raise; should fall back to cross-category mean
    trend = loader.demand_trend(
        as_of=date(2024, 6, 30),
        lookback_months=6,
        category="NonexistentCategory123",
    )
    assert len(trend) == 6


def test_demand_trend_values_on_sensible_scale():
    """Index should stay in a reasonable range around 100."""
    loader = get_loader()
    trend = loader.demand_trend(as_of=date(2024, 6, 30), lookback_months=12)
    for p in trend:
        assert 40 < p.value < 200, f"demand trend out of range: {p}"


# ─── Category seasonality ─────────────────────────────────────────────────

def test_category_seasonality_returns_monthly_rows():
    loader = get_loader()
    rows = loader.category_seasonality(category="FMCG", year=2024)
    assert len(rows) == 12
    months = [r["month"] for r in rows]
    assert months[0].startswith("2024-")
    assert months[-1].startswith("2024-")


# ─── Monsoon ──────────────────────────────────────────────────────────────

def test_monsoon_for_regions():
    loader = get_loader()
    m = loader.monsoon_for_regions(year=2024, regions=["Mumbai", "Delhi"])
    assert len(m) == 2
    regions = {r["region"] for r in m}
    assert regions == {"Mumbai", "Delhi"}
    for row in m:
        assert row["onset_date"] is not None
