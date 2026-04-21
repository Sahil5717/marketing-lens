"""
Shared pytest fixtures and helpers for routes tests.

In v26.1 the 5 new route modules are auth-protected with
`Depends(require_client_or_editor)`. Every test that used to pass
`TestClient(app)` now gets 401s because there's no token.

This conftest provides a single helper — `auth_headers()` — that
produces a valid Bearer token for a test user. Tests either:
  1. Use the `client` fixture they already define, then add headers to
     each request with `client.get(..., headers=auth_headers())`, or
  2. Use the `authed_client` fixture below, which wraps TestClient so
     every request automatically includes auth.

The `authed_client` approach keeps tests clean and preserves their
existing shape. Individual test modules can override the user role if
they specifically need editor permissions.
"""
from typing import Dict

import pytest
from fastapi.testclient import TestClient


def make_token(role: str = "client", user_id: int = 999, username: str = "testuser") -> str:
    """Create a JWT for use in tests. Defaults to the minimal role
    our new routes require (`client` — covered by require_client_or_editor)."""
    from auth import create_token
    return create_token(user_id, username, role)


def auth_headers(role: str = "client") -> Dict[str, str]:
    """Bearer headers dict for passing to `client.get(..., headers=...)`."""
    return {"Authorization": f"Bearer {make_token(role)}"}


class AuthedTestClient(TestClient):
    """TestClient that injects an Authorization header on every request.

    Subclassing keeps the whole TestClient API intact; we only intercept
    the one method that matters. If a test wants to issue an unauth'd
    request to check a 401 path, it can still use `super().get(...)`.
    """

    def __init__(self, app, role: str = "client"):
        super().__init__(app)
        self._default_headers = auth_headers(role)

    def request(self, method, url, **kwargs):
        # Merge default auth header with any caller-provided headers,
        # letting the caller override when they want to test auth failures.
        headers = {**self._default_headers, **(kwargs.pop("headers", None) or {})}
        return super().request(method, url, headers=headers, **kwargs)
