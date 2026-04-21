import styled, { css } from "styled-components";
import { t } from "../tokens.js";

/**
 * AppHeader — sticky top nav across all main app screens.
 *
 * Per mockup (marketlens-mockups.html) and handoff §5 (AppHeader spec):
 *   - 60px fixed height, sticks to top on scroll
 *   - Brand lockup on the far left: serif italic 'M' in accent + sans
 *     'MarketLens' wordmark
 *   - Center: horizontal nav with pill-style active state (dark fill)
 *   - Right: engagement metadata (client name · period) + Share button
 *   - Editor-mode variant: subtle amber tint on background + '✎ Editor
 *     mode' indicator
 *
 * Currently drives the ?screen= URL-param pattern for routing. When we
 * promote to client-side routing (post-v1), the `href` on NavItem becomes
 * a router Link, but the visual API stays the same.
 */

export function AppHeader({
  currentScreen = "diagnosis",
  auth,
  editorMode = false,
  engagementMeta,
  bayesStatus,       // { state, message, elapsed_s, r_hat_max, ess_min } — editor mode only
  onBayesRefresh,    // callback to trigger /api/bayes-refit
  onSignOut,
  onShare,
}) {
  return (
    <HeaderBar $editor={editorMode}>
      <Inner $editor={editorMode}>
        <BrandNav>
          <Brand href={editorMode ? "/editor" : "/"}>
            <BrandMark>M</BrandMark>
            <BrandWord>MarketLens</BrandWord>
          </Brand>

          <Nav>
            {editorMode && (
              <NavItem screen="engagements" current={currentScreen} label="Engagements" />
            )}
            {editorMode && (
              <NavItem screen="hub" current={currentScreen} label="Workspace" />
            )}
            <NavItem screen="diagnosis" current={currentScreen} label="Diagnosis" />
            <NavItem screen="plan" current={currentScreen} label="Plan" />
            <NavItem screen="scenarios" current={currentScreen} label="Scenarios" />
            <NavItem screen="channels" current={currentScreen} label="Channels" />
            <NavItem screen="market" current={currentScreen} label="Market" />
          </Nav>
        </BrandNav>

        <MetaGroup>
          {editorMode && <EditorBadge>✎ Editor mode</EditorBadge>}
          {editorMode && bayesStatus && (
            <MmmChip status={bayesStatus} onRefresh={onBayesRefresh} />
          )}
          {engagementMeta && (
            <Engagement>
              <strong>{engagementMeta.client}</strong>
              <Sep>·</Sep>
              <span>{engagementMeta.period}</span>
              {engagementMeta.updated && (
                <>
                  <VBar />
                  <span>Updated {engagementMeta.updated}</span>
                </>
              )}
            </Engagement>
          )}
          {onShare && <ShareButton onClick={onShare}>Share ↗</ShareButton>}
          {auth && <UserChip auth={auth} onSignOut={onSignOut} />}
        </MetaGroup>
      </Inner>
    </HeaderBar>
  );
}

function NavItem({ screen, current, label }) {
  const isActive = current === screen;
  return (
    <NavLink href={`?screen=${screen}`} $active={isActive}>
      {label}
    </NavLink>
  );
}

function UserChip({ auth, onSignOut }) {
  return (
    <UserChipWrap>
      <UserName>{auth.username}</UserName>
      <UserRole>{auth.role}</UserRole>
      <SignOutLink onClick={onSignOut}>Sign out</SignOutLink>
    </UserChipWrap>
  );
}

/**
 * MmmChip — always visible in editor mode. Communicates which MMM method
 * is currently backing the numbers in the UI.
 *
 * State semantics:
 *   idle        → "Bayesian MMM queued" (before first run-analysis)
 *   pending     → "Bayesian MMM queued"
 *   running     → "Bayesian running · {elapsed}s" with spinner
 *   ready       → "Bayesian ready · r̂ {r_hat}" with green dot; clicking refreshes
 *   non_converged → "Bayesian did not converge" (muted warning)
 *   failed      → "Bayesian fit failed" (red warning)
 *
 * In any non-ready state, the UI falls back to frequentist results.
 * The chip is the user's honest signal about which model they're seeing.
 */
function MmmChip({ status, onRefresh }) {
  const state = status?.state || "idle";
  const isRunning = state === "pending" || state === "running";
  const isReady = state === "ready";
  const isFailed = state === "failed";
  const isNonConv = state === "non_converged";

  let label;
  if (isReady) {
    const rhat = status.r_hat_max != null ? status.r_hat_max.toFixed(2) : "—";
    label = `Bayesian ready · r̂ ${rhat}`;
  } else if (isRunning) {
    const elapsed = status.elapsed_s != null
      ? `${Math.round(status.elapsed_s)}s`
      : status.state === "running" ? "sampling…" : "queued";
    label = `Bayesian ${elapsed}`;
  } else if (isFailed) {
    label = "Bayesian fit failed";
  } else if (isNonConv) {
    label = "Bayesian did not converge";
  } else {
    label = "Bayesian MMM queued";
  }

  const clickable = isReady && typeof onRefresh === "function";
  const methodologyNote =
    "PyMC NUTS · 6 channels · adstock + Hill saturation · 300 draws × 2 chains · converged at r-hat < 1.05";
  const tooltip = isReady
    ? `${status.message || ""}\n${methodologyNote}\nClick to re-run`
    : isRunning
      ? `${status.message || ""}\n${methodologyNote}`
      : status?.message || "Bayesian MMM status";
  return (
    <MmmChipWrap
      $state={state}
      $clickable={clickable}
      onClick={clickable ? onRefresh : undefined}
      title={tooltip}
    >
      <MmmChipDot $state={state} />
      <MmmChipLabel>{label}</MmmChipLabel>
    </MmmChipWrap>
  );
}

// ─── Styled components ───

const HeaderBar = styled.header`
  position: sticky;
  top: 0;
  z-index: ${t.z.sticky};
  background: ${({ $editor }) => ($editor ? t.color.accentSub : `${t.color.canvas}F2`)};
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-bottom: 1px solid ${t.color.borderFaint};

  /* Editor mode has 7-8 discrete header pieces (Workspace nav + 4 analysis
     nav items + Editor badge + engagement meta + Share + user chip + sign
     out) — way too many for one row below ~1600px. Strategy: in editor
     mode, always split to two rows (BrandNav on top, MetaGroup below).
     Client mode has less chrome and fits one row on any reasonable desktop. */
  height: ${({ $editor }) => ($editor ? "auto" : t.layout.headerHeight)};
  min-height: ${t.layout.headerHeight};

  /* Client mode: only wrap at narrow viewports (<1200px). */
  @media (max-width: 1199px) {
    height: auto;
  }
`;

const Inner = styled.div`
  max-width: ${t.layout.maxWidth};
  margin: 0 auto;
  padding: ${({ $editor }) => ($editor ? `${t.space[2]} ${t.layout.pad.wide}` : `0 ${t.layout.pad.wide}`)};
  height: ${({ $editor }) => ($editor ? "auto" : "100%")};
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: ${t.space[4]};
  min-width: 0;

  /* Editor mode: always stacked as two rows.
     Client mode: single row until it overflows. */
  flex-wrap: ${({ $editor }) => ($editor ? "wrap" : "nowrap")};
  row-gap: ${t.space[2]};

  @media (max-width: 1199px) {
    flex-wrap: wrap;
    padding-top: ${t.space[2]};
    padding-bottom: ${t.space[2]};
    height: auto;
  }

  @media (max-width: ${t.layout.bp.wide}) {
    padding-left: ${t.layout.pad.narrow};
    padding-right: ${t.layout.pad.narrow};
  }
`;

const BrandNav = styled.div`
  display: flex;
  align-items: center;
  gap: ${t.space[8]};
  flex-shrink: 0;  /* nav items never compress */
  min-width: 0;
`;

const Brand = styled.a`
  display: flex;
  align-items: baseline;
  gap: ${t.space[2]};
  text-decoration: none;
  color: ${t.color.ink};
`;

const BrandMark = styled.span`
  font-family: ${t.font.serif};
  font-style: italic;
  font-size: ${t.size.xl};
  color: ${t.color.accent};
  line-height: 1;
`;

const BrandWord = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.md};
  font-weight: ${t.weight.semibold};
  color: ${t.color.ink};
  letter-spacing: ${t.tracking.tight};
`;

const Nav = styled.nav`
  display: flex;
  align-items: center;
  gap: ${t.space[1]};
  flex-wrap: wrap;  /* allow nav to wrap if truly tiny viewport, but items themselves never shrink */
`;

const NavLink = styled.a`
  display: inline-flex;
  align-items: center;
  padding: ${t.space[2]} ${t.space[3]};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.base};
  font-weight: ${t.weight.medium};
  text-decoration: none;
  white-space: nowrap;
  flex-shrink: 0;
  transition: background ${t.motion.base} ${t.motion.ease}, color ${t.motion.base} ${t.motion.ease};

  ${({ $active }) =>
    $active
      ? css`
          background: ${t.color.dark};
          color: ${t.color.inkInverse};
          font-weight: ${t.weight.semibold};

          &:hover {
            background: ${t.color.dark};
          }
        `
      : css`
          background: transparent;
          color: ${t.color.ink2};

          &:hover {
            background: ${t.color.sunken};
            color: ${t.color.ink};
          }
        `}
`;

const MetaGroup = styled.div`
  display: flex;
  align-items: center;
  gap: ${t.space[4]};
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  color: ${t.color.ink2};
  min-width: 0;
  flex-wrap: wrap;
  row-gap: ${t.space[2]};
`;

const EditorBadge = styled.span`
  display: inline-flex;
  align-items: center;
  padding: ${t.space[1]} ${t.space[2]};
  border-radius: ${t.radius.sm};
  background: ${t.color.accentSub};
  color: ${t.color.accentInk};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  letter-spacing: ${t.tracking.wider};
  white-space: nowrap;   /* "Editor mode" never wraps */
  flex-shrink: 0;
`;

const Engagement = styled.div`
  display: inline-flex;
  align-items: center;
  gap: ${t.space[2]};
  font-size: ${t.size.sm};
  color: ${t.color.ink2};
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;

  strong {
    font-weight: ${t.weight.semibold};
    color: ${t.color.ink};
  }
`;

const Sep = styled.span`
  color: ${t.color.ink4};
`;

const VBar = styled.span`
  display: inline-block;
  width: 1px;
  height: 14px;
  background: ${t.color.border};
  margin: 0 ${t.space[2]};
`;

const ShareButton = styled.button`
  display: inline-flex;
  align-items: center;
  padding: ${t.space[2]} ${t.space[3]};
  background: ${t.color.surface};
  color: ${t.color.ink};
  border: 1px solid ${t.color.border};
  border-radius: ${t.radius.sm};
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.medium};
  cursor: pointer;
  transition: background ${t.motion.base} ${t.motion.ease}, border-color ${t.motion.base} ${t.motion.ease};

  &:hover {
    background: ${t.color.sunken};
    border-color: ${t.color.borderStrong};
  }
`;

const UserChipWrap = styled.div`
  display: flex;
  align-items: center;
  gap: ${t.space[2]};
  padding-left: ${t.space[3]};
  border-left: 1px solid ${t.color.borderFaint};
  flex-shrink: 0;
  white-space: nowrap;
`;

const UserName = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.sm};
  font-weight: ${t.weight.medium};
  color: ${t.color.ink};
  white-space: nowrap;
`;

const UserRole = styled.span`
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.ink3};
  text-transform: uppercase;
  letter-spacing: ${t.tracking.wider};
  font-weight: ${t.weight.semibold};
  white-space: nowrap;
`;

const SignOutLink = styled.button`
  background: none;
  border: none;
  padding: 0;
  margin-left: ${t.space[2]};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  color: ${t.color.accent};
  font-weight: ${t.weight.medium};
  cursor: pointer;
  white-space: nowrap;

  &:hover {
    color: ${t.color.accentHover};
  }
`;

// ─── MMM chip ───

const MmmChipWrap = styled.button`
  display: inline-flex;
  align-items: center;
  gap: ${t.space[2]};
  padding: 3px ${t.space[3]};
  border-radius: ${t.radius.sm};
  border: 1px solid ${({ $state }) => {
    if ($state === "ready") return t.color.positive;
    if ($state === "failed") return t.color.negative;
    if ($state === "non_converged") return t.color.border;
    if ($state === "running" || $state === "pending") return t.color.accent;
    return t.color.border;
  }};
  background: ${({ $state }) => {
    if ($state === "ready") return t.color.positiveBg;
    if ($state === "failed") return t.color.negativeBg;
    if ($state === "non_converged") return t.color.sunken;
    if ($state === "running" || $state === "pending") return t.color.accentSub;
    return t.color.sunken;
  }};
  font-family: ${t.font.body};
  font-size: ${t.size.xs};
  font-weight: ${t.weight.semibold};
  color: ${({ $state }) => {
    if ($state === "ready") return t.color.positive;
    if ($state === "failed") return t.color.negative;
    if ($state === "non_converged") return t.color.ink3;
    if ($state === "running" || $state === "pending") return t.color.accentInk;
    return t.color.ink3;
  }};
  cursor: ${({ $clickable }) => ($clickable ? "pointer" : "default")};
  white-space: nowrap;
  transition: filter ${t.motion.base} ${t.motion.ease};
  flex-shrink: 0;

  &:hover {
    filter: ${({ $clickable }) => ($clickable ? "brightness(0.96)" : "none")};
  }
`;

const MmmChipDot = styled.span`
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: ${({ $state }) => {
    if ($state === "ready") return t.color.positive;
    if ($state === "failed") return t.color.negative;
    if ($state === "non_converged") return t.color.ink4;
    return t.color.accent;
  }};
  flex-shrink: 0;

  ${({ $state }) =>
    ($state === "running" || $state === "pending") &&
    `
    animation: mmmPulse 1.2s ease-in-out infinite;

    @keyframes mmmPulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.5; transform: scale(1.25); }
    }
  `}
`;

const MmmChipLabel = styled.span`
  font-variant-numeric: tabular-nums;
`;
