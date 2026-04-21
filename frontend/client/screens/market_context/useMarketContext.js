/**
 * useMarketContext — fetches GET /api/market-context via apiRequest,
 * returns { data, loading, error } in the shape the two panels expect.
 */
import { useEffect, useState } from "react";
import { apiRequest } from "../../api.js";

export function useMarketContext({
  asOf,
  category,
  regions,         // array<string> | undefined
  lookaheadDays = 90,
  lookbackMonths = 4,
  peakLimit = 5,
  engagementId = "default",
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
    qs.set("engagement_id", engagementId);

    apiRequest(`/api/market-context?${qs.toString()}`).then(({ data, error }) => {
      if (cancelled) return;
      if (error) {
        setState({ data: null, loading: false, error: error.message || "Request failed" });
      } else {
        setState({ data, loading: false, error: null });
      }
    });

    return () => { cancelled = true; };
  }, [asOf, category, regions?.join(","), lookaheadDays, lookbackMonths, peakLimit, engagementId]);

  return state;
}
