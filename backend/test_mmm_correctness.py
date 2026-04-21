"""
Statistical correctness tests for MMM engine.

These are the tests the original suite didn't have. They don't check that
endpoints return 200 — they check that the numbers the endpoints produce
are mathematically defensible. Each one is paired with the class of bug it
would catch.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
from mock_data import generate_all_data
from engines.mmm import (
    run_mmm,
    fit_ols_mmm,
    fit_mle_mmm,
    prepare_mmm_data,
    geometric_adstock,
    hill_saturation,
)

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
print("MMM STATISTICAL CORRECTNESS TESTS")
print("=" * 60)

# Seed for reproducibility -- mock_data uses randomness.
np.random.seed(42)
data = generate_all_data()
df = data["campaign_performance"]

print("\n--- Basic sanity on mock data ---")
mdata = prepare_mmm_data(df)
assert_test(
    "Mock data has 48 periods",
    mdata["n_periods"] == 48,
    f"got {mdata['n_periods']}",
)
assert_test(
    "Revenue is strictly positive",
    (mdata["revenue"] > 0).all(),
    f"min={mdata['revenue'].min()}",
)

print("\n--- OLS (NNLS) fit ---")
ols = fit_ols_mmm(mdata)
r2_ols = ols["model_diagnostics"]["r_squared"]
assert_test(
    "OLS R² is finite and >= 0 (would catch unbounded blow-ups)",
    np.isfinite(r2_ols) and r2_ols >= 0,
    f"R²={r2_ols}",
)
assert_test(
    "OLS R² <= 1.0 (would catch a broken r2_score wiring)",
    r2_ols <= 1.0,
    f"R²={r2_ols}",
)

ols_betas = [c["beta_mean"] for c in ols["contributions"].values()]
assert_test(
    "All OLS betas >= 0 (NNLS invariant — would catch reintroducing lstsq)",
    all(b >= 0 for b in ols_betas),
    f"min beta={min(ols_betas)}",
)

ols_total_contrib = sum(c["contribution"] for c in ols["contributions"].values())
ols_total_rev = ols["total_revenue"]
assert_test(
    "OLS media contribution <= total revenue (would catch the old 300%-of-revenue bug)",
    ols_total_contrib <= ols_total_rev * 1.01,
    f"media={ols_total_contrib/1e6:.0f}M rev={ols_total_rev/1e6:.0f}M",
)

print("\n--- MLE fit ---")
mle = fit_mle_mmm(mdata)
r2_mle = mle["model_diagnostics"]["r_squared"]
mape_mle = mle["model_diagnostics"]["mape"]

# The pre-fix MLE produced R² around -4e13. The raise-on-bad-fit guard should
# fire long before that, so any passing MLE here is already better than before.
assert_test(
    "MLE R² is in a sane range (would catch the 1e13 scale-mismatch bug)",
    -1.0 <= r2_mle <= 1.0,
    f"R²={r2_mle}",
)
assert_test(
    "MLE MAPE is bounded (would catch divergent fits)",
    mape_mle < 500,
    f"MAPE={mape_mle}%",
)

mle_fitted = np.array(mle["fitted_values"])
mle_actual = np.array(mle["actual_values"])
assert_test(
    "MLE fitted values have same order of magnitude as actuals",
    0.1 <= mle_fitted.mean() / max(mle_actual.mean(), 1) <= 10,
    f"fitted_mean={mle_fitted.mean():.2e} actual_mean={mle_actual.mean():.2e}",
)

mle_betas_dollar = [c["beta_mean"] for c in mle["contributions"].values()]
assert_test(
    "All MLE betas >= 0 (log-reparameterization invariant)",
    all(b >= 0 for b in mle_betas_dollar),
    f"min beta={min(mle_betas_dollar)}",
)

print("\n--- Auto chain + finalize ---")
# We test against method='mle' directly rather than 'auto'. The auto chain
# will try Bayesian first when PyMC is installed, and a Bayesian fit takes
# 2-5 minutes -- too slow for a CI-gating correctness suite. The behavior
# under test here is _finalize's accounting identities, which are the same
# regardless of which fit method produced the input.
result = run_mmm(df, method="mle")
baseline_pct = result["baseline_pct"]
media_pct = sum(c["contribution_pct"] for c in result["contributions"].values())

assert_test(
    "Baseline %% + media %% sums to ~100 (accounting identity)",
    abs((baseline_pct + media_pct) - 100) < 1.0,
    f"baseline={baseline_pct}% media={media_pct}% sum={baseline_pct + media_pct}%",
)
assert_test(
    "Baseline is nonnegative",
    baseline_pct >= 0,
    f"baseline={baseline_pct}%",
)
assert_test(
    "Media contribution is in realistic MMM range (40-85%%)",
    40 <= media_pct <= 85,
    f"media={media_pct}% — real MMM outputs typically fall in this band",
)

# Separately: verify _finalize still protects against pathological fits.
# We construct a fake result where media is 300% of revenue (like the old
# OLS bug used to produce) and check that _finalize clamps it.
from engines.mmm import _finalize as _mmm_finalize
fake_broken = {
    "contributions": {
        "ch_a": {"contribution": 100.0, "spend": 50.0, "_spend_scale": 10.0,
                 "beta_mean": 1.0, "decay_mean": 0.5, "half_saturation": 0.5},
        "ch_b": {"contribution": 200.0, "spend": 40.0, "_spend_scale": 10.0,
                 "beta_mean": 2.0, "decay_mean": 0.5, "half_saturation": 0.5},
    },
    "total_revenue": 100.0,  # media sums to 300 -- 300% of revenue
    "baseline_contribution": 0.0,
    "baseline_pct": 0.0,
    "model_diagnostics": {"r_squared": 0.5},
}
finalized = _mmm_finalize(fake_broken)
broken_media = sum(c["contribution"] for c in finalized["contributions"].values())
assert_test(
    "_finalize clamps pathological >100%% media fits (regression test for the old OLS bug)",
    broken_media <= 100.0 and finalized["model_diagnostics"].get("contribution_normalized"),
    f"broken_media={broken_media}, normalized_flag={finalized['model_diagnostics'].get('contribution_normalized')}",
)

# Incremental ROAS sanity: should NOT be identically zero for every channel,
# and saturation should NOT be 100% for every channel. This was the second
# bug I fixed (the unit mismatch in _finalize).
inc_roas = result["incremental_roas"]
sats = [v["saturation_pct"] for v in inc_roas.values()]
inc_vals = [v["incremental_roas"] for v in inc_roas.values()]
assert_test(
    "Incremental ROAS has variation (would catch the unit-mismatch bug)",
    len(set(sats)) > 1 and max(inc_vals) > 0,
    f"unique_sats={len(set(sats))} max_incR={max(inc_vals)}",
)
assert_test(
    "Not all channels reported at 100% saturation (same bug, different angle)",
    sum(1 for s in sats if s >= 99.5) < len(sats),
    f"{sum(1 for s in sats if s >= 99.5)}/{len(sats)} channels at 100%",
)

# Headroom classifications should be mixed, not all one value.
headrooms = [v["headroom"] for v in inc_roas.values()]
assert_test(
    "Headroom classifications are not all identical",
    len(set(headrooms)) >= 2,
    f"all headrooms were {set(headrooms)}",
)

print("\n--- Determinism (seeded) ---")
# Run twice with the same seed; the fitted R² should be stable. Again,
# we pin method='mle' to keep the suite fast and independent of PyMC.
np.random.seed(42)
data2 = generate_all_data()
result2 = run_mmm(data2["campaign_performance"], method="mle")
r2a = result["model_diagnostics"]["r_squared"]
r2b = result2["model_diagnostics"]["r_squared"]
# We don't demand bit-identical — mock_data reseeds inside — but outputs
# should at least be in the same ballpark run-to-run.
assert_test(
    "R² is stable within a reasonable range across runs",
    abs(r2a - r2b) < 0.3,
    f"run1={r2a} run2={r2b}",
)

# Bayesian correctness is tested separately in test_mmm_bayesian.py because
# a full PyMC fit takes 1-3 minutes — too slow for a CI-gating correctness
# suite that should finish in seconds.

print("\n" + "=" * 60)
print(f"  PASSED: {passed}  |  FAILED: {failed}  |  TOTAL: {passed + failed}")
print("=" * 60)
if errors:
    print("\nFailures:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
print("  ALL CORRECTNESS TESTS PASS")
