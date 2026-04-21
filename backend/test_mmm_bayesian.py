"""
Bayesian MMM tests — slow, opt-in.

Run: cd backend && python test_mmm_bayesian.py

These tests exercise the PyMC NUTS fit end-to-end. A single small fit
(200 tune, 200 draws, 2 chains) takes ~60-90 seconds on a dev laptop,
which is why they live in their own file instead of the core correctness
suite. Only run this file when PyMC is installed and you have the time.

If PyMC is not installed, this script exits cleanly with a message.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

try:
    import pymc  # noqa: F401
except ImportError:
    print("PyMC not installed. Skipping Bayesian tests.")
    print("Install with: pip install pymc arviz")
    sys.exit(0)

import numpy as np

from mock_data import generate_all_data
from engines.mmm import fit_bayesian_mmm, prepare_mmm_data, run_mmm


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
print("MMM BAYESIAN TESTS")
print("=" * 60)
print("Note: A small Bayesian fit takes ~60-90 seconds.\n")

np.random.seed(42)
data = generate_all_data()
mdata = prepare_mmm_data(data["campaign_performance"])

print("--- Small Bayesian fit (200 tune, 200 draws, 2 chains) ---")
t0 = time.time()
bayes = fit_bayesian_mmm(
    mdata, n_draws=200, n_tune=200, n_chains=2, target_accept=0.95
)
elapsed = time.time() - t0
print(f"  Fit completed in {elapsed:.1f}s")

d = bayes["model_diagnostics"]
print(f"  R²={d['r_squared']}, MAPE={d['mape']}%")
print(f"  r-hat max={d['r_hat_max']}, ESS min={d['ess_min']}, converged={d['converged']}")
print()

# --- Mechanical correctness ---

assert_test(
    "Bayesian completes and reports r-hat diagnostic",
    "r_hat_max" in d and np.isfinite(d["r_hat_max"]),
    f"diagnostics={d}",
)

assert_test(
    "Bayesian reports ESS diagnostic",
    "ess_min" in d and np.isfinite(d["ess_min"]),
    f"ess_min={d.get('ess_min')}",
)

assert_test(
    "Fitted values are in revenue units, not scaled space",
    0.1 <= np.mean(bayes["fitted_values"]) / max(np.mean(bayes["actual_values"]), 1) <= 10,
    f"mean_fit={np.mean(bayes['fitted_values']):.2e} mean_actual={np.mean(bayes['actual_values']):.2e}",
)

assert_test(
    "All betas non-negative (HalfNormal prior invariant — would catch re-broken unscaling)",
    all(c["beta_mean"] >= 0 for c in bayes["contributions"].values()),
    f"found negative beta: {[c['beta_mean'] for c in bayes['contributions'].values() if c['beta_mean'] < 0]}",
)

assert_test(
    "All contributions non-negative",
    all(c["contribution"] >= 0 for c in bayes["contributions"].values()),
    "found negative contribution",
)

assert_test(
    "All channels report HDI intervals of length 2",
    all(len(c.get("beta_hdi_90", [])) == 2 for c in bayes["contributions"].values()),
    "missing or malformed HDI intervals",
)

assert_test(
    "HDI intervals are ordered (low <= high)",
    all(c["beta_hdi_90"][0] <= c["beta_hdi_90"][1] for c in bayes["contributions"].values()),
    "found HDI with lower > upper",
)

assert_test(
    "Baseline contribution is non-negative",
    bayes["baseline_contribution"] >= 0,
    f"baseline={bayes['baseline_contribution']}",
)

# Accounting identity: reported baseline + reported media = reported total revenue
total_media = sum(c["contribution"] for c in bayes["contributions"].values())
total_reported = bayes["baseline_contribution"] + total_media
assert_test(
    "Baseline + media contribution == total revenue (accounting identity)",
    abs(total_reported - bayes["total_revenue"]) / max(bayes["total_revenue"], 1) < 0.01,
    f"baseline={bayes['baseline_contribution']:.0f} media={total_media:.0f} "
    f"sum={total_reported:.0f} rev={bayes['total_revenue']:.0f}",
)

assert_test(
    "R² is finite and bounded above by 1",
    np.isfinite(d["r_squared"]) and d["r_squared"] <= 1.0,
    f"R²={d['r_squared']}",
)

# --- Auto-chain integration ---
print("\n--- Auto-chain routes convergent Bayesian correctly ---")
# With the scaled-space model we now ship, a 500-draw 4-chain fit at
# target_accept=0.95 converges on the mock data. The auto chain should
# accept it.
print("  Running run_mmm(method='auto') — this invokes a full Bayesian fit")
print("  (~2-3 min). Skipping this block if we're short on time.")

# Behind an env-var gate so a user can skip the longest test.
if os.environ.get("SKIP_AUTO_CHAIN_TEST") == "1":
    print("  SKIPPED (SKIP_AUTO_CHAIN_TEST=1)")
else:
    t0 = time.time()
    auto = run_mmm(data["campaign_performance"], method="auto")
    elapsed = time.time() - t0
    print(f"  run_mmm(auto) completed in {elapsed:.1f}s")
    print(f"  Method selected: {auto['method']}")

    # The auto chain may legitimately pick Bayesian OR MLE depending on
    # whether the Bayesian converges on that particular mock data sample.
    # What we require: whatever it picks, the diagnostics should match it.
    assert_test(
        "Auto chain selects a valid method",
        auto["method"] in ("bayesian_pymc", "mle_scipy", "ols_nnls_bootstrap"),
        f"unexpected method: {auto['method']}",
    )

    if auto["method"] == "bayesian_pymc":
        assert_test(
            "Auto chain only accepts Bayesian when it converged",
            auto["model_diagnostics"].get("converged") is True,
            f"Bayesian was selected but converged={auto['model_diagnostics'].get('converged')}",
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
print("  ALL BAYESIAN TESTS PASS")
