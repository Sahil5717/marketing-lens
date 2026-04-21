/**
 * useExecutiveSummary — fetches GET /api/executive-summary.
 *
 * Same shape as useMarketContext: returns { data, loading, error }.
 * No library, no retries — swap in real query layer later.
 *
 * Pass `engagementId` to target a non-default engagement.
 */
import { useEffect, useState } from "react";

export function useExecutiveSummary({ apiBase = "", engagementId = "default" } = {}) {
  const [state, setState] = useState({ data: null, loading: true, error: null });

  useEffect(() => {
    let cancelled = false;
    setState({ data: null, loading: true, error: null });

    const url = `${apiBase}/api/executive-summary?engagement_id=${encodeURIComponent(engagementId)}`;
    fetch(url)
      .then(r => {
        if (!r.ok) throw new Error(`Executive summary request failed: ${r.status}`);
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

  return state;
}
