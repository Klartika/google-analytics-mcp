import importlib

import pytest
from starlette.testclient import TestClient

from analytics_mcp.remote import app as app_mod
from analytics_mcp.remote.config import load as load_config


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
