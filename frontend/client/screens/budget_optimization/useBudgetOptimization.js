/**
 * useBudgetOptimization — fetches GET /api/budget-optimization and
 * exposes a callback for POSTing override scorings.
 *
 * Returns { data, loading, error, scoreOverride }.
 * scoreOverride(alloc: {channel: nativeCurrencyValue}) → resolves with
 * the server's scoring payload (or null on error). Allocation values
 * must be in the engagement's currency base unit (dollars, rupees,
 * euros, pounds).
 *
 * Pass `engagementId` to target a non-default engagement.
 */
import { useEffect, useState, useCallback } from "react";

export function useBudgetOptimization({ apiBase = "", engagementId = "default" } = {}) {
  const [state, setState] = useState({ data: null, loading: true, error: null });

  useEffect(() => {
    let cancelled = false;
    setState({ data: null, loading: true, error: null });

    const url = `${apiBase}/api/budget-optimization?engagement_id=${encodeURIComponent(engagementId)}`;
    fetch(url)
      .then(r => {
        if (!r.ok) throw new Error(`Budget optimization request failed: ${r.status}`);
        return r.json();
      })
      .then(data => {
        if (!cancelled) setState({ data, loading: false, error: null });
      })
      .catch(err => {
        if (!cancelled) setState({ data: null, loading: false, error: err.message });
      });

    return () => { cancelled = true; };
  }, [apiBase, engagementId]);

  const scoreOverride = useCallback(async (allocation) => {
    try {
      const url = `${apiBase}/api/budget-optimization/override?engagement_id=${encodeURIComponent(engagementId)}`;
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ allocation }),
      });
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  }, [apiBase, engagementId]);

  return { ...state, scoreOverride };
}
