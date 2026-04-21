/**
 * FourMoves — Atlas's top 4 moves with inline "Why?" reveals.
 *
 * Each move shows:
 *   - number, direction arrow, action text with coloured delta
 *   - revenue lift/loss (mint if gain, coral if cut)
 *   - confidence % with horizontal bar
 *   - collapsible Atlas reasoning (80% Bayesian credible interval when present)
 *
 * Data: from /api/budget-optimization .moves
 */
import React, { useState } from "react";
import { tok, atlasCalloutStyle } from "../../design/tokens.js";

/** Render the action string with the monetary delta highlighted in accent. */
function renderActionText(move) {
  const parts = move.action.split(move.delta_spend_display);
  if (parts.length !== 2) {
    // Fallback: just render the action
    return move.action;
  }
  return (
    <>
      {parts[0]}
      <span style={{ fontWeight: 700, color: tok.accentDeep }}>
        {move.delta_spend_display}
      </span>
      {parts[1]}
    </>
  );
}

function ConfidenceBar({ pct }) {
  return (
    <div style={{
      width: 60, height: 4, background: tok.border, borderRadius: 2,
      overflow: "hidden",
    }}>
      <div style={{
        width: `${Math.max(0, Math.min(100, pct))}%`,
        height: "100%",
        background: pct >= 85 ? tok.green : pct >= 70 ? tok.amber : tok.red,
      }}/>
    </div>
  );
}

function MoveRow({ move, isOpen, onToggle }) {
  const isUp = move.direction === "up";
  return (
    <div style={{
      padding: "16px 0",
      borderBottom: `1px solid ${tok.border}`,
    }}>
      <div style={{
        display: "grid",
        gridTemplateColumns: "32px 1fr 140px 140px 80px",
        alignItems: "center", gap: 16,
      }}>
        <div style={{
          fontFamily: tok.fontDisplay, fontStyle: "italic",
          fontSize: 14, color: tok.text3, fontWeight: 500,
        }}>{move.num}</div>

        <div style={{ fontSize: 13, fontWeight: 500 }}>
          <span style={{
            display: "inline-block", marginRight: 8,
            color: isUp ? tok.green : tok.red, fontWeight: 700,
          }}>{isUp ? "↑" : "↓"}</span>
          {renderActionText(move)}
        </div>

        <div>
          <div style={{
            fontFamily: tok.fontDisplay, fontSize: 15, fontWeight: 600,
            fontStyle: "italic", letterSpacing: "-.01em",
            color: move.revenue_lift_kind === "gain" ? tok.greenDeep : tok.red,
          }}>{move.revenue_lift_display}</div>
          <div style={{ fontSize: 10, color: tok.text3,
                         textTransform: "uppercase", letterSpacing: "0.05em" }}>
            {move.revenue_lift_kind === "gain" ? "Revenue lift" : "Lost revenue"}
          </div>
        </div>

        <div>
          <div style={{ fontSize: 13, fontWeight: 700 }}>{move.confidence_display}</div>
          <div style={{ marginTop: 4 }}><ConfidenceBar pct={move.confidence}/></div>
          <div style={{
            fontSize: 10, color: tok.text3,
            textTransform: "uppercase", letterSpacing: "0.05em", marginTop: 4,
          }}>Conf</div>
        </div>

        <div
          onClick={onToggle}
          style={{
            fontSize: 10, fontWeight: 600, color: tok.atlasDeep,
            background: tok.atlasSoft,
            padding: "4px 10px", borderRadius: 5,
            cursor: "pointer", border: "1px solid #F2D89A",
            display: "flex", alignItems: "center", gap: 4,
            userSelect: "none", justifyContent: "center",
            transition: "all .2s",
          }}
          onMouseEnter={e => {
            e.currentTarget.style.background = tok.atlas;
            e.currentTarget.style.color = "#fff";
            e.currentTarget.style.borderColor = tok.atlas;
          }}
          onMouseLeave={e => {
            e.currentTarget.style.background = tok.atlasSoft;
            e.currentTarget.style.color = tok.atlasDeep;
            e.currentTarget.style.borderColor = "#F2D89A";
          }}
        >
          Why? <span style={{
            display: "inline-block",
            transform: isOpen ? "rotate(180deg)" : "none",
            transition: "transform .25s",
          }}>▾</span>
        </div>
      </div>

      {isOpen && (
        <div style={{ paddingTop: 14, paddingLeft: 48 }}>
          <div style={atlasCalloutStyle}>
            <div style={{
              fontFamily: tok.fontDisplay, fontStyle: "italic", fontWeight: 600,
              color: tok.atlasDeep, marginBottom: 6,
              fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em",
            }}>{move.why.who}</div>
            {move.why.text}
          </div>
        </div>
      )}
    </div>
  );
}

export default function FourMoves({ moves = [] }) {
  const [openIdx, setOpenIdx] = useState(null);

  return (
    <div style={{
      background: tok.card, border: `1px solid ${tok.border}`,
      borderRadius: 12, padding: "22px 24px", marginBottom: 18,
      fontFamily: tok.fontUi,
    }}>
      <div style={{
        fontFamily: tok.fontDisplay, fontSize: 18, fontWeight: 600,
        letterSpacing: "-.01em", marginBottom: 4,
      }}>The Four Moves</div>
      <div style={{
        fontSize: 11, color: tok.text3, fontWeight: 500,
        marginBottom: 14,
      }}>Each with a reason · Each with a confidence score</div>

      {moves.length === 0 ? (
        <div style={{
          padding: "24px 0", textAlign: "center",
          color: tok.text3, fontSize: 12, fontStyle: "italic",
        }}>
          Moves populate once the optimizer has run on current performance data.
        </div>
      ) : moves.map((m, i) => (
        <MoveRow
          key={i}
          move={m}
          isOpen={openIdx === i}
          onToggle={() => setOpenIdx(openIdx === i ? null : i)}
        />
      ))}
    </div>
  );
}
