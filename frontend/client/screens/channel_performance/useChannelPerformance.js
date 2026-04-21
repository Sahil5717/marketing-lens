import { useEffect, useState } from "react";

export function useChannelPerformance({ apiBase = "", lookbackMonths = 24 } = {}) {
  const [state, setState] = useState({ data: null, loading: true, error: null });

  useEffect(() => {
    let cancelled = false;
    setState({ data: null, loading: true, error: null });
    fetch(`${apiBase}/api/channel-performance?lookback_months=${lookbackMonths}`)
      .then(r => {
        if (!r.ok) throw new Error(`Channel performance request failed: ${r.status}`);
        return r.json();
      })
      .then(data => { if (!cancelled) setState({ data, loading: false, error: null }); })
      .catch(err => { if (!cancelled) setState({ data: null, loading: false, error: err.message }); });
    return () => { cancelled = true; };
  }, [apiBase, lookbackMonths]);

  return state;
}
