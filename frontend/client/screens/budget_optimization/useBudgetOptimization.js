/**
 * useBudgetOptimization — fetches GET /api/budget-optimization and
 * exposes a callback for POSTing override scorings.
 *
 * Returns { data, loading, error, scoreOverride }.
 * scoreOverride(alloc: {channel: crValue}) → resolves with the server's
 * scoring payload (or null on error).
 */
import { useEffect, useState, useCallback } from "react";

export function useBudgetOptimization({ apiBase = "" } = {}) {
  const [state, setState] = useState({ data: null, loading: true, error: null });

  useEffect(() => {
    let cancelled = false;
    setState({ data: null, loading: true, error: null });

    fetch(`${apiBase}/api/budget-optimization`)
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
  }, [apiBase]);

  const scoreOverride = useCallback(async (allocation) => {
    try {
      const res = await fetch(`${apiBase}/api/budget-optimization/override`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ allocation }),
      });
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  }, [apiBase]);

  return { ...state, scoreOverride };
}
