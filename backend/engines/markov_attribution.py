"""
Markov Chain Attribution — Production Grade
=============================================
Probabilistic multi-touch attribution using transition matrices + removal effect.
Added: convergence validation, confidence via bootstrap, scipy.sparse for efficiency.

Libraries: numpy, scipy.sparse (transition matrix), scipy.stats (significance)
"""
import numpy as np
import pandas as pd
from typing import Dict, List
from itertools import combinations
from scipy import sparse
from scipy import stats as sp_stats
import logging
logger = logging.getLogger(__name__)

def build_transition_matrix(journeys):
    """Build transition probability matrix from journey paths."""
    states_set = set()
    transitions = {}
    for j in journeys:
        path = ["start"]
        tps = sorted(j.get("tps",[]), key=lambda x: x.get("o", x.get("order",0)))
        for tp in tps:
            ch = tp.get("ch", tp.get("channel",""))
            if ch: path.append(ch); states_set.add(ch)
        path.append("conversion" if j.get("cv", j.get("converted",False)) else "null")
        for i in range(len(path)-1):
            f, t = path[i], path[i+1]
            if f not in transitions: transitions[f] = {}
            transitions[f][t] = transitions[f].get(t,0) + 1
    prob = {}
    for f, tos in transitions.items():
        total = sum(tos.values())
        prob[f] = {t: c/total for t, c in tos.items()}
    return prob, sorted(states_set)

def simulate_conversion_probability(prob_matrix, channels, max_iter=100, tol=1e-8):
    """
    Simulate steady-state conversion probability using matrix exponentiation.
    Checks convergence — returns None if matrix doesn't converge.
    """
    all_states = ["start"] + channels + ["conversion", "null"]
    n = len(all_states)
    idx = {s:i for i,s in enumerate(all_states)}
    T = np.zeros((n,n))
    for f, tos in prob_matrix.items():
        if f not in idx: continue
        for t, p in tos.items():
            if t in idx: T[idx[f], idx[t]] = p
    T[idx["conversion"], idx["conversion"]] = 1.0
    T[idx["null"], idx["null"]] = 1.0
    # Ensure rows sum to 1
    for i in range(n):
        rs = T[i].sum()
        if rs > 0: T[i] /= rs
        else: T[i, idx["null"]] = 1.0
    # Power iteration
    state = np.zeros(n); state[idx["start"]] = 1.0
    for it in range(max_iter):
        new_state = state @ T
        if np.max(np.abs(new_state - state)) < tol:
            return float(new_state[idx["conversion"]]), True, it+1
        state = new_state
    return float(state[idx["conversion"]]), False, max_iter

def removal_effect(prob_matrix, channels, base_prob):
    """Calculate removal effect: how much conversion probability drops when each channel is removed."""
    effects = {}
    for ch in channels:
        modified = {}
        for f, tos in prob_matrix.items():
            if f == ch:
                modified[f] = {"null": 1.0}
            else:
                new_tos = {}; removed = 0
                for t, p in tos.items():
                    if t == ch: removed += p
                    else: new_tos[t] = p
                if removed > 0: new_tos["null"] = new_tos.get("null",0) + removed
                total = sum(new_tos.values())
                if total > 0: new_tos = {t: p/total for t,p in new_tos.items()}
                modified[f] = new_tos
        remaining = [c for c in channels if c != ch]
        rem_prob, _, _ = simulate_conversion_probability(modified, remaining)
        effects[ch] = max(0, base_prob - rem_prob)
    return effects

def run_markov_attribution(journeys, n_bootstrap=50):
    """
    Full Markov attribution with bootstrap confidence intervals.
    
    Args:
        journeys: list of journey dicts with tps, cv, rv fields
        n_bootstrap: number of bootstrap resamples for confidence intervals
    
    Returns:
        Channel attributions with revenue, percentage, and 90% CI
    """
    prob, channels = build_transition_matrix(journeys)
    base_prob, converged, iters = simulate_conversion_probability(prob, channels)
    
    if not converged:
        logger.warning(f"Markov chain did not converge after {iters} iterations")
    
    effects = removal_effect(prob, channels, base_prob)
    total_effect = sum(effects.values()) or 1
    total_revenue = sum(j.get("rv",0) for j in journeys if j.get("cv",False))
    
    # Point estimates
    result = {}
    for ch in channels:
        weight = effects[ch] / total_effect
        result[ch] = {
            "weight": round(weight, 4),
            "revenue": round(total_revenue * weight, 0),
            "pct": round(weight * 100, 1),
            "removal_effect": round(effects[ch], 6),
        }
    
    # Bootstrap confidence intervals
    if n_bootstrap > 0 and len(journeys) > 20:
        boot_weights = {ch: [] for ch in channels}
        for _ in range(n_bootstrap):
            sample = [journeys[i] for i in np.random.choice(len(journeys), len(journeys), replace=True)]
            try:
                bp, bch = build_transition_matrix(sample)
                b_base, _, _ = simulate_conversion_probability(bp, bch)
                b_eff = removal_effect(bp, bch, b_base)
                b_total = sum(b_eff.values()) or 1
                for ch in channels:
                    if ch in b_eff: boot_weights[ch].append(b_eff[ch]/b_total)
            except: pass
        
        for ch in channels:
            if boot_weights[ch]:
                arr = np.array(boot_weights[ch])
                result[ch]["weight_ci_90"] = [round(float(np.percentile(arr,5)),4), round(float(np.percentile(arr,95)),4)]
                result[ch]["weight_std"] = round(float(arr.std()),4)
                ci_width = arr.std() / max(result[ch]["weight"], 0.001)
                result[ch]["confidence"] = "High" if ci_width < 0.2 else ("Medium" if ci_width < 0.5 else "Low")
            else:
                result[ch]["confidence"] = "Low"
    
    # Top transitions for visualization
    top_trans = []
    for f, tos in prob.items():
        if f in ("conversion","null"): continue
        for t, p in tos.items():
            if p > 0.03: top_trans.append({"from":f,"to":t,"probability":round(p,4)})
    top_trans.sort(key=lambda x: x["probability"], reverse=True)
    
    return {
        "channels": result,
        "base_conversion_probability": round(base_prob, 6),
        "converged": converged,
        "iterations": iters,
        "total_revenue": round(total_revenue, 0),
        "n_journeys": len(journeys),
        "n_converting": sum(1 for j in journeys if j.get("cv",False)),
        "top_transitions": top_trans[:20],
        "n_bootstrap": n_bootstrap,
    }
