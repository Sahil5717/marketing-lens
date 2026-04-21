import { useState, useEffect } from "react";
import styled from "styled-components";
import { t } from "../tokens.js";
import { login, fetchDemoUsers, getStoredAuth } from "../api.js";

/**
 * LoginScreen — rebuilt per mockup Image 1.
 *
 * Two-column layout:
 *   Left (dark, ~50% width on wide viewports): brand lockup at the top,
 *     tagline anchored toward vertical center ("Smarter media decisions.
 *     / Built on the evidence." — second line italic + accent serif),
 *     footer with copyright + legal links.
 *   Right (canvas background, ~50%): "Welcome back" serif heading,
 *     subhead, email/password form, forgot-password link, sign-in
 *     button, demo access row.
 *
 * At narrow viewports (<960px) the dark left panel collapses into a
 * short header strip and the form takes full width — login still works
 * on a tablet even if we don't design below 1024px elsewhere.
 *
 * Business logic preserved from LoginScreen.legacy.jsx:
 *   - Auto-redirect if already logged in
 *   - Fetch demo users on mount (backend returns empty list in prod)
 *   - Hard redirect by role after successful login (editor → /editor,
 *     client → /)
 *   - Inline error on failure, no toast
 */
export function LoginScreen() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [demoUsers, setDemoUsers] = useState([]);

  useEffect(() => {
    const auth = getStoredAuth();
    if (auth?.role) redirectByRole(auth.role);
  }, []);

  useEffect(() => {
    (async () => {
      const { data } = await fetchDemoUsers();
      if (data?.demo_users) setDemoUsers(data.demo_users);
    })();
  }, []);

  async function handleSubmit(e) {
    if (e) e.preventDefault();
    if (!username.trim() || !password) return;
    setErrorMsg(null);
    setSubmitting(true);
    const { data, error } = await login(username.trim(), password);
    setSubmitting(false);
    if (data) {
      redirectByRole(data.role);
    } else {
      setErrorMsg(
        error?.message === "Invalid username or password"
          ? "Email or password didn't match. Please try again."
          : error?.message || "Unable to sign in. Please try again."
      );
    }
  }

  function handleDemoClick(demo) {
    setUsername(demo.username);
    setPassword(demo.password);
  }

  return (
    <Root>
      {/* ── Left panel — dark, brand + tagline ── */}
      <Left>
        {/* Decorative response-curve pattern. Intentionally abstract —
            evokes the shape of a saturation curve without being literal.
            In-code SVG so zero copyright risk + scales cleanly. */}
        <LeftPattern aria-hidden="true">
          <svg
            viewBox="0 0 600 800"
            preserveAspectRatio="xMidYMid slice"
            xmlns="http://www.w3.org/2000/svg"
          >
            <defs>
              <linearGradient id="mlCurveGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="rgba(217, 119, 6, 0.35)" />
                <stop offset="100%" stopColor="rgba(217, 119, 6, 0.02)" />
              </linearGradient>
              <linearGradient id="mlCurveLine" x1="0%" y1="100%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="rgba(217, 119, 6, 0.6)" />
                <stop offset="100%" stopColor="rgba(217, 119, 6, 0.15)" />
              </linearGradient>
            </defs>
            {/* Main curve — diminishing-returns shape */}
            <path
              d="M 0 720 Q 120 620, 240 440 T 600 200"
              fill="none"
              stroke="url(#mlCurveLine)"
              strokeWidth="1.5"
            />
            {/* HDI-like shaded band above and below */}
            <path
              d="M 0 680 Q 140 560, 260 380 T 600 150 L 600 280 Q 280 440, 160 600 T 0 760 Z"
              fill="url(#mlCurveGrad)"
            />
            {/* Secondary dotted curve — different channel */}
            <path
              d="M 0 780 Q 180 700, 340 540 T 600 320"
              fill="none"
              stroke="rgba(255, 255, 255, 0.08)"
              strokeWidth="1"
              strokeDasharray="3 4"
            />
            {/* Data points scattered along the main curve */}
            {[
              [60, 705], [140, 615], [220, 470], [320, 365],
              [420, 290], [520, 235],
            ].map(([cx, cy], i) => (
              <circle
                key={i}
                cx={cx}
                cy={cy}
                r="3"
                fill="rgba(217, 119, 6, 0.55)"
              />
            ))}
          </svg>
        </LeftPattern>

        <LeftInner>
          <Brand>
            <BrandMark>M</BrandMark>
            <BrandWord>MarketLens</BrandWord>
          </Brand>

          <Tagline>
            Smarter media decisions.
            <TaglineAccent>Built on the evidence.</TaglineAccent>
          </Tagline>

          <FooterCopy>
            <span>© {new Date().getFullYear()} MarketLens</span>
            <FooterDot />
            <a href="#">Privacy</a>
            <FooterDot />
            <a href="#">Terms</a>
          </FooterCopy>
        </LeftInner>
      </Left>

      {/* ── Right panel — form ── */}
      <Right>
        <FormInner>
          <Welcome>Welcome back</Welcome>
          <Subhead>Sign in to view your media performance analysis.</Subhead>

          <Form onSubmit={handleSubmit}>
            <Field>
              <Label htmlFor="login-email">Work email</Label>
              <Input
                id="login-email"
                type="text"
                autoComplete="username"
                autoFocus
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="alex@acme.com"
                disabled={submitting}
                $hasError={!!errorMsg}
              />
            </Field>

            <Field>
              <Label htmlFor="login-password">Password</Label>
              <Input
                id="login-password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                disabled={submitting}
                $hasError={!!errorMsg}
              />
            </Field>

            {errorMsg && <ErrorRow role="alert">{errorMsg}</ErrorRow>}

            <FormRow>
              <ForgotLink href="#" tabIndex={submitting ? -1 : 0}>
                Forgot password?
              </ForgotLink>
              <SignInButton
                type="submit"
                disabled={submitting || !username.trim() || !password}
              >
                {submitting ? "Signing in…" : "Sign in →"}
              </SignInButton>
            </FormRow>
          </Form>

          {demoUsers.length > 0 && (
            <DemoSection>
              <DemoLabel>Demo access ·</DemoLabel>
              <DemoUsers>
                {demoUsers.map((u, i) => (
                  <span key={u.username}>
                    {i > 0 && <DemoSep />}
                    <DemoRole>{u.role}:</DemoRole>
                    <DemoButton
                      type="button"
                      onClick={() => handleDemoClick(u)}
                      disabled={submitting}
                    >
                      <code>{u.username}</code>
                      {" / "}
                      <code>{u.password}</code>
                    </DemoButton>
                  </span>
                ))}
              </DemoUsers>
            </DemoSection>
          )}
        </FormInner>
      </Right>
    </Root>
  );
}

function redirectByRole(role) {
  if (role === "editor" || role === "admin") window.location.href = "/editor";
  else window.location.href = "/";
}

// ─── Styled ───

const Root = styled.main`
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1fr 1fr;

  @media (max-width: 960px) {
    grid-template-columns: 1fr;
  }
`;

const Left = styled.aside`
  background:
    radial-gradient(circle at 30% 30%, rgba(180, 83, 9, 0.22), transparent 60%),
    ${t.color.dark};
  color: ${t.color.inkInverse};
  display: flex;
  flex-direction: column;
  padding: ${t.space[10]} ${t.space[12]};
  min-height: 100vh;
  position: relative;
  overflow: hidden;

  @media (max-width: 960px) {
    min-height: auto;
    padding: ${t.space[6]} ${t.space[8]};
  }
`;

const LeftPattern = styled.div`
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.9;

  svg {
    width: 100%;
    height: 100%;
    display: block;
  }

  @media (max-width: 960px) {
    opacity: 0.6;
  }
`;

const LeftInner = styled.div`
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  flex: 1;
  width: 100%;
  max-width: 520px;
  margin: 0 auto;
  position: relative;
  z-index: 1;

  @media (max-width: 960px) {
    gap: ${t.space[4]};
  }
`;

const Brand = styled.div`
  display: flex;
  align-items: baseline;
  gap: ${t.space[2]};
`;

const BrandMark = styled.span`
  font-family: ${t.font.serif};
  font-style: italic;
  font-size: 40px;
  color: ${t.color.accent};
  line-height: 1;
`;

const BrandWord = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.xl};
  font-weight: ${t.weight.semibold};
  color: ${t.color.inkInverse};
  letter-spacing: ${t.tracking.tight};
`;

const Tagline = styled.div`
  font-family: ${t.font.serif};
  font-size: clamp(28px, 3.6vw, 44px);
  font-weight: ${t.weight.regular};
  line-height: 1.2;
  letter-spacing: ${t.tracking.tightest};
  color: ${t.color.inkInverse};

  @media (max-width: 960px) {
    font-size: ${t.size.xl};
  }
`;

const TaglineAccent = styled.div`
  font-style: italic;
  color: ${t.color.accent};
  margin-top: ${t.space[1]};
`;

const FooterCopy = styled.div`
  display: flex;
  align-items: center;
  gap: ${t.space[3]};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink4};

  a {
    color: ${t.color.ink4};
    text-decoration: none;

    &:hover {
      color: ${t.color.inkInverse};
    }
  }

  @media (max-width: 960px) {
    display: none;
  }
`;

const FooterDot = styled.span`
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: ${t.color.ink4};
`;

const Right = styled.section`
  background: ${t.color.canvas};
  display: flex;
  align-items: center;
  justify-content: center;
  padding: ${t.space[10]};
  min-height: 100vh;

  @media (max-width: 960px) {
    min-height: auto;
    padding: ${t.space[8]} ${t.space[6]};
  }
`;

const FormInner = styled.div`
  width: 100%;
  max-width: 400px;
  display: flex;
  flex-direction: column;
  gap: ${t.space[6]};
`;

const Welcome = styled.h1`
  font-family: ${t.font.serif};
  font-size: clamp(32px, 3.6vw, 44px);
  font-weight: ${t.weight.regular};
  line-height: 1.1;
  letter-spacing: ${t.tracking.tightest};
  color: ${t.color.ink};
  margin: 0;
`;

const Subhead = styled.p`
  font-family: ${t.font.body};
  font-size: ${t.size.md};
  color: ${t.color.ink2};
  margin: -${t.space[4]} 0 0 0;
  line-height: ${t.leading.relaxed};
`;

const Form = styled.form`
  display: flex;
  flex-direction: column;
  gap: ${t.space[4]};
`;

const Field = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${t.space[2]};
`;

const Label = styled.label`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink3};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
`;

const Input = styled.input`
  padding: ${t.space[3]} ${t.space[4]};
  background: ${t.color.surface};
  border: 1px solid ${({ $hasError }) => $hasError ? t.color.negative : t.color.border};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.md};
  color: ${t.color.ink};
  transition: border-color ${t.motion.base} ${t.motion.ease};

  &:focus {
    border-color: ${t.color.accent};
    outline: none;
  }

  &::placeholder {
    color: ${t.color.ink4};
  }

  &:disabled {
    opacity: 0.7;
    cursor: wait;
  }
`;

const ErrorRow = styled.div`
  padding: ${t.space[3]} ${t.space[4]};
  background: ${t.color.negativeBg};
  border: 1px solid ${t.color.negative}33;
  border-radius: ${t.radius.sm};
  color: ${t.color.negative};
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
`;

const FormRow = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: ${t.space[4]};
  margin-top: ${t.space[2]};
`;

const ForgotLink = styled.a`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink3};
  text-decoration: none;

  &:hover {
    color: ${t.color.accent};
  }
`;

const SignInButton = styled.button`
  padding: ${t.space[3]} ${t.space[6]};
  background: ${t.color.dark};
  color: ${t.color.inkInverse};
  border: none;
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.md};
  font-weight: ${t.weight.semibold};
  cursor: pointer;
  transition: background ${t.motion.base} ${t.motion.ease};

  &:hover:not(:disabled) {
    background: ${t.color.darkSurface};
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const DemoSection = styled.div`
  padding-top: ${t.space[5]};
  border-top: 1px solid ${t.color.borderFaint};
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink3};
  line-height: ${t.leading.relaxed};
`;

const DemoLabel = styled.span`
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink2};
  margin-right: ${t.space[1]};
`;

const DemoUsers = styled.span`
  display: inline;
`;

const DemoSep = styled.span`
  display: inline-block;
  margin: 0 ${t.space[2]};
  color: ${t.color.ink4};

  &::before {
    content: "·";
  }
`;

const DemoRole = styled.span`
  margin-right: ${t.space[1]};
  color: ${t.color.ink2};
`;

const DemoButton = styled.button`
  display: inline;
  padding: 0;
  background: none;
  border: none;
  color: ${t.color.accent};
  cursor: pointer;
  font-family: inherit;
  font-size: inherit;

  code {
    font-family: ${t.font.mono};
    font-size: ${t.size.xs};
    background: ${t.color.sunken};
    padding: 1px ${t.space[1]};
    border-radius: ${t.radius.sm};
    color: ${t.color.ink};
  }

  &:hover:not(:disabled) code {
    background: ${t.color.accentSub};
  }

  &:disabled {
    opacity: 0.5;
    cursor: wait;
  }
`;
