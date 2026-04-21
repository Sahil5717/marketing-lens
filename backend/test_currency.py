"""Tests for currency.py."""
import pytest

from currency import (
    format_money, format_delta, format_rate, format_count,
    get_spec, UnsupportedCurrency, CURRENCY_TABLE,
)


# ─── USD formatting ──────────────────────────────────────────────────────

def test_usd_millions():
    assert format_money(248_000_000, "USD") == "$248M"
    assert format_money(12_400_000, "USD") == "$12.4M"
    assert format_money(1_000_000, "USD") == "$1.0M"


def test_usd_billions():
    """Large revenue values render as $X.XB, not $XXXXM."""
    assert format_money(2_480_000_000, "USD") == "$2.5B"
    assert format_money(1_000_000_000, "USD") == "$1.0B"
    assert format_money(100_000_000_000, "USD") == "$100B"


def test_eur_and_gbp_billions():
    assert format_money(2_480_000_000, "EUR") == "€2.5B"
    assert format_money(2_480_000_000, "GBP") == "£2.5B"


def test_usd_thousands():
    assert format_money(582_000, "USD") == "$582K"
    assert format_money(1_500, "USD") == "$1.5K"   # < 100 at K tier → 1 decimal
    assert format_money(12_400, "USD") == "$12.4K"
    assert format_money(150_000, "USD") == "$150K"  # >= 100 at K tier → 0 decimals


def test_usd_below_thousand():
    assert format_money(582, "USD") == "$582"
    assert format_money(42, "USD") == "$42"


def test_usd_zero():
    assert format_money(0, "USD") == "$0M"


def test_usd_none_renders_as_zero():
    assert format_money(None, "USD") == "$0M"


# ─── INR formatting (legacy crore/lakh) ─────────────────────────────────

def test_inr_crore():
    assert format_money(248_000_000, "INR") == "₹24.8 Cr"
    assert format_money(2_480_000_000, "INR") == "₹248 Cr"
    assert format_money(10_000_000, "INR") == "₹1.0 Cr"


def test_inr_lakh():
    assert format_money(500_000, "INR") == "₹5.0 L"
    assert format_money(5_000_000, "INR") == "₹50.0 L"


def test_inr_below_lakh():
    assert format_money(582, "INR") == "₹582"


# ─── EUR and GBP mirror USD behavior ─────────────────────────────────────

def test_eur_and_gbp_use_million_convention():
    assert format_money(248_000_000, "EUR") == "€248M"
    assert format_money(248_000_000, "GBP") == "£248M"
    assert format_money(12_400_000, "EUR") == "€12.4M"


# ─── Signed formatting ──────────────────────────────────────────────────

def test_signed_positive_shows_plus():
    assert format_money(5_200_000, "USD", signed=True) == "+$5.2M"
    assert format_delta(5_200_000, "USD") == "+$5.2M"


def test_signed_negative_uses_proper_minus_sign():
    result = format_money(-3_100_000, "USD", signed=True)
    assert result == "\u2212$3.1M"   # U+2212, not "-"


def test_signed_negative_without_flag_still_negative():
    """Unsigned negative still gets a minus sign — signed controls the +."""
    assert format_money(-3_100_000, "USD") == "\u2212$3.1M"


def test_signed_zero_renders_unsigned():
    assert format_money(0, "USD", signed=True) == "$0M"


# ─── Case insensitivity + default ───────────────────────────────────────

def test_currency_is_case_insensitive():
    assert format_money(1_000_000, "usd") == "$1.0M"
    assert format_money(1_000_000, "Usd") == "$1.0M"


def test_empty_or_none_currency_falls_back_to_default():
    assert format_money(1_000_000, "") == "$1.0M"   # USD default


def test_unsupported_currency_raises():
    with pytest.raises(UnsupportedCurrency):
        format_money(1000, "CAD")
    with pytest.raises(UnsupportedCurrency):
        get_spec("XYZ")


# ─── Custom decimals override ───────────────────────────────────────────

def test_decimals_override():
    assert format_money(12_345_678, "USD", decimals=0) == "$12M"
    assert format_money(12_345_678, "USD", decimals=2) == "$12.35M"


# ─── Default decimal behavior ───────────────────────────────────────────

def test_large_values_drop_decimals():
    """Values >= 100 at the scale tier render without decimals."""
    assert format_money(248_000_000, "USD") == "$248M"
    assert format_money(99_000_000, "USD") == "$99.0M"  # < 100 at M tier → 1 decimal


# ─── Ancillary formatters ───────────────────────────────────────────────

def test_format_rate_basic():
    assert format_rate(3.62) == "3.62x"
    assert format_rate(10.3) == "10.30x"
    assert format_rate(None) == "—"
    assert format_rate(0) == "—"


def test_format_count_scales():
    assert format_count(98_300) == "98K"
    assert format_count(1_450_000) == "1.4M"
    assert format_count(42) == "42"
    assert format_count(None) == "—"
    assert format_count(0) == "—"


# ─── Table integrity ────────────────────────────────────────────────────

def test_all_currencies_have_required_fields():
    for code, spec in CURRENCY_TABLE.items():
        assert spec.code == code
        assert spec.symbol
        assert spec.scales  # at least one tier
        # Each scale tier is (threshold, divisor, suffix)
        for tier in spec.scales:
            assert len(tier) == 3
            threshold, divisor, suffix = tier
            assert threshold > 0
            assert divisor > 0
            assert isinstance(suffix, str)
