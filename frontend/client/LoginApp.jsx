import { t } from "./tokens.js";
import { LoginScreen } from "./screens/LoginScreen.jsx";
import { GlobalStyle } from "./globalStyle.js";

/**
 * LoginApp — minimal shell for the /login route.
 *
 * Renders the login screen with the shared GlobalStyle so fonts load
 * consistently. No header, no footer — the login page is a focal
 * surface carrying its own two-column layout (dark brand panel + form).
 */
export default function LoginApp() {
  return (
    <div style={{ minHeight: "100vh", background: t.color.canvas, fontFamily: t.font.body }}>
      <GlobalStyle />
      <LoginScreen />
    </div>
  );
}
