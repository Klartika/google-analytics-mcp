import importlib
import os
import time

import pytest
import respx
import httpx
from starlette.testclient import TestClient

from analytics_mcp.remote import app as app_mod
from analytics_mcp.remote.config import load as load_config
from analytics_mcp.remote.store import TokenStore


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "csec")
    monkeypatch.setenv("JWT_SECRET", "jwt")
    # The MCP SDK's create_auth_routes() requires an HTTPS issuer URL, with the
    # sole exception of localhost/127.0.0.1 over HTTP (see validate_issuer_url).
    # Use http://localhost so the auth routes build under the test client.
    monkeypatch.setenv("BASE_URL", "http://localhost")
    monkeypatch.setenv("TOKEN_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("ALLOWED_GOOGLE_DOMAINS", "example.com")
    importlib.reload(app_mod)
    return TestClient(
        app_mod.create_app(load_config()), base_url="http://localhost"
    )


def test_health_is_open(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_protected_resource_metadata_served(client):
    resp = client.get("/.well-known/oauth-protected-resource")
    assert resp.status_code == 200
    assert "authorization_servers" in resp.json()


def test_authorization_server_metadata_served(client):
    resp = client.get("/.well-known/oauth-authorization-server")
    assert resp.status_code == 200
    body = resp.json()
    assert body["authorization_endpoint"].endswith("/authorize")
    assert body["token_endpoint"].endswith("/token")


def test_mcp_requires_auth(client):
    resp = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        headers={"Accept": "application/json, text/event-stream"},
    )
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers


# --- /oauth/callback tests ---

def _seed_state(db_path: str, state: str) -> None:
    """Insert a federation state row directly into the store."""
    store = TokenStore(db_path)
    store.save_state(
        state=state,
        client_id="c1",
        redirect_uri="https://claude.ai/cb",
        redirect_uri_provided_explicitly=True,
        code_challenge="ch",
        scopes=["openid"],
        resource=None,
        expires_at=time.time() + 600,
    )


def test_oauth_callback_allowed_domain(client, monkeypatch):
    """Callback with an allowed domain redirects with an auth code."""
    db_path = os.environ["TOKEN_DB_PATH"]
    _seed_state(db_path, "st-allow")

    with respx.mock(assert_all_called=True) as mock:
        mock.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "ga",
                    "refresh_token": "gr",
                    "expires_in": 3600,
                },
            )
        )
        mock.get("https://openidconnect.googleapis.com/v1/userinfo").mock(
            return_value=httpx.Response(
                200,
                json={
                    "sub": "1",
                    "email": "user@example.com",
                    "email_verified": True,
                },
            )
        )
        resp = client.get(
            "/oauth/callback?code=x&state=st-allow",
            follow_redirects=False,
        )

    assert resp.status_code == 302
    location = resp.headers["location"]
    assert "code=" in location
    assert "state=st-allow" in location

    # Auth code row should now exist in the store.
    store = TokenStore(db_path)
    from urllib.parse import urlparse, parse_qs
    qs = parse_qs(urlparse(location).query)
    issued_code = qs["code"][0]
    assert store.get_auth_code(issued_code) is not None


def test_oauth_callback_rejected_domain(client, monkeypatch):
    """Callback with a disallowed domain returns 403 and issues no auth code."""
    db_path = os.environ["TOKEN_DB_PATH"]
    _seed_state(db_path, "st-deny")

    with respx.mock(assert_all_called=True) as mock:
        mock.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "ga2",
                    "refresh_token": "gr2",
                    "expires_in": 3600,
                },
            )
        )
        mock.get("https://openidconnect.googleapis.com/v1/userinfo").mock(
            return_value=httpx.Response(
                200,
                json={
                    "sub": "2",
                    "email": "user@notallowed.test",
                    "email_verified": True,
                },
            )
        )
        resp = client.get(
            "/oauth/callback?code=y&state=st-deny",
            follow_redirects=False,
        )

    assert resp.status_code == 403
