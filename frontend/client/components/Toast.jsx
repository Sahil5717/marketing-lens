import { useEffect } from "react";
import { CheckCircle2, AlertTriangle, X } from "lucide-react";
import { tokens as t } from "../tokens.js";

/**
 * Toast — transient notification for save success and error feedback.
 *
 * Auto-dismisses after 3 seconds for success, 6 seconds for errors
 * (errors need more time to read). Can be dismissed manually via the
 * X button. No stacking yet — the editor app shows one toast at a time;
 * a second toast replaces the first.
 *
 * Render at the app level, not inside components, so it overlays
 * regardless of scroll position.
 */
export function Toast({ message, kind = "success", onDismiss }) {
  useEffect(() => {
    const timeout = kind === "error" ? 6000 : 3000;
    const id = setTimeout(() => onDismiss?.(), timeout);
    return () => clearTimeout(id);
  }, [message, kind, onDismiss]);

  const config =
    kind === "error"
      ? {
          icon: <AlertTriangle size={16} strokeWidth={2} />,
          bg: t.color.negativeBg,
          fg: t.color.negative,
          border: t.color.negative,
        }
      : {
          icon: <CheckCircle2 size={16} strokeWidth={2} />,
          bg: t.color.positiveBg,
          fg: t.color.positive,
          border: t.color.positive,
        };

  return (
    <div
      style={{
        position: "fixed",
        bottom: t.space[6],
        right: t.space[6],
        zIndex: 200,
        display: "flex",
        alignItems: "center",
        gap: t.space[3],
        padding: `${t.space[3]} ${t.space[4]}`,
        background: t.color.surface,
        border: `1px solid ${config.border}40`,
        borderLeft: `3px solid ${config.border}`,
        borderRadius: t.radius.md,
        boxShadow: "0 8px 24px rgba(10, 10, 10, 0.12)",
        maxWidth: "420px",
        animation: `toastSlideIn ${t.motion.base} ${t.motion.ease}`,
      }}
      role="status"
      aria-live="polite"
    >
      <div style={{ color: config.fg, display: "flex" }}>{config.icon}</div>
      <div
        style={{
          flex: 1,
          fontFamily: t.font.body,
          fontSize: t.size.sm,
          fontWeight: t.weight.medium,
          color: t.color.textPrimary,
          lineHeight: t.leading.snug,
        }}
      >
        {message}
      </div>
      <button
        onClick={onDismiss}
        aria-label="Dismiss"
        style={{
          background: "none",
          border: "none",
          padding: t.space[1],
          cursor: "pointer",
          color: t.color.textTertiary,
          display: "flex",
        }}
      >
        <X size={14} strokeWidth={1.75} />
      </button>
    </div>
  );
}
