/**
 * useBudgetOptimization — fetches GET /api/budget-optimization and
 * exposes a callback for POSTing override scorings. Uses apiRequest
 * so every call carries the user's JWT.
 *
 * Returns { data, loading, error, scoreOverride }.
 * scoreOverride(alloc: { channel: nativeCurrencyValue }) → resolves
 * with the server's scoring payload (or null on error). Allocation
 * values are in the engagement's currency base unit.
 */
import { useEffect, useState, useCallback } from "react";
import { apiRequest } from "../../api.js";

export function useBudgetOptimization({ engagementId = "default" } = {}) {
  const [state, setState] = useState({ data: null, loading: true, error: null });

  useEffect(() => {
    let cancelled = false;
    setState({ data: null, loading: true, error: null });

    apiRequest(
      `/api/budget-optimization?engagement_id=${encodeURIComponent(engagementId)}`
    ).then(({ data, error }) => {
      if (cancelled) return;
      if (error) {
        setState({ data: null, loading: false, error: error.message || "Request failed" });
      } else {
        setState({ data, loading: false, error: null });
      }
    });

    return () => { cancelled = true; };
  }, [engagementId]);

  const scoreOverride = useCallback(async (allocation) => {
    const { data, error } = await apiRequest(
      `/api/budget-optimization/override?engagement_id=${encodeURIComponent(engagementId)}`,
      {
        method: "POST",
        body: JSON.stringify({ allocation }),
      }
    );
    if (error) return null;
    return data;
  }, [engagementId]);

  return { ...state, scoreOverride };
}
