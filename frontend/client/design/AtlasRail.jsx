/**
 * AtlasRail — the collapsible right-hand panel that hosts Atlas's
 * per-screen narration and suggested questions.
 *
 * When collapsed, a 56px strip remains showing only the avatar + vertical
 * label + expand button. The screen's main flow can include an
 * <AtlasInlineCallout/> so users still see Atlas's headline when the
 * rail is collapsed.
 *
 * Props:
 *   - narration: { paragraphs: [{text}], suggested_questions: [string] }
 *   - collapsed + onToggle: controlled by AppShell
 *   - onAsk: callback(question) for suggested-question clicks
 */
import React from "react";
import { tok } from "./tokens.js";

function AtlasAvatar({ size = 40 }) {
  return (
    <div style={{
      width: size, height: size, borderRadius: "50%",
      background: `linear-gradient(135deg, ${tok.atlas}, ${tok.atlasDeep})`,
      display: "flex", alignItems: "center", justifyContent: "center",
      color: "#fff", fontFamily: tok.fontDisplay, fontWeight: 700,
      fontSize: size * 0.45, position: "relative", flexShrink: 0,
    }}>
      A
      <span style={{
        content: '""', position: "absolute",
        bottom: -1, right: -1, width: 10, height: 10, borderRadius: "50%",
        background: tok.green, border: "2px solid #FAFBFE",
      }}/>
    </div>
  );
}

function AtlasRailExpanded({ narration, onAsk, onCollapse }) {
  const paragraphs = narration?.paragraphs || [];
  const questions = narration?.suggested_questions || [];

  return (
    <div style={{
      padding: "24px 22px",
      display: "flex", flexDirection: "column", height: "100%",
      overflowY: "auto",
    }}>
      {/* Head */}
      <div style={{
        display: "flex", alignItems: "center", gap: 12,
        paddingBottom: 18, borderBottom: `1px solid ${tok.border}`,
        marginBottom: 20,
      }}>
        <AtlasAvatar />
        <div style={{ flex: 1 }}>
          <div style={{
            fontFamily: tok.fontDisplay, fontSize: 15, fontWeight: 600,
            letterSpacing: "-.01em", lineHeight: 1.1,
          }}>Atlas</div>
          <div style={{ fontSize: 11, color: tok.text3, marginTop: 2 }}>
            Your analyst · Online
          </div>
        </div>
        <button
          onClick={onCollapse}
          title="Collapse"
          style={{
            width: 28, height: 28, borderRadius: 6,
            background: "transparent", border: `1px solid ${tok.border}`,
            display: "flex", alignItems: "center", justifyContent: "center",
            cursor: "pointer", color: tok.text2, fontSize: 12,
            fontWeight: 700, fontFamily: tok.fontUi,
          }}
        >→</button>
      </div>

      {/* Narration */}
      <div style={{ marginBottom: 22, fontSize: 13, lineHeight: 1.6, color: tok.text }}>
        {paragraphs.map((p, i) => (
          <p key={i} style={{ marginBottom: 12 }}>{renderNarrationHighlights(p.text)}</p>
        ))}
      </div>

      {/* Suggested questions */}
      {questions.length > 0 && (
        <>
          <div style={{
            fontSize: 10, color: tok.text3,
            textTransform: "uppercase", letterSpacing: "0.18em",
            marginBottom: 10, fontWeight: 600,
          }}>Suggested questions</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: "auto" }}>
            {questions.map((q, i) => (
              <button
                key={i}
                onClick={() => onAsk && onAsk(q)}
                style={{
                  padding: "11px 14px",
                  background: tok.card, border: `1px solid ${tok.border}`,
                  borderRadius: 6, fontSize: 12, color: tok.text2,
                  cursor: "pointer", lineHeight: 1.4, textAlign: "left",
                  fontFamily: tok.fontUi,
                  transition: "all .2s",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = tok.atlas;
                  e.currentTarget.style.color = tok.text;
                  e.currentTarget.style.background = tok.atlasSoft;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = tok.border;
                  e.currentTarget.style.color = tok.text2;
                  e.currentTarget.style.background = tok.card;
                }}
              >
                <span style={{ color: tok.atlas, marginRight: 8, fontWeight: 700 }}>›</span>
                {q}
              </button>
            ))}
          </div>
        </>
      )}

      {/* Input box (non-functional placeholder in v1 — template-driven only) */}
      <div style={{
        marginTop: 18, paddingTop: 18,
        borderTop: `1px solid ${tok.border}`,
      }}>
        <div style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "10px 12px", background: tok.card,
          border: `1px solid ${tok.border}`, borderRadius: 8,
        }}>
          <input
            type="text"
            placeholder="Suggested questions only in v1"
            disabled
            style={{
              flex: 1, background: "transparent", border: "none", outline: "none",
              fontFamily: "inherit", fontSize: 12, color: tok.text3,
            }}
          />
          <span style={{ color: tok.text3, fontWeight: 700, fontSize: 14 }}>↵</span>
        </div>
      </div>
    </div>
  );
}

function AtlasRailCollapsed({ onExpand }) {
  return (
    <div style={{
      display: "flex", flexDirection: "column",
      alignItems: "center", gap: 14,
      padding: "24px 0", height: "100%",
    }}>
      <div onClick={onExpand} style={{ cursor: "pointer" }} title="Expand Atlas">
        <AtlasAvatar size={38} />
      </div>
      <div style={{
        writingMode: "vertical-rl", transform: "rotate(180deg)",
        fontSize: 10, color: tok.text3, textTransform: "uppercase",
        letterSpacing: "0.2em", fontWeight: 600, marginTop: 8,
      }}>Atlas</div>
      <button
        onClick={onExpand}
        title="Expand"
        style={{
          marginTop: "auto",
          width: 32, height: 32, borderRadius: 6,
          background: tok.card, border: `1px solid ${tok.border}`,
          display: "flex", alignItems: "center", justifyContent: "center",
          cursor: "pointer", color: tok.text2, fontSize: 14,
        }}
      >←</button>
    </div>
  );
}

export default function AtlasRail({ narration, collapsed, onToggle, onAsk }) {
  return (
    <aside style={{
      background: "#FAFBFE",
      borderLeft: `1px solid ${tok.border}`,
      position: "sticky", top: 0, height: "100vh",
      display: "flex", flexDirection: "column",
      overflow: "hidden",
      transition: "all .35s cubic-bezier(.4,0,.2,1)",
    }}>
      {collapsed
        ? <AtlasRailCollapsed onExpand={onToggle}/>
        : <AtlasRailExpanded narration={narration} onAsk={onAsk} onCollapse={onToggle}/>
      }
    </aside>
  );
}

/** Inline Atlas callout — shown inside the main flow when the rail is collapsed. */
export function AtlasInlineCallout({ narration }) {
  const first = narration?.paragraphs?.[0];
  if (!first) return null;
  return (
    <div style={{
      background: `linear-gradient(135deg, ${tok.atlasSoft}, #FEFAEC)`,
      border: "1px solid #F2D89A",
      borderLeft: `3px solid ${tok.atlas}`,
      borderRadius: 10,
      padding: "16px 20px",
      marginBottom: 18,
      display: "flex", alignItems: "flex-start", gap: 14,
    }}>
      <div style={{
        width: 32, height: 32, borderRadius: "50%",
        background: `linear-gradient(135deg, ${tok.atlas}, ${tok.atlasDeep})`,
        display: "flex", alignItems: "center", justifyContent: "center",
        color: "#fff", fontFamily: tok.fontDisplay, fontWeight: 700,
        fontSize: 14, flexShrink: 0,
      }}>A</div>
      <div style={{ flex: 1 }}>
        <div style={{
          fontFamily: tok.fontDisplay, fontWeight: 600, fontSize: 13,
          color: tok.atlasDeep, marginBottom: 4, fontStyle: "italic",
        }}>Atlas notes</div>
        <div style={{ fontSize: 13, color: tok.text, lineHeight: 1.55 }}>
          {renderNarrationHighlights(first.text)}
        </div>
      </div>
    </div>
  );
}

/** Bold monetary figures in Atlas narration text so they stand out. */
function renderNarrationHighlights(text) {
  if (!text) return null;
  // Match currency-formatted money across all supported currencies:
  //   USD/EUR/GBP: $/€/£ + digits + B/M/K suffix (or just digits for small amounts)
  //   INR:         ₹ + digits + Cr/L suffix
  // Also matches signed deltas (+$5.2M, −₹3.1 Cr) at word boundaries.
  const moneyRegex = /([+\u2212]?[$€£₹][\d,]+(?:\.\d+)?\s*(?:B|M|K|Cr|L)?)/g;
  const parts = text.split(moneyRegex);
  return parts.map((part, i) => {
    // A part is a match if it starts with a currency symbol (possibly
    // after a + or − sign) and contains digits.
    if (/^[+\u2212]?[$€£₹][\d,]+(?:\.\d+)?\s*(?:B|M|K|Cr|L)?$/.test(part)) {
      return <strong key={i} style={{ color: tok.atlasDeep, fontWeight: 600 }}>{part}</strong>;
    }
    return <React.Fragment key={i}>{part}</React.Fragment>;
  });
}
