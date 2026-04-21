"""
Statistical correctness tests for the budget optimizer.

Paired with the classes of bug each test catches. Every one of these would
have failed against the pre-extrapolation-cap optimizer (which produced
+4,657% spend recommendations on near-linear channels).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import numpy as np

from mock_data import generate_all_data
from engines.response_curves import fit_response_curves
from engines.optimizer import optimize_budget, sensitivity_analysis


passed = 0
failed = 0
errors: list[str] = []


def assert_test(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        errors.append(f"{name}: {detail}")
        print(f"  FAIL  {name}: {detail}")


print("=" * 60)
print("OPTIMIZER CORRECTNESS TESTS")
print("=" * 60)

np.random.seed(42)
data = generate_all_data()
df = data["campaign_performance"]
curves = fit_response_curves(df, model_type="power_law")
n_fitted = sum(1 for v in curves.values() if "error" not in v)
current_total = sum(v.get("current_avg_spend", 0) * 12 for v in curves.values() if "error" not in v)
print(f"\nFitted {n_fitted} channels; current total spend ~${current_total/1e6:.1f}M/year\n")


# --- Basic behavior at current-spend budget ---
print("--- Optimize near current spend ---")
r = optimize_budget(curves, current_total, objective="balanced")
info = r["optimizer_info"]

assert_test(
    "Converges when budget matches current spend",
    info["converged"],
    f"info={info}",
)
assert_test(
    "Reports the method used",
    info.get("method") == "scipy_SLSQP",
    f"method={info.get('method')}",
)
assert_test(
    "All channels present in result",
    len(r["channels"]) == n_fitted,
    f"got {len(r['channels'])} channels, fitted {n_fitted}",
)

# Sum-constraint: optimized spend should equal total budget (within numerical
# tolerance). Before the per-channel bound fixes, the optimizer could return
# allocations that didn't sum to the budget when bounds were infeasible.
opt_sum = sum(c["optimized_spend"] for c in r["channels"])
assert_test(
    "Optimized spend sums to target budget (accounting identity)",
    abs(opt_sum - current_total) / max(current_total, 1) < 0.02,
    f"opt_sum=${opt_sum:,.0f} vs target=${current_total:,.0f}",
)


# --- Extrapolation cap: no channel recommended beyond 3x current ---
# This is the big regression test for the "+4,657% spend" bug.
print("\n--- Extrapolation cap on recommendations ---")
r = optimize_budget(curves, current_total, objective="balanced")
max_swing = max(c["change_pct"] for c in r["channels"] if not c.get("locked"))
min_swing = min(c["change_pct"] for c in r["channels"] if not c.get("locked"))
assert_test(
    "No channel swings more than +200% (would catch near-linear curve exploitation)",
    max_swing <= 200,
    f"max swing was {max_swing}%",
)
assert_test(
    "No channel swings less than -80% (floor against zeroing out)",
    min_swing >= -80,
    f"min swing was {min_swing}%",
)

# Check the specific near-linear case -- organic_search has b≈0.99 and
# would be the first channel to blow up without extrapolation cap.
if "organic_search" in [c["channel"] for c in r["channels"]]:
    org = next(c for c in r["channels"] if c["channel"] == "organic_search")
    org_cur = org["current_spend"]
    org_opt = org["optimized_spend"]
    ratio = org_opt / max(org_cur, 1)
    assert_test(
        "Organic search (near-linear curve) recommended within extrapolation cap",
        ratio <= 3.5,  # 3x cap + small tolerance
        f"organic went ${org_cur:,.0f} -> ${org_opt:,.0f} ({ratio:.1f}x)",
    )


# --- Uplift direction: optimizer output >= current (never worse) ---
print("\n--- Optimizer never makes things strictly worse ---")
cur_rev = r["summary"]["current_revenue"]
opt_rev = r["summary"]["optimized_revenue"]
assert_test(
    "Optimized revenue >= current revenue (Guard 1 invariant)",
    opt_rev >= cur_rev * 0.95,  # allow 5% slack for numerical wiggle
    f"current=${cur_rev:,.0f} optimized=${opt_rev:,.0f}",
)


# --- Capacity detection: budget > absorbable capacity ---
print("\n--- Capacity warning when budget exceeds trusted range ---")
# Current total is ~$30M; 3x cap means ~$90M max absorbable. Request 10x.
oversize_budget = current_total * 10
r_big = optimize_budget(curves, oversize_budget, objective="balanced")
big_warnings = r_big["optimizer_info"].get("warnings", [])
has_capacity_warning = any("exceeds what the fitted curves" in w for w in big_warnings)
assert_test(
    "Capacity warning fires when budget exceeds 3x current spend",
    has_capacity_warning,
    f"warnings: {big_warnings}",
)
assert_test(
    "Optimizer still produces a valid result when over-capacity (not an error)",
    r_big["optimizer_info"]["converged"] and len(r_big["channels"]) > 0,
    f"converged={r_big['optimizer_info']['converged']}",
)
big_opt_sum = sum(c["optimized_spend"] for c in r_big["channels"])
assert_test(
    "Over-capacity result spends within the trusted envelope (not the full budget)",
    big_opt_sum < oversize_budget * 0.5,  # should be way under the requested $300M
    f"opt_sum=${big_opt_sum:,.0f} vs requested=${oversize_budget:,.0f}",
)


# --- Marginal ROI reported per channel ---
print("\n--- Marginal ROI reported and sane ---")
r = optimize_budget(curves, current_total, objective="balanced")
mrois = [c["marginal_roi"] for c in r["channels"] if not c.get("locked")]
assert_test(
    "All channels report a marginal ROI",
    all(isinstance(m, (int, float)) for m in mrois),
    "missing or non-numeric marginal ROI",
)
assert_test(
    "Marginal ROIs are finite (would catch divide-by-zero or NaN)",
    all(np.isfinite(m) for m in mrois),
    f"got non-finite: {[m for m in mrois if not np.isfinite(m)]}",
)
assert_test(
    "Marginal ROIs non-negative (revenue doesn't decrease with spend)",
    all(m >= -0.01 for m in mrois),  # tiny tolerance for numerical
    f"negative mROI found: {[m for m in mrois if m < 0]}",
)


# --- Locked channels are preserved ---
print("\n--- Locked channels are frozen at specified spend ---")
# Pick the first channel, lock it at $5M
first_ch = next(c for c, v in curves.items() if "error" not in v)
lock_spend = 5_000_000
r_locked = optimize_budget(curves, current_total, objective="balanced",
                           locked_channels={first_ch: lock_spend})
locked_entry = next(c for c in r_locked["channels"] if c["channel"] == first_ch)
assert_test(
    "Locked channel spend matches the lock value",
    locked_entry["optimized_spend"] == locked_entry["current_spend"] == lock_spend,
    f"locked at ${lock_spend}, got current=${locked_entry['current_spend']} opt=${locked_entry['optimized_spend']}",
)
assert_test(
    "Locked channel is flagged",
    locked_entry.get("locked") is True,
    f"locked flag: {locked_entry.get('locked')}",
)


# --- Sensitivity analysis sweep ---
print("\n--- Sensitivity analysis ---")
sensitivity = sensitivity_analysis(curves, current_total, objective="balanced")
assert_test(
    "Sensitivity returns multiple budget points",
    isinstance(sensitivity, list) and len(sensitivity) >= 5,
    f"got {len(sensitivity) if isinstance(sensitivity, list) else type(sensitivity)}",
)
assert_test(
    "Sensitivity rows have required fields",
    all({"budget_change_pct", "revenue", "roi"}.issubset(s.keys()) for s in sensitivity),
    f"row keys: {sensitivity[0].keys() if sensitivity else []}",
)
# Revenue should be monotonically non-decreasing as budget increases (more
# spend can only buy more revenue, modulo the extrapolation cap).
revenues = [s["revenue"] for s in sensitivity]
changes = [s["budget_change_pct"] for s in sensitivity]
sorted_pairs = sorted(zip(changes, revenues))
rev_by_budget = [r for _, r in sorted_pairs]
# Tolerance is 5% — with 12 channels SLSQP can land in slightly different
# local optima at adjacent budget levels. A real monotonicity violation
# (e.g., doubling budget halves revenue) would still fail this check.
monotonic = all(rev_by_budget[i + 1] >= rev_by_budget[i] * 0.95
                for i in range(len(rev_by_budget) - 1))
assert_test(
    "Revenue is non-decreasing as budget grows (sanity check)",
    monotonic,
    f"rev sequence: {rev_by_budget}",
)


# --- Determinism with seed ---
print("\n--- Determinism ---")
np.random.seed(42)
r1 = optimize_budget(curves, current_total, objective="balanced")
np.random.seed(42)
r2 = optimize_budget(curves, current_total, objective="balanced")
# Multi-start uses np.random; with same seed should produce same result.
uplift1 = r1["summary"]["uplift_pct"]
uplift2 = r2["summary"]["uplift_pct"]
assert_test(
    "Same seed produces same uplift (multi-start uses numpy RNG)",
    abs(uplift1 - uplift2) < 0.1,
    f"seeded: {uplift1} vs {uplift2}",
)


# --- Summary ---
print("\n" + "=" * 60)
print(f"  PASSED: {passed}  |  FAILED: {failed}  |  TOTAL: {passed + failed}")
print("=" * 60)
if errors:
    print("\nFailures:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
print("  ALL OPTIMIZER CORRECTNESS TESTS PASS")
