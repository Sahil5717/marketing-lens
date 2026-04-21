"""
Currency formatting for Yield Intelligence.

A single formatting entry point — `format_money(value, currency)` — used
across every route that emits rupee/dollar/euro/pound strings. Previously
each route had its own `_fmt_cr()` hardcoded to INR/Crore; this module
replaces that with a table-driven approach.

Supported currencies (v26):
    USD — dollars, uses $X.XM / $X.XK / $X,XXX
    INR — rupees, uses ₹X.X Cr / ₹X.X L (legacy India convention)
    EUR — euros, uses €X.XM / €X.XK / €X,XXX
    GBP — pounds, uses £X.XM / £X.XK / £X,XXX

New currencies are added by appending to CURRENCY_TABLE — no code
changes elsewhere.

Design notes
------------
The scale words are deliberately conservative:
  - USD/EUR/GBP top out at M (millions). Large amounts render as
    "$248.0M" rather than "$2.48B" so the display is consistent across
    the range most marketing budgets sit in.
  - INR keeps the Crore/Lakh convention because that's what Indian
    marketing decks use natively — converting to "₹680M" would feel
    foreign to Indian stakeholders.
  - A `signed` kwarg produces "+$5.2M" / "−$3.1M" for delta displays,
    using the minus sign (U+2212), not an ASCII hyphen.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


# ─── Currency table ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class CurrencySpec:
    code: str           # ISO 4217: USD, INR, EUR, GBP
    symbol: str         # $, ₹, €, £
    # Scale thresholds (in currency units) and their display suffixes.
    # Listed largest-first; the formatter picks the first threshold the
    # value exceeds.
    scales: tuple       # ((threshold, divisor, suffix), ...)
    # What to show for values smaller than the smallest scale threshold.
    # Typical: "$1,234" style with grouping separator.
    minor_format: str   # e.g. "{symbol}{value:,.0f}"


CURRENCY_TABLE: Dict[str, CurrencySpec] = {
    "USD": CurrencySpec(
        code="USD", symbol="$",
        scales=(
            (1e9, 1e9, "B"),    # $1.0B+
            (1e6, 1e6, "M"),    # $1.0M+
            (1e3, 1e3, "K"),    # $1.0K+
        ),
        minor_format="{symbol}{value:,.0f}",
    ),
    "EUR": CurrencySpec(
        code="EUR", symbol="€",
        scales=(
            (1e9, 1e9, "B"),
            (1e6, 1e6, "M"),
            (1e3, 1e3, "K"),
        ),
        minor_format="{symbol}{value:,.0f}",
    ),
    "GBP": CurrencySpec(
        code="GBP", symbol="£",
        scales=(
            (1e9, 1e9, "B"),
            (1e6, 1e6, "M"),
            (1e3, 1e3, "K"),
        ),
        minor_format="{symbol}{value:,.0f}",
    ),
    "INR": CurrencySpec(
        code="INR", symbol="₹",
        scales=(
            (1e7, 1e7, " Cr"),   # ₹1 Crore = 10 million
            (1e5, 1e5, " L"),    # ₹1 Lakh  = 100 thousand
        ),
        minor_format="{symbol}{value:,.0f}",
    ),
}

DEFAULT_CURRENCY = "USD"


class UnsupportedCurrency(ValueError):
    """Raised when asked to format a currency not in CURRENCY_TABLE."""


def get_spec(currency: str) -> CurrencySpec:
    """Return the CurrencySpec for a code. Normalizes casing."""
    if not currency:
        return CURRENCY_TABLE[DEFAULT_CURRENCY]
    code = currency.upper().strip()
    if code not in CURRENCY_TABLE:
        raise UnsupportedCurrency(
            f"Currency {currency!r} is not supported. "
            f"Known: {sorted(CURRENCY_TABLE)}"
        )
    return CURRENCY_TABLE[code]


def _default_display_tier(spec: CurrencySpec) -> str:
    """
    Return the suffix that makes sense for rendering zero and for
    column-header display. We pick the middle-of-the-road tier rather
    than the largest so "$0B" / "₹0 Cr" doesn't look odd for a zero.

    Convention:
      - Multi-tier currencies (USD/EUR/GBP with B/M/K): use M
      - INR (Cr/L): use Cr
      - Anything with only 1–2 tiers: use the second-largest if available,
        else the smallest
    """
    suffixes = [s for (_, _, s) in spec.scales]
    if "M" in suffixes:
        return "M"
    if " Cr" in suffixes:
        return " Cr"
    if len(suffixes) >= 2:
        return suffixes[1]  # second-largest
    return suffixes[-1] if suffixes else ""


# ─── Core formatter ──────────────────────────────────────────────────────

def format_money(
    value: Optional[float],
    currency: str = DEFAULT_CURRENCY,
    *,
    signed: bool = False,
    decimals: Optional[int] = None,
) -> str:
    """
    Format a currency value for display.

    Parameters
    ----------
    value : float | None
        Raw amount in base units (dollars, rupees, euros, pounds — never
        cents/paise). None and 0 render as "{symbol}0" at the largest
        scale (e.g. "$0M", "₹0 Cr") to keep column widths consistent.
    currency : str
        ISO 4217 code: "USD", "INR", "EUR", "GBP". Case-insensitive.
    signed : bool
        If True, prepend "+" for positive values and "−" (U+2212) for
        negative values. "+$5.2M" / "−$3.1M". Zero renders unsigned.
    decimals : int | None
        Override how many decimals to show at the M/K/Cr/L tier. When
        None, uses sensible defaults per tier:
            >= 100 units at that tier → 0 decimals ("$100M")
            otherwise                → 1 decimal  ("$12.4M")

    Returns
    -------
    str
        A ready-to-display string. Callers should not post-process.

    Examples
    --------
        format_money(248_000_000, "USD")       → "$248.0M"
        format_money(248_000_000, "INR")       → "₹24.8 Cr"
        format_money(5_200_000, "USD", signed=True)  → "+$5.2M"
        format_money(-3_100_000, "USD", signed=True) → "−$3.1M"
        format_money(0, "USD")                 → "$0M"
        format_money(582, "USD")               → "$582"
    """
    spec = get_spec(currency)

    if value is None:
        value = 0.0
    value = float(value)

    # Sign handling
    sign = ""
    if signed and value > 0:
        sign = "+"
    elif value < 0:
        sign = "\u2212"  # proper minus sign, not hyphen
    abs_value = abs(value)

    # Zero renders at the "default display tier" for the currency — the
    # tier most business numbers land in. Using the largest tier would
    # produce awkward strings like "$0B" after we added the Billion tier.
    # Convention: M for USD/EUR/GBP, Cr for INR.
    if abs_value == 0:
        default_tier = _default_display_tier(spec)
        return f"{sign}{spec.symbol}0{default_tier}"

    # Pick the right scale
    for threshold, divisor, suffix in spec.scales:
        if abs_value >= threshold:
            scaled = abs_value / divisor
            if decimals is None:
                decs = 0 if scaled >= 100 else 1
            else:
                decs = decimals
            fmt = f"{{:.{decs}f}}"
            return f"{sign}{spec.symbol}{fmt.format(scaled)}{suffix}"

    # Below the smallest scale — use minor format (e.g. "$582", "₹582")
    return sign + spec.minor_format.format(symbol=spec.symbol, value=abs_value)


# ─── Helpers used commonly across routes ─────────────────────────────────

def format_delta(
    value: Optional[float],
    currency: str = DEFAULT_CURRENCY,
) -> str:
    """Signed money delta — shorthand for `format_money(..., signed=True)`."""
    return format_money(value, currency, signed=True)


def format_rate(value: Optional[float], suffix: str = "x") -> str:
    """
    Non-currency ratio formatter used for ROI/ROAS-style values.
    Currency-independent, but lives here so routes have one place to import
    their display helpers from.

        format_rate(3.62)           → "3.62x"
        format_rate(None)           → "—"
        format_rate(10.3, "x")      → "10.30x"
    """
    if value is None or value == 0:
        return "—"
    return f"{float(value):.2f}{suffix}"


def format_count(value: Optional[float]) -> str:
    """
    Human-readable count formatter for conversions, impressions, etc.
    Currency-independent.

        format_count(98_300)       → "98K"
        format_count(1_450_000)    → "1.4M"
        format_count(None)         → "—"
    """
    if value is None or value == 0:
        return "—"
    v = float(value)
    if v >= 1e6: return f"{v/1e6:.1f}M"
    if v >= 1e3: return f"{v/1e3:.0f}K"
    return f"{int(v)}"
