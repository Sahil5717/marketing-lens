import { useState, useEffect, useRef } from "react";
import { t } from "../tokens.js";

/**
 * CommentaryModal — editor's-note editor for findings and moves.
 *
 * Pops up when an editor clicks "Add note" / "Edit note" on a
 * FindingCard or MoveCard in editor mode. Mirrors SuppressionModal's
 * pattern (backdrop + escape + focus trap) but the action is
 * non-destructive so there's no "you sure?" framing.
 *
 * Pre-populates with existing commentary if present. On save the
 * parent persists via /api/editor/commentary; on delete the parent
 * persists the deletion. Both actions close the modal on success.
 *
 * Kept in `components/` (legacy directory) rather than `ui/` to signal
 * that this is an editor-mode add-on rather than a primitive of the
 * core design system. Will be rebuilt in styled-components alongside
 * the Toast and SuppressionModal rewrite.
 */
export function CommentaryModal({
  target,           // finding or move object — used for context display
  existingText = "",
  onSave,           // (text) => {ok?, error?}
  onDelete,         // () => {ok?, error?}  — only called if existingText
  onCancel,
  submitting = false,
}) {
  const [text, setText] = useState(existingText || "");
  const [errorMsg, setErrorMsg] = useState(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    const id = setTimeout(() => textareaRef.current?.focus(), 80);
    return () => clearTimeout(id);
  }, []);

  useEffect(() => {
    function handleEsc(e) {
      if (e.key === "Escape" && !submitting) onCancel?.();
    }
    document.addEventListener("keydown", handleEsc);
    return () => document.removeEventListener("keydown", handleEsc);
  }, [onCancel, submitting]);

  const trimmed = text.trim();
  const canSave = trimmed.length > 0 && !submitting && trimmed !== existingText.trim();
  const isEditing = !!existingText;

  async function handleSave() {
    if (!canSave) return;
    setErrorMsg(null);
    const result = await onSave?.(trimmed);
    if (result?.error) {
      setErrorMsg(
        typeof result.error === "string"
          ? result.error
          : result.error.message || "Failed to save commentary."
      );
    }
  }

  async function handleDelete() {
    if (submitting || !isEditing) return;
    setErrorMsg(null);
    const result = await onDelete?.();
    if (result?.error) {
      setErrorMsg(
        typeof result.error === "string"
          ? result.error
          : result.error.message || "Failed to delete commentary."
      );
    }
  }

  // Extract a human-readable title for the modal context line
  const contextLabel =
    target?.headline ||
    target?.channel_display ||
    (target?.channel ? target.channel.replaceAll("_", " ") : "finding");

  return (
    <div
      onClick={(e) => {
        if (e.target === e.currentTarget && !submitting) onCancel?.();
      }}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(10, 10, 10, 0.4)",
        backdropFilter: "blur(4px)",
        WebkitBackdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 100,
        padding: t.space[6],
        animation: `modalFadeIn ${t.motion.base} ${t.motion.ease}`,
      }}
    >
      <div
        style={{
          background: t.color.surface,
          borderRadius: t.radius.lg,
          boxShadow: "0 24px 48px rgba(10, 10, 10, 0.16), 0 2px 8px rgba(10, 10, 10, 0.06)",
          maxWidth: "580px",
          width: "100%",
          display: "flex",
          flexDirection: "column",
          animation: `modalSlideIn ${t.motion.slow} ${t.motion.ease}`,
        }}
      >
        {/* Header */}
        <div style={{ padding: `${t.space[5]} ${t.space[6]} 0` }}>
          <div style={{
            fontFamily: t.font.body,
            fontSize: t.size.xs,
            fontWeight: t.weight.semibold,
            color: t.color.ink3,
            textTransform: "uppercase",
            letterSpacing: t.tracking.wider,
            marginBottom: t.space[2],
          }}>
            Editor's note · {isEditing ? "Edit" : "Add"}
          </div>
          <h2 style={{
            fontFamily: t.font.serif,
            fontSize: t.size.xl,
            fontWeight: t.weight.regular,
            color: t.color.ink,
            margin: 0,
            letterSpacing: t.tracking.tight,
          }}>
            {contextLabel}
          </h2>
          <p style={{
            fontFamily: t.font.body,
            fontSize: t.size.sm,
            color: t.color.ink3,
            margin: `${t.space[2]} 0 0 0`,
            lineHeight: t.leading.relaxed,
          }}>
            This note appears alongside the finding in the client view.
            Keep it short and specific — it's what the client reads after
            the automated narrative.
          </p>
        </div>

        {/* Editor */}
        <div style={{ padding: `${t.space[4]} ${t.space[6]}` }}>
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={submitting}
            placeholder="e.g. We observed this pattern in the Q3 data — caution on acting before the holiday season."
            style={{
              width: "100%",
              minHeight: 120,
              padding: `${t.space[3]} ${t.space[4]}`,
              background: t.color.surface,
              border: `1px solid ${errorMsg ? t.color.negative : t.color.border}`,
              borderRadius: t.radius.sm,
              fontFamily: t.font.body,
              fontSize: t.size.md,
              color: t.color.ink,
              resize: "vertical",
              outline: "none",
            }}
          />
          {errorMsg && (
            <div style={{
              marginTop: t.space[2],
              padding: `${t.space[2]} ${t.space[3]}`,
              background: t.color.negativeBg,
              color: t.color.negative,
              borderRadius: t.radius.sm,
              fontFamily: t.font.body,
              fontSize: t.size.sm,
            }}>
              {errorMsg}
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: `${t.space[4]} ${t.space[6]} ${t.space[5]}`,
          borderTop: `1px solid ${t.color.borderFaint}`,
          background: t.color.sunken,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: t.space[3],
        }}>
          {/* Delete on left — only if editing existing note */}
          <div>
            {isEditing && (
              <button
                onClick={handleDelete}
                disabled={submitting}
                style={{
                  padding: `${t.space[2]} ${t.space[3]}`,
                  background: "transparent",
                  color: t.color.negative,
                  border: `1px solid transparent`,
                  borderRadius: t.radius.sm,
                  fontFamily: t.font.body,
                  fontSize: t.size.sm,
                  fontWeight: t.weight.medium,
                  cursor: submitting ? "wait" : "pointer",
                  opacity: submitting ? 0.5 : 1,
                }}
              >
                Delete note
              </button>
            )}
          </div>

          {/* Cancel + Save on right */}
          <div style={{ display: "flex", gap: t.space[2] }}>
            <button
              onClick={onCancel}
              disabled={submitting}
              style={{
                padding: `${t.space[2]} ${t.space[4]}`,
                background: "transparent",
                color: t.color.ink2,
                border: `1px solid ${t.color.border}`,
                borderRadius: t.radius.sm,
                fontFamily: t.font.body,
                fontSize: t.size.sm,
                fontWeight: t.weight.medium,
                cursor: submitting ? "wait" : "pointer",
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={!canSave}
              style={{
                padding: `${t.space[2]} ${t.space[5]}`,
                background: canSave ? t.color.dark : t.color.ink4,
                color: t.color.inkInverse,
                border: "none",
                borderRadius: t.radius.sm,
                fontFamily: t.font.body,
                fontSize: t.size.sm,
                fontWeight: t.weight.semibold,
                cursor: canSave ? "pointer" : "not-allowed",
              }}
            >
              {submitting ? "Saving…" : isEditing ? "Save changes" : "Add note"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
