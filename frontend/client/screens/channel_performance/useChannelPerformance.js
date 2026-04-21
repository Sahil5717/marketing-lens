import { useEffect, useState } from "react";
import { apiRequest } from "../../api.js";

/**
 * useChannelPerformance — fetches GET /api/channel-performance via the
 * authenticated apiRequest helper.
 */
export function useChannelPerformance({
  lookbackMonths = 24,
  engagementId = "default",
} = {}) {
  const [state, setState] = useState({ data: null, loading: true, error: null });

  useEffect(() => {
    let cancelled = false;
    setState({ data: null, loading: true, error: null });

    const url = `/api/channel-performance`
      + `?lookback_months=${lookbackMonths}`
      + `&engagement_id=${encodeURIComponent(engagementId)}`;

    apiRequest(url).then(({ data, error }) => {
      if (cancelled) return;
      if (error) {
        setState({ data: null, loading: false, error: error.message || "Request failed" });
      } else {
        setState({ data, loading: false, error: null });
      }
    });

    return () => { cancelled = true; };
  }, [lookbackMonths, engagementId]);

  return state;
}
