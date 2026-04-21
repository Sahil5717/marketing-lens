/**
 * useExecutiveSummary — fetches GET /api/executive-summary via the
 * authenticated apiRequest helper. Returns { data, loading, error }.
 *
 * Pass `engagementId` to target a non-default engagement.
 */
import { useEffect, useState } from "react";
import { apiRequest } from "../../api.js";

export function useExecutiveSummary({ engagementId = "default" } = {}) {
  const [state, setState] = useState({ data: null, loading: true, error: null });

  useEffect(() => {
    let cancelled = false;
    setState({ data: null, loading: true, error: null });

    apiRequest(
      `/api/executive-summary?engagement_id=${encodeURIComponent(engagementId)}`
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

  return state;
}
