import { useState, useEffect, useRef } from "react";
import { X, AlertTriangle } from "lucide-react";
import { tokens as t } from "../tokens.js";

/**
 * SuppressionModal — blocks-before-confirming-destructive-action pattern.
 *
 * Suppression removes a finding from the client view. Since this is
 * editorial content with audit-log implications, we require:
 *   - a non-empty reason (enforced at backend too)
 *   - an explicit click on "Hide from client"
 * Escape and backdrop-click cancel without committing.
 *
 * Render this at the DiagnosisApp level (not inside FindingCard) so it
 * overlays the whole surface and keyboard focus management is sane.
 */
export function SuppressionModal({ finding, onConfirm, onCancel, submitting = false }) {
  const [reason, setReason] = useState("");
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

  const trimmedReason = reason.trim();
  const canConfirm = trimmedReason.length >= 10 && !submitting;

  async function handleConfirm() {
    if (!canConfirm) return;
    setErrorMsg(null);
    const result = await onConfirm(trimmedReason);
    if (result?.error) {
      setErrorMsg(
        typeof result.error === "string"
          ? result.error
          : result.error.message || "Failed to suppress finding."
      );
    }
  }

  return (
    <div
      onClick={(e) => {
        // Backdrop click cancels (but not inner click)
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
          maxWidth: "560px",
          width: "100%",
          display: "flex",
          flexDirection: "column",
          animation: `modalSlideIn ${t.motion.slow} ${t.motion.ease}`,
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: `${t.space[5]} ${t.space[6]} ${t.space[4]}`,
            borderBottom: `1px solid ${t.color.borderFaint}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: t.space[4],
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: t.space[3] }}>
            <div
              style={{
                padding: t.space[2],
                background: t.color.warningBg,
                borderRadius: t.radius.sm,
                color: t.color.warning,
                display: "flex",
                alignItems: "center",
              }}
            >
              <AlertTriangle size={16} strokeWidth={2} />
            </div>
            <div>
              <div
                style={{
                  fontFamily: t.font.display,
                  fontSize: t.size.lg,
                  fontWeight: t.weight.semibold,
                  color: t.color.textPrimary,
                  letterSpacing: t.tracking.snug,
                  lineHeight: t.leading.tight,
                }}
              >
                Hide this finding from the client view?
              </div>
            </div>
          </div>
          <button
            onClick={onCancel}
            disabled={submitting}
            aria-label="Close"
            style={{
              background: "none",
              border: "none",
              color: t.color.textTertiary,
              cursor: submitting ? "not-allowed" : "pointer",
              padding: t.space[1],
              opacity: submitting ? 0.5 : 1,
              display: "flex",
              alignItems: "center",
            }}
          >
            <X size={18} strokeWidth={1.75} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: `${t.space[5]} ${t.space[6]}` }}>
          <div
            style={{
              background: t.color.surfaceSunken,
              border: `1px solid ${t.color.borderFaint}`,
              borderRadius: t.radius.sm,
              padding: `${t.space[3]} ${t.space[4]}`,
              marginBottom: t.space[5],
            }}
          >
            <div
              style={{
                fontFamily: t.font.body,
                fontSize: t.size.xs,
                fontWeight: t.weight.semibold,
                color: t.color.textTertiary,
                textTransform: "uppercase",
                letterSpacing: t.tracking.wider,
                marginBottom: t.space[1],
              }}
            >
              Finding
            </div>
            <div
              style={{
                fontFamily: t.font.display,
                fontSize: t.size.md,
                fontWeight: t.weight.medium,
                color: t.color.textPrimary,
                lineHeight: t.leading.snug,
              }}
            >
              {finding.headline}
            </div>
          </div>

          <label
            style={{
              display: "block",
              fontFamily: t.font.body,
              fontSize: t.size.sm,
              fontWeight: t.weight.medium,
              color: t.color.textPrimary,
              marginBottom: t.space[2],
            }}
          >
            Reason for hiding <span style={{ color: t.color.negative }}>*</span>
          </label>
          <div
            style={{
              fontFamily: t.font.body,
              fontSize: t.size.xs,
              color: t.color.textTertiary,
              lineHeight: t.leading.normal,
              marginBottom: t.space[3],
            }}
          >
            Required for audit. Stored with the engagement record; not shown to the client.
          </div>
          <textarea
            ref={textareaRef}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. Addressed separately in Q2 operational review; not relevant to this engagement's scope."
            rows={3}
            disabled={submitting}
            style={{
              width: "100%",
              minHeight: "72px",
              padding: t.space[3],
              border: `1px solid ${t.color.border}`,
              borderRadius: t.radius.sm,
              fontFamily: t.font.body,
              fontSize: t.size.md,
              lineHeight: t.leading.relaxed,
              color: t.color.textPrimary,
              background: t.color.canvas,
              resize: "vertical",
              outline: "none",
              transition: `border-color ${t.motion.fast} ${t.motion.ease}`,
            }}
            onFocus={(e) => { e.currentTarget.style.borderColor = t.color.accent; }}
            onBlur={(e) => { e.currentTarget.style.borderColor = t.color.border; }}
          />

          {errorMsg && (
            <div
              style={{
                marginTop: t.space[3],
                fontFamily: t.font.body,
                fontSize: t.size.sm,
                color: t.color.negative,
                background: t.color.negativeBg,
                padding: `${t.space[2]} ${t.space[3]}`,
                borderRadius: t.radius.sm,
              }}
            >
              {errorMsg}
            </div>
          )}

          {trimmedReason.length > 0 && trimmedReason.length < 10 && (
            <div
              style={{
                marginTop: t.space[2],
                fontFamily: t.font.body,
                fontSize: t.size.xs,
                color: t.color.textTertiary,
              }}
            >
              Please write at least 10 characters so this is meaningful in the audit log.
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: `${t.space[4]} ${t.space[6]} ${t.space[5]}`,
            borderTop: `1px solid ${t.color.borderFaint}`,
            background: t.color.sunken,
            display: "flex",
            justifyContent: "flex-end",
            gap: t.space[2],
          }}
        >
          <button onClick={onCancel} disabled={submitting} style={footerButtonStyle("ghost", submitting)}>
            Cancel
          </button>
          <button onClick={handleConfirm} disabled={!canConfirm} style={footerButtonStyle("warning", !canConfirm)}>
            {submitting ? "Hiding…" : "Hide from client"}
          </button>
        </div>
      </div>
    </div>
  );
}

function footerButtonStyle(variant, disabled) {
  const base = {
    padding: `${t.space[2]} ${t.space[4]}`,
    fontFamily: t.font.body,
    fontSize: t.size.sm,
    fontWeight: t.weight.medium,
    borderRadius: t.radius.sm,
    cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.5 : 1,
    border: `1px solid transparent`,
  };
  if (variant === "warning") {
    return {
      ...base,
      background: t.color.warning,
      color: t.color.textInverse,
    };
  }
  return {
    ...base,
    background: t.color.surface,
    color: t.color.textSecondary,
    borderColor: t.color.border,
  };
}
