/**
 * Design tokens for the macro-context panels.
 *
 * Mirrors the `:root` block in the hybrid screen HTMLs. Kept as a plain
 * JS object rather than tied to the codebase's tokens.js so the
 * components drop cleanly into either the current app or a fresh
 * Vite rebuild. When the real token system lands, swap this file for
 * an import.
 */
export const tok = {
  // Surface
  card:       "#FFFFFF",
  bg:         "#F5F6FA",
  border:     "#E5E7EF",
  border2:    "#D8DCE8",

  // Text
  text:       "#0F1535",
  text2:      "#5C6280",
  text3:      "#8C92AC",

  // Accent
  accent:     "#7C5CFF",
  accentSoft: "#EFEAFF",
  accentDeep: "#5B3FD9",

  // Semantic
  green:      "#10B981",
  greenSoft:  "#E6F8F2",
  red:        "#EF4444",
  redSoft:    "#FEE9E9",
  amber:      "#F59E0B",
  amberSoft:  "#FEF3D7",

  // Atlas (reasoning blocks)
  atlas:      "#B8893B",
  atlasSoft:  "#FBF3E0",
  atlasDeep:  "#8C6520",

  // Fonts
  fontUi:      "'Plus Jakarta Sans', system-ui, sans-serif",
  fontDisplay: "'Fraunces', serif",
};

/** Panel card shell — used by both panels to stay consistent. */
export const panelStyle = {
  background: tok.card,
  border: `1px solid ${tok.border}`,
  borderRadius: 12,
  padding: "18px 20px",
  fontFamily: tok.fontUi,
  color: tok.text,
  fontSize: 13,
  lineHeight: 1.5,
};

export const panelHeadingStyle = {
  fontSize: 13,
  fontWeight: 700,
  marginBottom: 4,
  display: "flex",
  alignItems: "center",
  gap: 8,
};

export const panelTagStyle = {
  fontSize: 10,
  color: tok.text3,
  fontWeight: 500,
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  marginBottom: 14,
};
