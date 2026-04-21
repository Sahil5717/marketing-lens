/**
 * AllocationComparison — the core Screen 06 component.
 *
 * Modes:
 *   - default:   shows Current donut + "earned reveal" CTA (Recommended hidden)
 *   - revealed:  shows Current and Recommended side-by-side + override toggle
 *   - editing:   Recommended legend swaps into editable inputs with live deltas
 *
 * Data:
 *   - allocation from GET /api/budget-optimization .allocation
 *   - onScoreOverride(alloc): async callback that returns
 *       { delta_vs_atlas_cr, delta_vs_current_cr, projected_roi, pushback, user_total_cr, budget_total_cr }
 */
import React, { useState, useMemo, useCallback, useEffect } from "react";
import { tok } from "../../design/tokens.js";
import Donut from "./Donut.jsx";

/**
 * Parse the backend's display_amount string like "$24.6M" / "₹24.6 Cr" /
 * "€12.4M" / "£582" into { value, scale, unitSuffix, symbol }.
 * We use the scale + unit from the recommended total so all edit inputs
 * share the same scale (no mixed M and K in the same edit column).
 */
function parseScale(displayAmount) {
  if (!displayAmount) return { divisor: 1, unitSuffix: "", symbol: "" };
  const m = /^[+\u2212]?([$€£₹])[\d,]+(?:\.\d+)?\s*(B|M|K|Cr|L)?/.exec(displayAmount);
  if (!m) return { divisor: 1, unitSuffix: "", symbol: "" };
  const [, symbol, unit] = m;
  const map = { B: 1e9, M: 1e6, K: 1e3, Cr: 1e7, L: 1e5 };
  const divisor = map[unit] || 1;
  const unitSuffix = unit ? (unit === "Cr" ? "Cr" : unit === "L" ? "L" : unit) : "";
  return { divisor, unitSuffix, symbol };
}

function LegendRow({ slice, showDelta }) {
  const direction = slice.direction;
  const color = direction === "up" ? tok.green
              : direction === "down" ? tok.red
              : tok.text3;
  const arrow = direction === "up" ? "↑" : direction === "down" ? "↓" : "";
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10,
      padding: "7px 0", fontSize: 12,
    }}>
      <span style={{
        width: 8, height: 8, borderRadius: 2,
        background: slice.color, flexShrink: 0,
      }}/>
      <span style={{ flex: 1 }}>{slice.channel}</span>
      <span style={{ display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
        <strong style={{
          color: showDelta ? color : tok.text,
          fontSize: 12, fontWeight: 700,
        }}>
          {slice.percentage}% {showDelta && arrow}
        </strong>
        <span style={{ color: tok.text3, fontSize: 11 }}>{slice.display_amount}</span>
      </span>
    </div>
  );
}

function CurrentSide({ current, totalDisplay }) {
  return (
    <div>
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        marginBottom: 16,
      }}>
        <div style={{ fontSize: 13, fontWeight: 700 }}>Current</div>
        <div style={{
          fontSize: 10, color: tok.text3,
          textTransform: "uppercase", letterSpacing: "0.12em", fontWeight: 600,
        }}>Today</div>
      </div>
      <div style={{ display: "flex", gap: 18, alignItems: "center" }}>
        <Donut
          slices={current}
          centerLabel={totalDisplay}
          centerSub="Total"
          size={140}
        />
        <div style={{ flex: 1 }}>
          {current.map((s, i) => <LegendRow key={i} slice={s}/>)}
        </div>
      </div>
    </div>
  );
}

function EarnedRevealCTA({ onReveal }) {
  return (
    <div
      onClick={onReveal}
      style={{
        background: `linear-gradient(135deg, ${tok.accentSoft}, #F7F3FF)`,
        border: `1px dashed ${tok.accent}`,
        borderRadius: 12, padding: "32px 28px",
        display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center", gap: 16,
        cursor: "pointer", transition: "all .25s",
        textAlign: "center",
      }}
      onMouseEnter={e => {
        e.currentTarget.style.background = `linear-gradient(135deg, ${tok.accent}, ${tok.accentDeep})`;
        e.currentTarget.querySelectorAll("*").forEach(el => el.style.color = "#fff");
      }}
      onMouseLeave={e => {
        e.currentTarget.style.background = `linear-gradient(135deg, ${tok.accentSoft}, #F7F3FF)`;
        e.currentTarget.querySelector(".reveal-eyebrow").style.color = tok.accent;
        e.currentTarget.querySelector(".reveal-text").style.color = tok.text;
        e.currentTarget.querySelector(".reveal-arrow").style.color = tok.accent;
        e.currentTarget.querySelector(".reveal-arrow").style.background = tok.card;
      }}
    >
      <div className="reveal-eyebrow" style={{
        fontSize: 10, color: tok.accent,
        textTransform: "uppercase", letterSpacing: "0.22em",
        fontWeight: 700,
      }}>Earned reveal</div>
      <div className="reveal-text" style={{
        fontFamily: tok.fontDisplay, fontSize: 18, fontWeight: 500,
        letterSpacing: "-.01em", lineHeight: 1.35,
        maxWidth: 260, color: tok.text,
      }}>
        Show me <em>how Atlas would reallocate</em> this budget
      </div>
      <div className="reveal-arrow" style={{
        width: 42, height: 42, borderRadius: "50%",
        background: tok.card, color: tok.accent,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 20, fontWeight: 700, transition: "all .2s",
      }}>→</div>
    </div>
  );
}

function RecommendedSide({
  recommended, totalDisplay, editing, userValues, onUserChange,
}) {
  return (
    <div>
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        marginBottom: 16,
      }}>
        <div style={{ fontSize: 13, fontWeight: 700 }}>Atlas Recommended</div>
        <div style={{
          fontSize: 10, color: tok.green,
          textTransform: "uppercase", letterSpacing: "0.12em", fontWeight: 600,
        }}>↗ Optimized</div>
      </div>
      <div style={{ display: "flex", gap: 18, alignItems: "center" }}>
        <Donut
          slices={recommended}
          centerLabel={totalDisplay}
          centerSub="Total"
          centerColor={tok.accentDeep}
          size={140}
        />
        <div style={{ flex: 1 }}>
          {!editing && recommended.map((s, i) =>
            <LegendRow key={i} slice={s} showDelta />
          )}

          {editing && recommended.map((s, i) => {
            // Use the same scale as the backend's display_amount so
            // "24.6 M" stays in scale with "$24.6M" shown by the backend.
            const { divisor, unitSuffix, symbol } = parseScale(s.display_amount);
            const atlasScaled = s.amount / divisor;
            const value = userValues[s.channel] ?? +atlasScaled.toFixed(1);
            return (
              <div key={i} style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "6px 0",
              }}>
                <span style={{
                  width: 8, height: 8, borderRadius: 2,
                  background: s.color, flexShrink: 0,
                }}/>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, fontWeight: 500 }}>{s.channel}</div>
                  <div style={{ fontSize: 10, color: tok.text3 }}>
                    Atlas: {s.display_amount}
                  </div>
                </div>
                <div style={{
                  display: "flex", alignItems: "center",
                  border: `1px solid ${tok.border}`, borderRadius: 6,
                  overflow: "hidden",
                }}>
                  <span style={{
                    padding: "6px 8px", background: tok.panelSoft,
                    color: tok.text3, fontSize: 11, fontWeight: 600,
                  }}>{symbol}</span>
                  <input
                    type="number"
                    step="0.1"
                    value={value}
                    onChange={e => onUserChange(s.channel, parseFloat(e.target.value) * divisor)}
                    style={{
                      width: 70, padding: "6px 8px",
                      border: "none",
                      fontFamily: "inherit", fontSize: 12,
                      textAlign: "right", outline: "none",
                    }}
                  />
                </div>
                <span style={{ fontSize: 11, color: tok.text3 }}>{unitSuffix}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function EditTotalBar({ userTotal, budgetTotal, totalDisplay }) {
  // Tolerance: 0.1% of budget — matches the backend's "big shift" cutoff
  const tolerance = Math.max(budgetTotal * 0.001, 1);
  const matches = Math.abs(userTotal - budgetTotal) < tolerance;
  // Scale derived from the backend's formatted total, so user + budget
  // render with the same suffix (e.g. both in M for USD, both in Cr for INR).
  const { divisor, unitSuffix, symbol } = parseScale(totalDisplay);
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", alignItems: "center",
      padding: "12px 16px",
      background: matches ? tok.greenSoft : tok.redSoft,
      border: `1px solid ${matches ? "#D0F0E1" : "#F9D0D0"}`,
      borderRadius: 8, marginTop: 16,
      fontSize: 12,
    }}>
      <span style={{ fontWeight: 600 }}>Total allocation</span>
      <span>
        <span style={{
          fontWeight: 700,
          color: matches ? tok.greenDeep : tok.redDeep,
        }}>{symbol}{(userTotal / divisor).toFixed(1)}{unitSuffix}</span>
        <span style={{ color: tok.text3 }}>
          {" "}/ {symbol}{(budgetTotal / divisor).toFixed(1)}{unitSuffix} budget
        </span>
      </span>
    </div>
  );
}

function AtlasPushback({ pushback }) {
  if (!pushback) return null;
  return (
    <div style={{
      marginTop: 14, padding: "14px 18px",
      background: `linear-gradient(135deg, ${tok.atlasSoft}, #FEFAEC)`,
      border: `1px solid #F2D89A`,
      borderLeft: `3px solid ${tok.atlas}`,
      borderRadius: 10,
      display: "flex", gap: 14, alignItems: "flex-start",
    }}>
      <div style={{
        width: 30, height: 30, borderRadius: "50%",
        background: `linear-gradient(135deg, ${tok.atlas}, ${tok.atlasDeep})`,
        display: "flex", alignItems: "center", justifyContent: "center",
        color: "#fff", fontFamily: tok.fontDisplay, fontWeight: 700,
        fontSize: 13, flexShrink: 0,
      }}>A</div>
      <div style={{ flex: 1, fontSize: 13, lineHeight: 1.55 }}>
        <div style={{
          fontFamily: tok.fontDisplay, fontStyle: "italic", fontWeight: 600,
          color: tok.atlasDeep, marginBottom: 4,
          fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em",
        }}>Atlas · Pushback</div>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>{pushback.headline}</div>
        <div style={{ color: tok.text2, fontSize: 12 }}>{pushback.detail}</div>
      </div>
    </div>
  );
}

export default function AllocationComparison({
  allocation,
  onScoreOverride,
  revealed: controlledRevealed,
  onReveal,
}) {
  const [internalRevealed, setInternalRevealed] = useState(false);
  const revealed = controlledRevealed !== undefined ? controlledRevealed : internalRevealed;
  const handleReveal = () => {
    setInternalRevealed(true);
    if (onReveal) onReveal();
  };

  const [editing, setEditing] = useState(false);
  const [userValues, setUserValues] = useState({});
  const [scoreResult, setScoreResult] = useState(null);

  // Initialize user values from Atlas recommendation (in native currency units)
  useEffect(() => {
    if (revealed && allocation?.recommended) {
      const init = {};
      allocation.recommended.forEach(s => {
        init[s.channel] = s.amount;
      });
      setUserValues(init);
    }
  }, [revealed, allocation]);

  const userTotal = useMemo(
    () => Object.values(userValues).reduce((a, b) => a + (b || 0), 0),
    [userValues]
  );
  // Budget total in native currency units
  const budgetTotal = allocation?.total_budget ?? 0;

  // When editing, fetch override score after debounce
  useEffect(() => {
    if (!editing || !onScoreOverride) return;
    const id = setTimeout(() => {
      onScoreOverride(userValues).then(setScoreResult).catch(() => setScoreResult(null));
    }, 350);
    return () => clearTimeout(id);
  }, [editing, userValues, onScoreOverride]);

  const handleUserChange = useCallback((channel, val) => {
    setUserValues(prev => ({ ...prev, [channel]: val }));
  }, []);

  const handleReset = () => {
    if (!allocation?.recommended) return;
    const init = {};
    allocation.recommended.forEach(s => {
      init[s.channel] = s.amount;
    });
    setUserValues(init);
    setScoreResult(null);
  };

  if (!allocation) return null;

  return (
    <div style={{
      background: tok.card, border: `1px solid ${tok.border}`,
      borderRadius: 12, padding: "22px 24px", marginBottom: 18,
      fontFamily: tok.fontUi,
    }}>
      {/* Head */}
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        marginBottom: 18,
      }}>
        <div style={{
          fontFamily: tok.fontDisplay, fontSize: 18, fontWeight: 600,
          letterSpacing: "-.01em",
        }}>Current vs Recommended Allocation</div>
        <div style={{ fontSize: 12, color: tok.text2 }}>
          Total budget · <strong>{allocation.total_budget_display}</strong>
        </div>
      </div>

      {/* Comparison grid */}
      <div style={{
        display: "grid",
        gridTemplateColumns: revealed ? "1fr 1fr" : "1fr 1fr",
        gap: 20,
      }}>
        <CurrentSide current={allocation.current} totalDisplay={allocation.total_budget_display}/>
        {!revealed ? (
          <EarnedRevealCTA onReveal={handleReveal}/>
        ) : (
          <RecommendedSide
            recommended={allocation.recommended}
            totalDisplay={allocation.total_budget_display}
            editing={editing}
            userValues={userValues}
            onUserChange={handleUserChange}
          />
        )}
      </div>

      {/* Edit-mode extras */}
      {editing && (
        <>
          <EditTotalBar
            userTotal={userTotal}
            budgetTotal={budgetTotal}
            totalDisplay={allocation.total_budget_display}
          />
          <AtlasPushback pushback={scoreResult?.pushback}/>
        </>
      )}

      {/* Toggle row */}
      {revealed && (
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          marginTop: 20, paddingTop: 16,
          borderTop: `1px solid ${tok.border}`,
          gap: 16,
        }}>
          <div style={{ fontSize: 12, color: tok.text2, flex: 1 }}>
            Need to override Atlas's recommendation? <strong>You can edit individual channels</strong> — Atlas flags overrides that hurt the plan.
          </div>
          <button
            onClick={() => {
              if (editing) handleReset();
              setEditing(e => !e);
            }}
            style={{
              padding: "9px 16px",
              background: editing ? tok.card : tok.accent,
              color: editing ? tok.text : "#fff",
              border: `1px solid ${editing ? tok.border : tok.accent}`,
              borderRadius: 8,
              fontFamily: "inherit", fontSize: 12, fontWeight: 600,
              cursor: "pointer",
              display: "flex", alignItems: "center", gap: 6,
            }}
          >
            {editing ? "Cancel" : "✎ Override recommendation"}
          </button>
        </div>
      )}
    </div>
  );
}
