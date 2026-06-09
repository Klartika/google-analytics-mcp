from datetime import timedelta

import pytest
from mcp.server.auth.provider import AuthorizationParams, RefreshToken
from mcp.shared.auth import OAuthClientInformationFull

from analytics_mcp.remote.config import Config
from analytics_mcp.remote.provider import GoogleMCPProvider
from analytics_mcp.remote.store import TokenStore


def _cfg():
    return Config(
        port=8080, base_url="https://ga.example.com", google_client_id="cid",
        google_client_secret="csec", jwt_secret="j", allowed_hosts=[],
        allowed_emails=set(), allowed_google_domains={"example.com"},
        access_token_ttl=timedelta(hours=24), trust_proxy=False, log_level="info",
        token_db_path=":memory:",
    )


def _client():
    return OAuthClientInformationFull(
        client_id="c1", client_secret="s", redirect_uris=["https://claude.ai/cb"]
    )


@pytest.fixture
def provider(tmp_path):
    return GoogleMCPProvider(_cfg(), TokenStore(str(tmp_path / "t.db")))


async def test_authorize_redirects_to_google_and_stores_state(provider):
    params = AuthorizationParams(
        state="st", scopes=["openid"], code_challenge="ch",
        redirect_uri="https://claude.ai/cb", redirect_uri_provided_explicitly=True,
        resource=None,
    )
    url = await provider.authorize(_client(), params)
    assert url.startswith("https://accounts.google.com/")
    assert provider.store.pop_state("st")["client_id"] == "c1"


async def test_full_code_exchange_roundtrip(provider):
    # Simulate the callback having stored an auth code bound to Google tokens.
    provider.store.save_auth_code(
        code="ac", client_id="c1", redirect_uri="https://claude.ai/cb",
        redirect_uri_provided_explicitly=True, code_challenge="ch", scopes=["openid"],
        resource=None, subject="a@example.com", google_access="ga",
        google_refresh="gr", google_expiry=None, expires_at=2**31,
    )
    loaded = await provider.load_authorization_code(_client(), "ac")
    assert loaded is not None and loaded.code_challenge == "ch"
    token = await provider.exchange_authorization_code(_client(), loaded)
    assert token.token_type == "Bearer" and token.refresh_token
    access = await provider.load_access_token(token.access_token)
    assert access is not None and access.subject == "a@example.com"
    # Google tokens are retrievable by the access token (for credential building).
    assert provider.store.get_by_access(token.access_token)["google_refresh"] == "gr"


async def test_refresh_rotates_and_preserves_google_tokens(provider):
    provider.store.save_token(
        access_token="at", refresh_token="rt", client_id="c1", scopes=["openid"],
        expires_at=2**31, google_access="ga", google_refresh="gr",
        google_expiry=None, subject="a@example.com",
    )
    rt = RefreshToken(token="rt", client_id="c1", scopes=["openid"], expires_at=None)
    new = await provider.exchange_refresh_token(_client(), rt, ["openid"])
    assert new.access_token != "at"
    assert provider.store.get_by_refresh("rt") is None
    assert provider.store.get_by_access(new.access_token)["google_refresh"] == "gr"


async def test_revoke_deletes_token(provider):
    provider.store.save_token(
        access_token="at", refresh_token="rt", client_id="c1", scopes=[],
        expires_at=2**31, google_access="ga", google_refresh="gr",
        google_expiry=None, subject="a@example.com",
    )
    access = await provider.load_access_token("at")
    await provider.revoke_token(access)
    assert provider.store.get_by_access("at") is None
