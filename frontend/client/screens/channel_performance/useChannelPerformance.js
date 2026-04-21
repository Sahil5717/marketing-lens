import { useEffect, useState } from "react";

/**
 * useChannelPerformance — fetches GET /api/channel-performance.
 * Pass `engagementId` to target a non-default engagement.
 */
export function useChannelPerformance({
  apiBase = "",
  lookbackMonths = 24,
  engagementId = "default",
} = {}) {
  const [state, setState] = useState({ data: null, loading: true, error: null });

  useEffect(() => {
    let cancelled = false;
    setState({ data: null, loading: true, error: null });
    const url = `${apiBase}/api/channel-performance`
      + `?lookback_months=${lookbackMonths}`
      + `&engagement_id=${encodeURIComponent(engagementId)}`;
    fetch(url)
      .then(r => {
        if (!r.ok) throw new Error(`Channel performance request failed: ${r.status}`);
        return r.json();
      })
      .then(data => { if (!cancelled) setState({ data, loading: false, error: null }); })
      .catch(err => { if (!cancelled) setState({ data: null, loading: false, error: err.message }); });
    return () => { cancelled = true; };
  }, [apiBase, lookbackMonths, engagementId]);

  return state;
}
