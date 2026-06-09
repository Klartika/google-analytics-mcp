"""Request-scoped Google credentials, injected into the upstream client.

The upstream ``analytics_mcp.tools.client`` resolves credentials via the
module-level ``_get_credentials()``. We monkeypatch that name so the unchanged
tool code uses the per-request user's credentials when present, falling back to
Application Default Credentials otherwise. ``contextvars`` makes this safe under
concurrency: each request/task sees only its own credentials.
"""

import contextlib
import contextvars
from typing import Optional

import analytics_mcp.tools.client as _client_mod

current_credentials: contextvars.ContextVar[Optional[object]] = (
    contextvars.ContextVar("ga_user_credentials", default=None)
)

# Captured once so the patch is idempotent and can defer to the original.
_original_get_credentials = _client_mod._get_credentials


def _patched_get_credentials():
    creds = current_credentials.get()
    if creds is not None:
        return creds
    return _original_get_credentials()


def apply_patch() -> None:
    """Install the credential override on the upstream client module."""
    _client_mod._get_credentials = _patched_get_credentials


@contextlib.contextmanager
def use_credentials(creds):
    """Bind ``creds`` as the current request's Google credentials."""
    token = current_credentials.set(creds)
    try:
        yield
    finally:
        current_credentials.reset(token)
