from datetime import timedelta

import httpx
import pytest
import respx

from analytics_mcp.remote import google
from analytics_mcp.remote.config import Config


def _cfg():
    return Config(
        port=8080, base_url="https://ga.example.com", google_client_id="cid",
        google_client_secret="csec", jwt_secret="j", allowed_hosts=[],
        allowed_emails=set(), allowed_google_domains={"example.com"},
        access_token_ttl=timedelta(hours=24), trust_proxy=False, log_level="info",
        token_db_path=":memory:",
    )


def test_authorization_url_forces_offline_consent():
    url = google.authorization_url(_cfg(), "state123")
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "state=state123" in url
    assert "redirect_uri=https%3A%2F%2Fga.example.com%2Foauth%2Fcallback" in url
    assert "analytics.readonly" in url


@pytest.mark.asyncio
@respx.mock
async def test_exchange_code_posts_and_returns_tokens():
    route = respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=httpx.Response(
            200, json={"access_token": "ga", "refresh_token": "gr", "expires_in": 3600}
        )
    )
    out = await google.exchange_code(_cfg(), "authcode")
    assert out["refresh_token"] == "gr"
    assert route.calls.last.request.read().decode().count("grant_type=authorization_code")


@pytest.mark.asyncio
@respx.mock
async def test_fetch_userinfo_returns_identity():
    respx.get("https://openidconnect.googleapis.com/v1/userinfo").mock(
        return_value=httpx.Response(
            200, json={"sub": "1", "email": "a@example.com", "email_verified": True}
        )
    )
    info = await google.fetch_userinfo("ga")
    assert info["email"] == "a@example.com"


def test_build_credentials_carries_refresh_token():
    creds = google.build_credentials(_cfg(), "ga", "gr", expiry_epoch=None)
    assert creds.refresh_token == "gr"
    assert creds.token == "ga"
