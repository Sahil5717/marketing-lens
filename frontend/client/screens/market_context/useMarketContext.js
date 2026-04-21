/**
 * useMarketContext — fetches GET /api/market-context and returns
 * { data, loading, error } in the shape the two panels expect.
 *
 * Kept tiny on purpose. No library. No retries. No SWR/react-query
 * coupling. When the real data layer lands (plan §4 "API client"), the
 * hook swaps to that without touching the consumers.
 */
import { useEffect, useState } from "react";

export function useMarketContext({
  asOf,
  category,
  regions,         // array<string> | undefined
  lookaheadDays = 90,
  lookbackMonths = 4,
  peakLimit = 5,
  apiBase = "",   // blank when same-origin; set to e.g. "http://localhost:8000" for dev
} = {}) {
  const [state, setState] = useState({ data: null, loading: true, error: null });

  useEffect(() => {
    let cancelled = false;
    setState({ data: null, loading: true, error: null });

    const qs = new URLSearchParams();
    if (asOf) qs.set("as_of", asOf);
    if (category) qs.set("category", category);
    if (regions && regions.length) qs.set("regions", regions.join(","));
    qs.set("lookahead_days", String(lookaheadDays));
    qs.set("lookback_months", String(lookbackMonths));
    qs.set("peak_limit", String(peakLimit));

    fetch(`${apiBase}/api/market-context?${qs.toString()}`)
      .then(r => {
        if (!r.ok) throw new Error(`Market context request failed: ${r.status}`);
        return r.json();
      })
      .then(data => {
        if (!cancelled) setState({ data, loading: false, error: null });
      })
      .catch(err => {
        if (!cancelled) setState({ data: null, loading: false, error: err.message });
      });

    return () => { cancelled = true; };
  }, [asOf, category, regions?.join(","), lookaheadDays, lookbackMonths, peakLimit, apiBase]);

  return state;
}
