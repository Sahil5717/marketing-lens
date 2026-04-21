/**
 * Shared design tokens for the Yield Intelligence frontend.
 *
 * Mirrors the `:root` block in the hybrid screen HTMLs. Any new screen
 * imports from here rather than redefining. When the fresh Vite rebuild
 * lands, this file moves to `src/design/tokens.ts` with types added.
 */
export const tok = {
  // Surface
  bg:         "#F5F6FA",
  card:       "#FFFFFF",
  sidebar:    "#0F1535",
  sidebarHover: "#1A2150",
  border:     "#E5E7EF",
  border2:    "#D8DCE8",

  // Text
  text:       "#0F1535",
  text2:      "#5C6280",
  text3:      "#8C92AC",

  // Brand accent
  accent:     "#7C5CFF",
  accentSoft: "#EFEAFF",
  accentDeep: "#5B3FD9",

  // Semantic
  green:      "#10B981",
  greenSoft:  "#E6F8F2",
  greenDeep:  "#047857",
  red:        "#EF4444",
  redSoft:    "#FEE9E9",
  redDeep:    "#B91C1C",
  amber:      "#F59E0B",
  amberSoft:  "#FEF3D7",
  amberDeep:  "#92400E",

  // Atlas persona
  atlas:      "#B8893B",
  atlasSoft:  "#FBF3E0",
  atlasDeep:  "#8C6520",

  // Hero gradient stops
  heroFrom:   "#0F1535",
  heroTo:     "#1E2456",
  heroNum:    "#FF8B7A",   // loss — coral italic in headline
  heroGain:   "#7BE0BC",   // gain — mint italic in headline
  heroEyebrow:"#FFB547",

  // Fonts
  fontUi:      "'Plus Jakarta Sans', system-ui, sans-serif",
  fontDisplay: "'Fraunces', serif",
};

/** Standard card surface used across screens. */
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

/** Inline "Atlas reasoning" callout — gold-soft box with left border. */
export const atlasCalloutStyle = {
  background: tok.atlasSoft,
  borderLeft: `3px solid ${tok.atlas}`,
  borderRadius: 6,
  padding: "12px 16px",
  fontSize: 12,
  color: tok.text,
  lineHeight: 1.6,
};

/** Fonts link tag — consumers render this in their document head. */
export const FONTS_HREF =
  "https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap";
