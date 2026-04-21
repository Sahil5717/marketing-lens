/**
 * useExecutiveSummary — fetches GET /api/executive-summary.
 *
 * Same shape as useMarketContext: returns { data, loading, error }.
 * No library, no retries — swap in real query layer later.
 */
import { useEffect, useState } from "react";

export function useExecutiveSummary({ apiBase = "" } = {}) {
  const [state, setState] = useState({ data: null, loading: true, error: null });

  useEffect(() => {
    let cancelled = false;
    setState({ data: null, loading: true, error: null });

    fetch(`${apiBase}/api/executive-summary`)
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
  }, [apiBase]);

  return state;
}
