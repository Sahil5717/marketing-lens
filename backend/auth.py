"""
Authentication — JWT + RBAC
=============================
Provides register, login, token validation, and role-based access control
for MarketLens.

Role model (v18e):
    editor  — EY analysts curating the deliverable. Full edit access:
              commentary, suppression, rewrite, audit log. This is the
              role for anyone working IN the tool.
    client  — Client executives and analysts consuming the published
              deliverable. Read-only; sees only the client-view output
              (suppressed findings filtered, commentary rendered as
              "EY's Take").

Two earlier roles (admin / analyst / viewer) in the legacy analyst
workbench are preserved through backward-compatible permission mapping
so the existing analyst app continues to function without modification.

Demo accounts seeded on first boot via `seed_demo_users()` — see module
bottom. Four accounts, two per role, so the login screen has recognizable
credentials to demo with.
"""
import os
import time
from typing import Optional, Dict
from jose import jwt, JWTError
from passlib.hash import bcrypt
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from persistence import create_user, get_user, get_user_by_id
import logging
logger = logging.getLogger(__name__)

SECRET_KEY = os.environ.get("JWT_SECRET", "yield-intelligence-dev-secret-change-in-production")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

security = HTTPBearer(auto_error=False)

# New MarketLens roles + legacy analyst workbench roles.
# The legacy roles stay in the map so the existing analyst app continues
# to accept its own tokens; they're not exposed on the login screen for
# MarketLens users.
ROLE_PERMISSIONS = {
    # MarketLens roles (v18e+)
    "editor": {"read", "edit_commentary", "edit_suppression", "edit_rewrite",
               "view_audit_log", "view_editor_mode", "view_client_mode"},
    "client": {"read", "view_client_mode"},

    # Legacy analyst workbench roles (preserved for backward compat)
    "admin": {"read", "write", "optimize", "upload", "export", "manage_users", "scenarios"},
    "analyst": {"read", "write", "optimize", "upload", "export", "scenarios"},
    "viewer": {"read", "export"},
}


def hash_password(password: str) -> str:
    return bcrypt.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.verify(password, password_hash)


def create_token(user_id: int, username: str, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": time.time() + TOKEN_EXPIRE_HOURS * 3600,
        "iat": time.time(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("exp", 0) < time.time():
            raise HTTPException(401, "Token expired")
        return payload
    except JWTError:
        raise HTTPException(401, "Invalid token")


def register_user(username: str, password: str, role: str = "client") -> Dict:
    """Register a new user."""
    if len(password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    if role not in ROLE_PERMISSIONS:
        raise HTTPException(400, f"Invalid role. Must be one of: {list(ROLE_PERMISSIONS.keys())}")
    try:
        user_id = create_user(username, hash_password(password), role)
    except ValueError as e:
        raise HTTPException(409, str(e))
    token = create_token(user_id, username, role)
    return {"user_id": user_id, "username": username, "role": role, "token": token}


def login_user(username: str, password: str) -> Dict:
    """Authenticate and return JWT."""
    user = get_user(username)
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    token = create_token(user["id"], user["username"], user["role"])
    return {"user_id": user["id"], "username": user["username"], "role": user["role"], "token": token}


async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[Dict]:
    """Extract user from JWT token. Returns None if no auth header (anonymous mode)."""
    if credentials is None:
        return None
    payload = decode_token(credentials.credentials)
    user = get_user_by_id(int(payload["sub"]))
    if not user:
        raise HTTPException(401, "User not found")
    return user


def require_role(*roles):
    """
    FastAPI dependency that asserts the caller's JWT has one of the
    specified roles. Used to protect the /api/editor/* endpoints so only
    `editor`-role tokens can mutate overlay state.

    If the caller has no token, raises 401. If they have a token with the
    wrong role, raises 403 with a message naming the required role.
    """
    async def checker(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
        if credentials is None:
            if "anonymous" in roles:
                return {"id": 0, "username": "anonymous", "role": "anonymous"}
            raise HTTPException(401, "Authentication required")
        payload = decode_token(credentials.credentials)
        user_role = payload.get("role", "client")
        if user_role not in roles:
            raise HTTPException(
                403,
                f"Requires role: {', '.join(roles)}. You have: {user_role}"
            )
        return {"id": int(payload["sub"]), "username": payload["username"], "role": user_role}
    return checker


# Convenience dependencies — express intent more clearly than require_role("editor")
# at call sites.
require_editor = require_role("editor")
require_client_or_editor = require_role("client", "editor")


def check_permission(user: Optional[Dict], permission: str) -> bool:
    """Check if user has a specific permission."""
    if user is None:
        return permission in ROLE_PERMISSIONS.get("analyst", set())
    role = user.get("role", "client")
    return permission in ROLE_PERMISSIONS.get(role, set())


# ─── Demo user seeding ───

# Four demo accounts for the MarketLens pitch tool. These are seeded on
# first boot. Two editors, two clients — enough to demo both roles with
# recognizable credentials. Passwords are deliberately simple strings the
# demoer can type; not a security concern for a pitch tool but MUST be
# changed before anything touches real client data.
DEMO_USERS = [
    # EY side
    {"username": "ey.partner",  "password": "demo1234", "role": "editor"},
    {"username": "ey.analyst",  "password": "demo1234", "role": "editor"},
    # Client side
    {"username": "client.cmo",      "password": "demo1234", "role": "client"},
    {"username": "client.analyst",  "password": "demo1234", "role": "client"},
]


def seed_demo_users() -> None:
    """
    Create the four MarketLens demo users if they don't already exist.
    Idempotent: calling this multiple times (e.g., on every server start)
    has the same effect as calling it once.

    Logs a single line per user — either "[seed] created" or "[seed]
    exists" — so it's easy to verify in container startup logs that the
    accounts are available after a fresh deploy.
    """
    for spec in DEMO_USERS:
        existing = get_user(spec["username"])
        if existing:
            logger.info(f"[seed] user exists: {spec['username']} (role={existing['role']})")
            continue
        try:
            create_user(spec["username"], hash_password(spec["password"]), spec["role"])
            logger.info(f"[seed] created user: {spec['username']} (role={spec['role']})")
        except ValueError:
            # Race condition (another worker seeded the same user) — idempotent
            # so we just log and move on.
            logger.info(f"[seed] race — user created by another process: {spec['username']}")


def get_demo_credentials_for_login_page() -> list:
    """
    Return the demo credentials in a shape the login screen can render.
    Only for demo builds; in a real deployment this endpoint is removed
    or returns an empty list.
    """
    if os.environ.get("MARKETLENS_HIDE_DEMO_CREDS") == "1":
        return []
    return [
        {"username": u["username"], "role": u["role"], "password_hint": u["password"]}
        for u in DEMO_USERS
    ]
