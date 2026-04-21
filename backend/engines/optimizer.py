"""
Budget Optimization Engine — Production Grade
===============================================
Constrained nonlinear optimization via scipy.optimize.minimize (SLSQP).
Supports: maximize_revenue, maximize_roi, minimize_cac, balanced multi-objective.
Multi-start to escape local optima. Sensitivity analysis built in.

Libraries: scipy.optimize.minimize (SLSQP), numpy
"""
import numpy as np
from scipy.optimize import minimize
from typing import Dict, List, Optional
import logging
logger = logging.getLogger(__name__)

# How far outside the observed spend range we'll trust the fitted response curve.
# If current avg spend is $100K/month, we evaluate the curve up to $300K/month
# (3x) and beyond that we clamp to the value at the cap. This prevents the
# classic MMM bug where a near-linear fit (b -> 1.0) extrapolated to 10x the
# observed range produces absurd revenue predictions -- e.g. organic search
# with b=0.99 has an analytical saturation point at ~10^158 and the optimizer
# rationally pours all budget into it. Real MMM engagements always bound the
# trusted extrapolation range.
DEFAULT_EXTRAPOLATION_CAP = 3.0


def _predict_revenue(spend_annual, curve, extrapolation_cap=DEFAULT_EXTRAPOLATION_CAP):
    """Predict annual revenue from annual spend using fitted response curve.

    Spend is clamped at `extrapolation_cap * current_avg_spend_annual`. Beyond
    that, the curve returns the revenue value at the cap -- i.e. we assume
    zero marginal return past the trusted range. This is conservative and
    defensible; the alternative (blind extrapolation) drives real MMM
    disasters.
    """
    current_monthly = curve.get("current_avg_spend", 0)
    current_annual = current_monthly * 12
    cap_annual = max(current_annual * extrapolation_cap, 1000.0)  # at least $1k/yr
    effective_spend = min(spend_annual, cap_annual)

    monthly = effective_spend / 12
    if curve.get("model") == "hill":
        a, b, K = curve["params"]["a"], curve["params"]["b"], curve["params"]["K"]
        xb = np.power(max(monthly, 1e-6), b)
        return float(a * xb / (np.power(K, b) + xb)) * 12
    else:  # power_law
        a, b = curve["params"]["a"], curve["params"]["b"]
        return float(a * np.power(max(monthly, 1e-6), b)) * 12


def _marginal_revenue(spend_annual, curve, extrapolation_cap=DEFAULT_EXTRAPOLATION_CAP):
    """Marginal revenue (derivative) at given spend level.

    Outside the trusted extrapolation range, marginal revenue is 0 -- we
    refuse to say anything about return on additional spend beyond the
    cap. This is what drives the optimizer to back off rather than
    recommending infinite spend on near-linear channels.
    """
    current_monthly = curve.get("current_avg_spend", 0)
    current_annual = current_monthly * 12
    cap_annual = max(current_annual * extrapolation_cap, 1000.0)
    if spend_annual > cap_annual:
        return 0.0

    monthly = spend_annual / 12
    if curve.get("model") == "hill":
        a, b, K = curve["params"]["a"], curve["params"]["b"], curve["params"]["K"]
        Kb = K**b; xb = monthly**b
        return float(a * b * (monthly**(b-1)) * Kb / ((Kb + xb)**2))
    else:
        a, b = curve["params"]["a"], curve["params"]["b"]
        return float(a * b * np.power(max(monthly, 1e-6), b - 1))

def _build_capacity_bound_result(
    response_curves, channels, current_allocation, bounds,
    total_budget, capacity_warning
):
    """Short-circuit result for the over-capacity case.

    When requested budget > sum of per-channel 3x caps, the feasible region
    collapses to "every channel at its upper bound." Rather than ask SLSQP
    to rediscover this (it fails with singular-hessian errors when nearly
    every bound is active), return the allocation directly.

    The per-channel answer is: spend up to the upper bound. Total spend is
    the sum of those bounds — which is *less* than what the caller
    requested, but that's the honest answer: we don't know what happens
    beyond the trusted range.
    """
    channel_results = []
    total_rev = 0.0
    total_opt_spend = 0.0
    for i, ch in enumerate(channels):
        cur = current_allocation.get(ch, 0)
        hi = bounds[i][1]
        opt = hi  # Max out every channel
        opt_rev = _predict_revenue(opt, response_curves[ch])
        cur_rev = _predict_revenue(cur, response_curves[ch])
        channel_results.append({
            "channel": ch,
            "current_spend": round(cur, 0),
            "optimized_spend": round(opt, 0),
            "change_pct": round((opt - cur) / max(cur, 1) * 100, 1),
            "current_revenue": round(cur_rev, 0),
            "optimized_revenue": round(opt_rev, 0),
            "revenue_delta": round(opt_rev - cur_rev, 0),
            "current_roi": round((cur_rev - cur) / max(cur, 1), 3),
            "optimized_roi": round((opt_rev - opt) / max(opt, 1), 3),
            "marginal_roi": 0,
            "locked": False,
            "at_extrapolation_cap": True,
        })
        total_rev += opt_rev
        total_opt_spend += opt

    current_total = sum(c["current_revenue"] for c in channel_results)
    return {
        "channels": channel_results,
        "summary": {
            "total_budget": total_budget,
            "current_revenue": current_total,
            "optimized_revenue": total_rev,
            "revenue_uplift": round(total_rev - current_total, 0),
            "uplift_pct": round((total_rev - current_total) / max(current_total, 1) * 100, 2),
            "current_roi": round((current_total - sum(c["current_spend"] for c in channel_results)) / max(sum(c["current_spend"] for c in channel_results), 1), 3),
            "optimized_roi": round((total_rev - total_opt_spend) / max(total_opt_spend, 1), 3),
        },
        "optimizer_info": {
            "converged": True,
            "warning": capacity_warning,
            "warnings": [capacity_warning],
            "mode": "capacity_bound",
        },
    }


def _get_channel_constraints(channel_name: str, attribution_basis: str = "click"):
    """
    Per-channel execution constraints — how fast this channel can flex
    budget, what minimum buy is feasible, etc. Real offline media has
    structural constraints digital doesn't:

      - TV networks sell in weekly/monthly commitments with 4-8 week lead
        times. Shifting $X into TV next quarter is realistic; shifting
        next month is not.
      - Radio has 2-3 week lead time on ad placement, smaller minimum buys
      - OOH has 6-8 week lead time for new creative, ~4 weeks for rotating
        existing inventory
      - Call center is operational — lead time is weeks not months but
        throughput is capped by headcount
      - Digital channels can flex spend in days

    Returns a dict with:
      - swing_cap: max fractional change in one optimization step.
        0.5 means the channel can move between 50% and 150% of current.
      - lead_time_weeks: how long before a new allocation can be executed
      - min_annual_floor: hard floor — don't recommend going below this
    """
    # Broadcast offline — slowest to flex, largest minimum buys
    if channel_name == "tv_national":
        return {"swing_cap": 0.35, "lead_time_weeks": 8, "min_annual_floor": 500_000}
    if channel_name == "radio":
        return {"swing_cap": 0.45, "lead_time_weeks": 3, "min_annual_floor": 120_000}
    if channel_name == "ooh":
        return {"swing_cap": 0.40, "lead_time_weeks": 6, "min_annual_floor": 200_000}
    # Direct-response offline — moderate flexibility
    if channel_name == "events":
        return {"swing_cap": 0.30, "lead_time_weeks": 12, "min_annual_floor": 250_000}
    if channel_name == "direct_mail":
        return {"swing_cap": 0.50, "lead_time_weeks": 4, "min_annual_floor": 50_000}
    if channel_name == "call_center":
        return {"swing_cap": 0.40, "lead_time_weeks": 6, "min_annual_floor": 100_000}
    # Digital — flexible by design
    return {"swing_cap": None, "lead_time_weeks": 1, "min_annual_floor": None}


def optimize_budget(
    response_curves: Dict,
    total_budget: float,
    objective: str = "balanced",
    objective_weights: Optional[Dict] = None,
    min_spend_pct: float = 0.02,
    max_spend_pct: float = 0.40,
    locked_channels: Optional[Dict] = None,
    current_allocation: Optional[Dict] = None,
    n_restarts: int = 5,
    max_channel_change_pct: float = 0.75,
    extrapolation_cap: float = DEFAULT_EXTRAPOLATION_CAP,
) -> Dict:
    """
    Constrained budget optimization using scipy SLSQP solver with multi-start.

    Args:
        response_curves: from response_curves engine (fitted params per channel)
        total_budget: total annual budget
        objective: maximize_revenue | maximize_roi | minimize_cac | balanced
        locked_channels: {channel: fixed_spend}
        n_restarts: number of random starting points to escape local optima
        max_channel_change_pct: cap on how much a single channel can move from
            its current allocation in one optimization step. 0.75 = channel
            may move between 25% and 175% of current. Real CMOs rarely swing
            a channel budget past ±50% in a quarter; this protects against
            the optimizer exploiting an overfit response curve to recommend
            a 10x reallocation.
        extrapolation_cap: how far outside observed spend range to trust the
            fitted curve. 3.0 means the curve is evaluated up to 3x
            current average spend, then clamped.
    """
    locked = locked_channels or {}
    channels = [ch for ch in response_curves if ch not in locked and "error" not in response_curves[ch]]
    n = len(channels)
    if n == 0: return {"channels":[], "summary":{"total_budget":total_budget,"current_revenue":0,"optimized_revenue":0,"revenue_uplift":0,"uplift_pct":0,"current_roi":0,"optimized_roi":0}, "optimizer_info":{"converged":False,"warning":"No optimizable channels"}}

    locked_total = sum(locked.values())
    avail = total_budget - locked_total
    if avail <= 0: return {"channels":[], "summary":{"total_budget":total_budget,"current_revenue":0,"optimized_revenue":0,"revenue_uplift":0,"uplift_pct":0,"current_roi":0,"optimized_roi":0}, "optimizer_info":{"converged":False,"warning":"Locked spend exceeds budget"}}

    if current_allocation is None:
        current_allocation = {ch: response_curves[ch].get("current_avg_spend", avail/n/12)*12 for ch in channels}
    if objective_weights is None:
        objective_weights = {"revenue": 0.4, "roi": 0.3, "leakage": 0.15, "cost": 0.15}

    # Objective function (minimize negative objective).
    # Pass extrapolation_cap through to _predict_revenue / _marginal_revenue.
    def neg_objective(x):
        total_rev = sum(
            _predict_revenue(x[i], response_curves[channels[i]], extrapolation_cap)
            for i in range(n)
        )
        total_sp = sum(x)
        if objective == "maximize_revenue":
            return -total_rev
        elif objective == "maximize_roi":
            return -(total_rev - total_sp) / max(total_sp, 1)
        elif objective == "minimize_cac":
            # Approximate conversions from revenue / avg_order_value
            return total_sp / max(total_rev / 400, 1)  # rough CAC
        else:  # balanced
            roi = (total_rev - total_sp) / max(total_sp, 1)
            return -(objective_weights.get("revenue",0.4) * total_rev / 1e6
                   + objective_weights.get("roi",0.3) * roi * 10)

    # If the requested budget is much larger than current spend, the
    # "don't swing any channel more than ±75%" rule is the wrong one --
    # the user is asking where to deploy net-new budget, not how to
    # reallocate existing budget. Scale the per-channel swing cap up
    # proportionally to the budget-to-current-spend ratio, clipped so
    # the cap never drops below 0.5 (allowing at least 50% swing).
    current_total = sum(current_allocation.values())
    budget_expansion = avail / max(current_total, 1.0)
    if budget_expansion > 1.2:
        effective_swing_cap = max_channel_change_pct * budget_expansion
        if effective_swing_cap != max_channel_change_pct:
            logger.info(
                f"Budget is {budget_expansion:.1f}x current spend; relaxing "
                f"swing cap from {max_channel_change_pct:.2f} to {effective_swing_cap:.2f}"
            )
    else:
        effective_swing_cap = max_channel_change_pct

    # Per-channel bounds: combine global floor/ceiling with per-channel
    # swing limit AND extrapolation cap.
    #
    # The extrapolation cap matters as an upper bound because _predict_revenue
    # returns a constant value past the cap (marginal revenue = 0). If we let
    # SLSQP explore into that region, the objective function has a flat gradient
    # there, which SLSQP interprets as a convergence failure ("Positive
    # directional derivative for linesearch" — there's no descent direction).
    # Clipping the upper bound to the extrapolation cap keeps SLSQP in the
    # region where the objective function is actually differentiable and
    # informative.
    #
    # Subtle point on the floor: min_spend_pct is a FLOOR below which we
    # don't want the optimizer to zero out a channel -- but if a channel's
    # current spend is already smaller than that floor, we shouldn't force
    # it up just because the total budget is large. The floor is "don't
    # go below what you're currently spending, or min_spend_pct if you
    # don't have a current number", NOT "spend at least min_spend_pct".
    bounds = []
    per_channel_constraints = {}  # accumulated for the result payload
    for i, ch in enumerate(channels):
        cur = current_allocation.get(ch, avail / n)

        # Per-channel overrides for offline media.
        # The attribution_basis is attached to each curve by the response-
        # curve engine; fall back gracefully if absent.
        ch_curve = response_curves.get(ch, {}) or {}
        ch_basis = ch_curve.get("attribution_basis", "click")
        ch_constraints = _get_channel_constraints(ch, ch_basis)
        per_channel_constraints[ch] = ch_constraints

        # Offline channels get a tighter swing cap (their lead times and
        # contractual buys mean they can't flex as fast as digital)
        channel_swing_cap = ch_constraints["swing_cap"]
        if channel_swing_cap is not None:
            this_swing = channel_swing_cap
        else:
            this_swing = effective_swing_cap

        global_min = avail * min_spend_pct
        global_max = avail * max_spend_pct
        # Floor: normally the smaller of global_min and a tight fraction of
        # current, to avoid locking a cheap channel at an artificially-high
        # floor. BUT for channels with a per-channel swing cap (offline
        # media — TV, radio, etc.), we respect that cap on both sides:
        # the channel can't move down more than `this_swing` in one step.
        # Without this, global_min dominates and the optimizer can zero
        # out a TV buy that the contract says you owe $10M on.
        has_per_channel_swing = channel_swing_cap is not None
        if has_per_channel_swing:
            floor = cur * (1.0 - this_swing)
        else:
            floor = min(global_min, cur * (1.0 - this_swing))
        floor = max(floor, 1000.0)  # hard minimum of $1k/yr
        # For offline channels, enforce the min_annual_floor — media-buy
        # minimums. You can't contract TV for less than the network's
        # weekly minimum × 52.
        if ch_constraints["min_annual_floor"] is not None and cur > 0:
            # Only raise the floor if current spend already exceeds it —
            # we don't want to force NEW spend on a channel that's currently
            # at $0. But if we're running it at $10M, the floor should
            # reflect what the seller will contract for.
            if cur >= ch_constraints["min_annual_floor"]:
                floor = max(floor, ch_constraints["min_annual_floor"])
        # Ceiling: min of three caps -- global, swing, extrapolation.
        swing_max = cur * (1.0 + this_swing)
        extrapolation_max = cur * extrapolation_cap  # same cap _predict_revenue uses
        hi = min(global_max, swing_max, extrapolation_max)
        if hi <= floor:
            # Degenerate: fall back to a tight range around current.
            floor = cur * 0.5
            hi = cur * 2.0
        bounds.append((floor, hi))

    # Sanity check: can the channels absorb the total budget within bounds?
    # If max absorbable capacity is less than the target budget, we tell the
    # user explicitly instead of letting SLSQP fail cryptically. The
    # optimizer will still run -- on min(budget, max_absorbable) -- so the
    # caller gets a useful answer rather than an error.
    max_absorbable = sum(b[1] for b in bounds)
    min_required = sum(b[0] for b in bounds)
    capacity_warning = None
    if avail > max_absorbable:
        capacity_warning = (
            f"Requested budget (${avail:,.0f}) exceeds what the fitted curves "
            f"can trustworthily absorb (${max_absorbable:,.0f} at 3x current spend "
            f"per channel). Optimizing against capacity, not full budget. "
            f"Beyond-capacity spend has no predicted return — a larger sample of "
            f"historical data at higher spend levels is needed before extrapolating."
        )
        logger.warning(capacity_warning)
        # When avail > max_absorbable, the feasible region collapses to
        # essentially "every channel at its upper bound." SLSQP struggles
        # with this (singular hessian, pinned bounds), so short-circuit:
        # return the upper-bound allocation directly. This is still an
        # "optimal" answer — there's nowhere else to put the budget within
        # the extrapolation-safe envelope.
        return _build_capacity_bound_result(
            response_curves, channels, current_allocation, bounds,
            total_budget, capacity_warning
        )
    elif avail < min_required:
        capacity_warning = (
            f"Requested budget (${avail:,.0f}) is below the sum of per-channel "
            f"floors (${min_required:,.0f}). Raising budget to meet floors."
        )
        logger.warning(capacity_warning)
        avail = min_required * 1.02

    constraints = [{"type": "eq", "fun": lambda x: sum(x) - avail}]

    # Multi-start optimization.
    # Starting points are clipped into per-channel bounds so SLSQP always
    # starts feasibly. If the intersection of [lo, hi] bounds and the sum
    # constraint leaves no feasible point (can happen when all global_mins
    # sum to more than avail), we fall back to equal allocation.
    lo_arr = np.array([b[0] for b in bounds])
    hi_arr = np.array([b[1] for b in bounds])
    min_sum = lo_arr.sum()
    max_sum = hi_arr.sum()

    best_result = None; best_obj = float("inf")
    for restart in range(n_restarts):
        if restart == 0:
            x0 = np.array([current_allocation.get(ch, avail/n) for ch in channels])
            if x0.sum() > 0:
                x0 = x0 * (avail / x0.sum())
            else:
                x0 = np.full(n, avail / n)
        else:
            x0 = np.random.dirichlet(np.ones(n)) * avail

        # Clip to per-channel bounds, then renormalize to hit sum=avail.
        x0 = np.clip(x0, lo_arr, hi_arr)
        if min_sum <= avail <= max_sum and x0.sum() > 0:
            # Scale-and-project: scale to match avail, then re-clip, repeat
            # a few times until feasible. This is a simple iterative fix
            # that handles the common case without needing an LP.
            for _ in range(5):
                if abs(x0.sum() - avail) < 1e-6:
                    break
                x0 = x0 * (avail / x0.sum())
                x0 = np.clip(x0, lo_arr, hi_arr)
        else:
            # Bounds incompatible with budget constraint; SLSQP will relax
            # via the equality constraint, but warn the caller.
            x0 = np.clip(x0 * (avail / max(x0.sum(), 1e-9)), lo_arr, hi_arr)

        try:
            res = minimize(neg_objective, x0, method="SLSQP", bounds=bounds,
                          constraints=constraints, options={"maxiter": 500, "ftol": 1e-10})
            if res.fun < best_obj:
                best_obj = res.fun; best_result = res
        except Exception as e:
            logger.warning(f"Restart {restart} failed: {e}")

    # If SLSQP failed across all restarts, retry with trust-constr which
    # handles degenerate cases (singular hessian, near-boundary solutions)
    # better. Trust-constr is slower but more robust for 12+ channels.
    if best_result is None or not best_result.success:
        logger.info("SLSQP failed across restarts; retrying with trust-constr")
        try:
            x0_fallback = np.array([current_allocation.get(ch, avail/n) for ch in channels])
            if x0_fallback.sum() > 0:
                x0_fallback = x0_fallback * (avail / x0_fallback.sum())
            x0_fallback = np.clip(x0_fallback, lo_arr, hi_arr)
            # Re-project onto the sum constraint
            if abs(x0_fallback.sum() - avail) > 1e-3:
                x0_fallback = x0_fallback * (avail / max(x0_fallback.sum(), 1e-9))
                x0_fallback = np.clip(x0_fallback, lo_arr, hi_arr)
            res_tc = minimize(neg_objective, x0_fallback, method="trust-constr",
                              bounds=bounds, constraints=constraints,
                              options={"maxiter": 300, "xtol": 1e-8})
            if res_tc.fun < best_obj and res_tc.success:
                best_obj = res_tc.fun
                best_result = res_tc
        except Exception as e:
            logger.warning(f"trust-constr fallback also failed: {e}")

    if best_result is None or not best_result.success:
        logger.warning(f"Optimization did not converge: {best_result}")
        # Smarter fallback: proportionally scale current allocation to
        # hit the requested budget. This respects the constraint and
        # is a better answer than "return current unchanged" — if the
        # user asked for more budget, give them at least a proportional
        # scale-up rather than silently reporting current revenue.
        channel_results = []
        cur_spend_vec = np.array([current_allocation.get(ch, avail/n) for ch in channels])
        cur_total = cur_spend_vec.sum()
        if cur_total > 0:
            scale = avail / cur_total
            proportional = np.clip(cur_spend_vec * scale, lo_arr, hi_arr)
        else:
            proportional = np.full(n, avail / n)

        for i, ch in enumerate(channels):
            cur = current_allocation.get(ch, avail/n)
            opt = float(proportional[i])
            cur_rev = _predict_revenue(cur, response_curves[ch])
            opt_rev = _predict_revenue(opt, response_curves[ch])
            mROI = _marginal_revenue(opt, response_curves[ch])
            channel_results.append({
                "channel": ch, "current_spend": round(cur, 0), "optimized_spend": round(opt, 0),
                "change_pct": round((opt - cur) / max(cur, 1) * 100, 1),
                "current_revenue": round(cur_rev, 0), "optimized_revenue": round(opt_rev, 0),
                "revenue_delta": round(opt_rev - cur_rev, 0),
                "current_roi": round((cur_rev-cur)/max(cur,1), 3),
                "optimized_roi": round((opt_rev-opt)/max(opt,1), 3),
                "marginal_roi": round(mROI, 4), "locked": False,
            })
        for ch, sp in locked.items():
            if ch in response_curves and "error" not in response_curves[ch]:
                rev = _predict_revenue(sp, response_curves[ch])
                channel_results.append({"channel":ch,"current_spend":round(sp,0),"optimized_spend":round(sp,0),
                    "change_pct":0,"current_revenue":round(rev,0),"optimized_revenue":round(rev,0),
                    "revenue_delta":0,"current_roi":round((rev-sp)/max(sp,1),3),
                    "optimized_roi":round((rev-sp)/max(sp,1),3),"marginal_roi":0,"locked":True})
        total_opt_rev = sum(c["optimized_revenue"] for c in channel_results)
        total_cur_rev = sum(c["current_revenue"] for c in channel_results)
        fail_warnings = ["Optimizer did not converge; showing a proportional scale-up as a directional answer."]
        if capacity_warning:
            fail_warnings.insert(0, capacity_warning)
        return {"channels": channel_results, "summary": {
            "total_budget": total_budget, "current_revenue": total_cur_rev,
            "optimized_revenue": total_opt_rev,
            "revenue_uplift": round(total_opt_rev - total_cur_rev, 0),
            "uplift_pct": round((total_opt_rev - total_cur_rev) / max(total_cur_rev, 1) * 100, 2),
            "current_roi": round((total_cur_rev - sum(c["current_spend"] for c in channel_results)) / max(sum(c["current_spend"] for c in channel_results), 1), 3),
            "optimized_roi": round((total_opt_rev - sum(c["optimized_spend"] for c in channel_results)) / max(sum(c["optimized_spend"] for c in channel_results), 1), 3),
        }, "optimizer_info": {
            "converged": False,
            "warning": fail_warnings[0],
            "warnings": fail_warnings,
            "mode": "proportional_scale",
        }}

    opt_spend = best_result.x

    # Build results
    channel_results = []
    for i, ch in enumerate(channels):
        cur = current_allocation.get(ch, avail/n)
        opt = float(opt_spend[i])
        opt_rev = _predict_revenue(opt, response_curves[ch])
        cur_rev = _predict_revenue(cur, response_curves[ch])
        mROI = _marginal_revenue(opt, response_curves[ch])
        channel_results.append({
            "channel": ch, "current_spend": round(cur, 0), "optimized_spend": round(opt, 0),
            "change_pct": round((opt-cur)/max(cur,1)*100, 1),
            "current_revenue": round(cur_rev, 0), "optimized_revenue": round(opt_rev, 0),
            "revenue_delta": round(opt_rev - cur_rev, 0),
            "current_roi": round((cur_rev-cur)/max(cur,1), 3),
            "optimized_roi": round((opt_rev-opt)/max(opt,1), 3),
            "marginal_roi": round(mROI, 4), "locked": False,
            # Execution constraints for this channel — surface them so the
            # Plan/Roadmap screens can show lead times and honest expectations.
            "constraints": per_channel_constraints.get(ch, {}),
        })
    # Add locked channels
    for ch, sp in locked.items():
        if ch in response_curves and "error" not in response_curves[ch]:
            rev = _predict_revenue(sp, response_curves[ch])
            channel_results.append({"channel":ch,"current_spend":round(sp,0),"optimized_spend":round(sp,0),
                "change_pct":0,"current_revenue":round(rev,0),"optimized_revenue":round(rev,0),
                "revenue_delta":0,"current_roi":round((rev-sp)/max(sp,1),3),
                "optimized_roi":round((rev-sp)/max(sp,1),3),"marginal_roi":0,"locked":True})

    total_cur_rev = sum(c["current_revenue"] for c in channel_results)
    total_opt_rev = sum(c["optimized_revenue"] for c in channel_results)

    # ═══ GUARDRAILS ═══
    warnings = []
    if capacity_warning:
        warnings.append(capacity_warning)

    # Guard 1: If optimized is worse than current, fall back to current allocation
    # -- but only when current allocation actually fits within the target budget.
    # If budget < current spend, we can't "stay with current" because that would
    # violate the budget constraint. In that case the optimizer's answer
    # (shrinking proportionally) stands even if revenue dropped, because
    # dropping revenue is the correct answer when you cut budget.
    total_current_spend = sum(c["current_spend"] for c in channel_results)
    current_allocation_fits = total_current_spend <= total_budget * 1.01  # 1% tolerance
    if total_opt_rev < total_cur_rev * 0.95 and current_allocation_fits:
        warnings.append("Optimizer found no improvement over current allocation. Returning current plan with analysis.")
        # Reset to current allocation
        for c in channel_results:
            if not c.get("locked"):
                c["optimized_spend"] = c["current_spend"]
                c["optimized_revenue"] = c["current_revenue"]
                c["change_pct"] = 0
                c["revenue_delta"] = 0
                c["optimized_roi"] = c["current_roi"]
        total_opt_rev = total_cur_rev

    # Guard 2: Cap extreme individual channel swings. With the new per-channel
    # bounds and extrapolation cap, this should almost never fire — it's a
    # belt-and-suspenders check against ever reporting a >+200% or <-80%
    # swing to the user. When it does fire, we update BOTH the change_pct
    # display AND the underlying optimized_spend (the previous code only
    # updated the display, leaving an inconsistency between "spend went from
    # $1M to $25M" and "change_pct = 200").
    for c in channel_results:
        if c.get("locked"): continue
        cur = c["current_spend"]
        if c["change_pct"] > 200:
            warnings.append(f"{c['channel']}: capped from +{c['change_pct']:.0f}% to +200%")
            c["change_pct"] = 200
            c["optimized_spend"] = round(cur * 3.0, 0)  # +200% = 3x current
            c["optimized_revenue"] = round(
                _predict_revenue(c["optimized_spend"], response_curves[c["channel"]], extrapolation_cap), 0
            )
            c["revenue_delta"] = round(c["optimized_revenue"] - c["current_revenue"], 0)
            c["optimized_roi"] = round(
                (c["optimized_revenue"] - c["optimized_spend"]) / max(c["optimized_spend"], 1), 3
            )
        if c["change_pct"] < -80:
            warnings.append(f"{c['channel']}: capped from {c['change_pct']:.0f}% to -80%")
            c["change_pct"] = -80
            c["optimized_spend"] = round(cur * 0.2, 0)  # -80% = 0.2x current
            c["optimized_revenue"] = round(
                _predict_revenue(c["optimized_spend"], response_curves[c["channel"]], extrapolation_cap), 0
            )
            c["revenue_delta"] = round(c["optimized_revenue"] - c["current_revenue"], 0)
            c["optimized_roi"] = round(
                (c["optimized_revenue"] - c["optimized_spend"]) / max(c["optimized_spend"], 1), 3
            )

    # Guard 3: Ensure all spends positive
    for c in channel_results:
        c["optimized_spend"] = max(0, c["optimized_spend"])
        c["current_spend"] = max(0, c["current_spend"])

    return {
        "channels": channel_results,
        "summary": {
            "total_budget": round(total_budget, 0),
            "current_revenue": round(total_cur_rev, 0),
            "optimized_revenue": round(total_opt_rev, 0),
            "revenue_uplift": round(total_opt_rev - total_cur_rev, 0),
            "uplift_pct": round((total_opt_rev-total_cur_rev)/max(total_cur_rev,1)*100, 2),
            "current_roi": round((total_cur_rev-total_budget)/max(total_budget,1), 3),
            "optimized_roi": round((total_opt_rev-total_budget)/max(total_budget,1), 3),
        },
        "optimizer_info": {
            "method": "scipy_SLSQP",
            "objective": objective,
            "n_restarts": n_restarts,
            "converged": best_result.success,
            "n_channels_optimized": n,
            "n_channels_locked": len(locked),
            "warnings": warnings,
        },
    }

def sensitivity_analysis(response_curves, base_budget, objective="balanced", steps=None):
    """Run optimizer at multiple budget levels to show sensitivity.

    Each budget step uses a deterministic seed so the results are
    reproducible across calls with the same inputs. Without this, the
    multi-restart Dirichlet sampling inside optimize_budget produces
    slightly different local optima at adjacent budget levels, which
    can cause the revenue-vs-budget curve to dip at a few points even
    though theory says it should be monotonic.
    """
    if steps is None: steps = [-30, -20, -10, 0, 10, 20, 30, 50]
    results = []
    for i, pct in enumerate(steps):
        budget = base_budget * (1 + pct/100)
        # Fixed seed per step for reproducibility
        np.random.seed(42 + i)
        opt = optimize_budget(response_curves, budget, objective)
        if "error" not in opt:
            results.append({"budget_change_pct": pct, "budget": round(budget,0),
                "revenue": opt["summary"]["optimized_revenue"],
                "roi": opt["summary"]["optimized_roi"],
                "uplift": opt["summary"]["revenue_uplift"]})
    return results
