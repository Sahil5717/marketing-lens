#!/usr/bin/env python3
"""
Fast Bayesian regression test — tight budget (6 channels, 200 draws × 2 chains).
Designed to stay under ~3 minutes so it can join the regression loop.

Larger exhaustive tests live in test_mmm_bayesian.py (4 chains, all channels,
slow) and are NOT in the regression loop.
"""
import sys
import time
import warnings

warnings.filterwarnings("ignore")

import numpy as np
from mock_data import generate_all_data
from engines.mmm import run_mmm

_pass = 0
_fail = 0


def assert_test(name, ok, detail=""):
    global _pass, _fail
    if ok:
        print(f"  PASS  {name}")
        _pass += 1
    else:
        print(f"  FAIL  {name}: {detail}")
        _fail += 1


# ── Setup ──
print("Generating mock data...")
data = generate_all_data()
df = data["campaign_performance"]
# Subset to the pitch channels — matches _bayes_subset_df in api.py
keep = ["paid_search", "social_paid", "tv_national", "events", "email", "direct_mail"]
df_small = df[df["channel"].isin(keep)].copy()

print(f"\n--- Running Bayesian fit (6 channels, 200 draws × 2 chains) ---")
t0 = time.time()
result = run_mmm(df_small, method="bayesian", n_draws=200, n_chains=2, n_tune=200)
elapsed = time.time() - t0
print(f"Fit completed in {elapsed:.1f}s\n")

# ── Tests ──

assert_test(
    "Result dict has the expected top-level keys",
    all(k in result for k in ("method", "contributions", "model_diagnostics")),
    f"keys={list(result.keys())}",
)

assert_test(
    "Method is bayesian_pymc",
    result.get("method") == "bayesian_pymc",
    f"method={result.get('method')}",
)

diag = result.get("model_diagnostics", {})
assert_test(
    "R² is reasonable (> 0.3 on mock data)",
    diag.get("r_squared", 0) > 0.3,
    f"r_squared={diag.get('r_squared')}",
)

assert_test(
    "Convergence diagnostics present (r_hat_max, ess_min)",
    "r_hat_max" in diag and "ess_min" in diag,
    f"diag_keys={list(diag.keys())}",
)

assert_test(
    "r_hat_max is finite",
    diag.get("r_hat_max") is not None and np.isfinite(diag["r_hat_max"]),
    f"r_hat_max={diag.get('r_hat_max')}",
)

# HDI structure
contribs = result.get("contributions", {})
assert_test(
    "Contribution dict has all 6 channels",
    set(contribs.keys()) == set(keep),
    f"got={set(contribs.keys())}, expected={set(keep)}",
)

sample_ch = list(contribs.keys())[0]
sample = contribs[sample_ch]

assert_test(
    "Each channel has mmm_roas_hdi_90 (new Week 4 field)",
    "mmm_roas_hdi_90" in sample,
    f"sample keys={list(sample.keys())}",
)

for ch, cc in contribs.items():
    hdi = cc.get("mmm_roas_hdi_90", [])
    if len(hdi) != 2:
        assert_test(f"{ch} has [low, high] ROAS HDI", False, f"hdi={hdi}")
        continue
    lo, hi = hdi
    point = cc.get("mmm_roas", 0)
    assert_test(
        f"{ch} ROAS HDI ordered correctly (low ≤ high)",
        lo <= hi,
        f"lo={lo}, hi={hi}",
    )
    assert_test(
        f"{ch} ROAS point estimate is inside or near HDI",
        # Point estimate uses posterior mean of betas while HDI uses marginal ROAS samples,
        # so strict containment isn't guaranteed. Allow ±20% tolerance.
        lo * 0.8 <= point <= hi * 1.2 + 0.01,
        f"point={point}, hdi=[{lo}, {hi}]",
    )

assert_test(
    "Each channel has contribution_hdi_90",
    all("contribution_hdi_90" in cc for cc in contribs.values()),
    "",
)

# Confidence tier
for ch, cc in contribs.items():
    conf = cc.get("confidence")
    assert_test(
        f"{ch} has a confidence tier (High/Medium/Low)",
        conf in ("High", "Medium", "Low"),
        f"confidence={conf}",
    )

# Response curve with HDI band
for ch, cc in contribs.items():
    curve = cc.get("response_curve")
    if not curve:
        assert_test(f"{ch} has response_curve", False, "missing")
        continue
    assert_test(
        f"{ch} response_curve has 30 points",
        len(curve) == 30,
        f"len={len(curve)}",
    )
    sample_pt = curve[len(curve) // 2]
    assert_test(
        f"{ch} curve point has spend, revenue, revenue_hdi_low/high",
        all(k in sample_pt for k in ("spend", "revenue", "revenue_hdi_low", "revenue_hdi_high")),
        f"keys={list(sample_pt.keys())}",
    )
    assert_test(
        f"{ch} curve HDI is ordered (low ≤ mid ≤ high)",
        all(p["revenue_hdi_low"] <= p["revenue"] <= p["revenue_hdi_high"] + 1 for p in curve),
        "some points violate ordering",
    )

# ── Wrap ──
print()
print("=" * 60)
print(f"  PASSED: {_pass}  |  FAILED: {_fail}  |  TOTAL: {_pass+_fail}")
print("=" * 60)

if _fail > 0:
    sys.exit(1)
