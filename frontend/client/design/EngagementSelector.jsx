/**
 * EngagementSelector — dropdown for picking the active engagement.
 *
 * Fetches the engagement list from /api/engagements once on mount, persists
 * the current selection in localStorage under "yi.engagementId", and fires
 * onChange(engagementId) when the user picks a different one.
 *
 * Rendered inside the Sidebar footer so the current engagement is visible
 * at all times (sets the context for every number on the screen).
 *
 * Props
 * -----
 *   apiBase         blank for same-origin; "http://localhost:8000" in dev
 *   engagementId    currently-selected id (controlled)
 *   onChange        (newId) => void
 *   compact         true for a tighter footer look
 */
import React, { useEffect, useState, useRef } from "react";
import { tok } from "./tokens.js";

const STORAGE_KEY = "yi.engagementId";

export function getStoredEngagementId() {
  try {
    return localStorage.getItem(STORAGE_KEY) || "default";
  } catch {
    return "default";
  }
}

export function setStoredEngagementId(id) {
  try {
    localStorage.setItem(STORAGE_KEY, id);
  } catch {
    /* no-op if storage is disabled */
  }
}

export default function EngagementSelector({
  apiBase = "",
  engagementId = "default",
  onChange,
  compact = false,
}) {
  const [engagements, setEngagements] = useState([]);
  const [currencies, setCurrencies] = useState([]);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState(null);
  const rootRef = useRef(null);

  // Load engagements once
  useEffect(() => {
    let cancelled = false;
    fetch(`${apiBase}/api/engagements`)
      .then(r => {
        if (!r.ok) throw new Error(`status ${r.status}`);
        return r.json();
      })
      .then(data => {
        if (cancelled) return;
        setEngagements(data.engagements || []);
        setCurrencies(data.supported_currencies || []);
        setError(null);
      })
      .catch(err => {
        if (!cancelled) setError(err.message);
      });
    return () => { cancelled = true; };
  }, [apiBase]);

  // Close when clicking outside
  useEffect(() => {
    if (!open) return;
    const onDocClick = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  const current = engagements.find(e => e.id === engagementId)
    || { id: engagementId, name: engagementId === "default" ? "Default" : engagementId, currency: "USD" };

  const handlePick = (id) => {
    setStoredEngagementId(id);
    setOpen(false);
    if (onChange) onChange(id);
  };

  return (
    <div ref={rootRef} style={{ position: "relative", fontFamily: tok.fontUi }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: "100%", textAlign: "left",
          padding: compact ? "9px 10px" : "11px 12px",
          background: "rgba(255,255,255,.06)",
          border: `1px solid rgba(255,255,255,.1)`,
          borderRadius: 8,
          color: "#fff", fontFamily: "inherit", fontSize: 12,
          cursor: "pointer",
          display: "flex", alignItems: "center", gap: 10,
          transition: "background .15s",
        }}
        onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,.1)"}
        onMouseLeave={e => e.currentTarget.style.background = "rgba(255,255,255,.06)"}
      >
        <div style={{ flex: 1, overflow: "hidden" }}>
          <div style={{
            fontSize: 9, color: "#8C92AC",
            textTransform: "uppercase", letterSpacing: "0.12em",
            fontWeight: 600, marginBottom: 2,
          }}>Engagement</div>
          <div style={{
            fontSize: 12, fontWeight: 600,
            whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
          }}>
            {current.name}
          </div>
        </div>
        <div style={{
          padding: "2px 6px", borderRadius: 4,
          background: "rgba(124,92,255,.25)",
          color: "#C4B5FD", fontSize: 10, fontWeight: 700,
        }}>{current.currency}</div>
        <div style={{
          color: "#8C92AC", fontSize: 11,
          transform: open ? "rotate(180deg)" : "none",
          transition: "transform .15s",
        }}>▾</div>
      </button>

      {open && (
        <div style={{
          position: "absolute", bottom: "calc(100% + 6px)", left: 0, right: 0,
          background: "#1A1D2E",
          border: "1px solid rgba(255,255,255,.12)",
          borderRadius: 8,
          boxShadow: "0 8px 30px rgba(0,0,0,.4)",
          overflow: "hidden",
          zIndex: 100,
          maxHeight: 320, overflowY: "auto",
        }}>
          <div style={{
            padding: "8px 12px",
            fontSize: 9, color: "#8C92AC",
            textTransform: "uppercase", letterSpacing: "0.12em",
            fontWeight: 600,
            borderBottom: "1px solid rgba(255,255,255,.06)",
          }}>
            {engagements.length} engagement{engagements.length === 1 ? "" : "s"} · Switch to
          </div>

          {error && (
            <div style={{ padding: 12, color: "#F87171", fontSize: 11 }}>
              Couldn't load engagements: {error}
            </div>
          )}

          {engagements.map(e => {
            const active = e.id === engagementId;
            return (
              <div
                key={e.id}
                onClick={() => handlePick(e.id)}
                style={{
                  padding: "10px 12px",
                  color: "#fff", fontSize: 12,
                  display: "flex", alignItems: "center", gap: 10,
                  cursor: "pointer",
                  background: active ? "rgba(124,92,255,.18)" : "transparent",
                  borderLeft: active ? `3px solid ${tok.accent}` : "3px solid transparent",
                  transition: "background .1s",
                }}
                onMouseEnter={ev => {
                  if (!active) ev.currentTarget.style.background = "rgba(255,255,255,.05)";
                }}
                onMouseLeave={ev => {
                  if (!active) ev.currentTarget.style.background = "transparent";
                }}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600 }}>{e.name}</div>
                  <div style={{ color: "#8C92AC", fontSize: 10, marginTop: 2 }}>
                    {e.id} · {e.locale}
                  </div>
                </div>
                <div style={{
                  padding: "2px 6px", borderRadius: 4,
                  background: "rgba(255,255,255,.08)",
                  fontSize: 10, fontWeight: 700,
                }}>{e.currency}</div>
              </div>
            );
          })}

          <div style={{
            padding: "8px 12px",
            fontSize: 10, color: "#8C92AC",
            borderTop: "1px solid rgba(255,255,255,.06)",
          }}>
            Supported: {currencies.join(", ") || "USD, INR, EUR, GBP"}
          </div>
        </div>
      )}
    </div>
  );
}
