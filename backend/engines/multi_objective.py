"""
Multi-Objective Optimization — Production Grade
=================================================
Pareto frontier computation for competing objectives (revenue vs ROI vs CAC).
Libraries: scipy.optimize.minimize (SLSQP per objective), numpy
"""
import numpy as np
from scipy.optimize import minimize
from typing import Dict, List, Optional
import logging
logger = logging.getLogger(__name__)

def pareto_optimize(response_curves, total_budget, objectives=None, n_points=20):
    """
    Compute Pareto frontier by sweeping objective weights.
    Returns set of non-dominated allocations.
    """
    from engines.optimizer import optimize_budget
    
    if objectives is None:
        objectives = ["maximize_revenue", "maximize_roi", "minimize_cac"]
    
    solutions = []
    
    # Sweep weights between revenue and ROI
    for w_rev in np.linspace(0.1, 0.9, n_points):
        w_roi = 1 - w_rev
        weights = {"revenue": w_rev, "roi": w_roi, "leakage": 0, "cost": 0}
        result = optimize_budget(response_curves, total_budget, "balanced", objective_weights=weights, n_restarts=2)
        if "error" not in result:
            solutions.append({
                "weight_revenue": round(w_rev,2), "weight_roi": round(w_roi,2),
                "revenue": result["summary"]["optimized_revenue"],
                "roi": result["summary"]["optimized_roi"],
                "allocation": {c["channel"]: c["optimized_spend"] for c in result["channels"]},
            })
    
    # Filter to Pareto-optimal (non-dominated)
    pareto = []
    for s in solutions:
        dominated = False
        for other in solutions:
            if other["revenue"] >= s["revenue"] and other["roi"] >= s["roi"] and (other["revenue"] > s["revenue"] or other["roi"] > s["roi"]):
                dominated = True; break
        if not dominated: pareto.append(s)
    
    return {"pareto_frontier": sorted(pareto, key=lambda x:x["revenue"]),
            "n_solutions_evaluated": len(solutions), "n_pareto_optimal": len(pareto)}
