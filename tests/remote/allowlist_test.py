from datetime import timedelta

from analytics_mcp.remote.allowlist import identity_allowed, is_open
from analytics_mcp.remote.config import Config


def _cfg(emails=None, domains=None):
    return Config(
        port=8080, base_url="https://x", google_client_id="", google_client_secret="",
        jwt_secret="", allowed_hosts=[], allowed_emails=emails or set(),
        allowed_google_domains=domains or set(),
        access_token_ttl=timedelta(hours=24), trust_proxy=False, log_level="info",
        token_db_path=":memory:",
    )


def test_domain_match_allows():
    cfg = _cfg(domains={"example.com", "example.org"})
    assert identity_allowed(cfg, "user@example.com", None, True) is True
    assert identity_allowed(cfg, "x@example.org", "example.org", True) is True


def test_non_allowlisted_domain_rejected():
    cfg = _cfg(domains={"example.com"})
    assert identity_allowed(cfg, "x@gmail.com", None, True) is False


def test_unverified_email_rejected():
    cfg = _cfg(domains={"example.com"})
    assert identity_allowed(cfg, "user@example.com", None, False) is False


def test_explicit_email_allows_outside_domain():
    cfg = _cfg(emails={"contractor@gmail.com"}, domains={"example.com"})
    assert identity_allowed(cfg, "contractor@gmail.com", None, True) is True


def test_open_mode_allows_anyone():
    cfg = _cfg()
    assert is_open(cfg) is True
    assert identity_allowed(cfg, "anyone@anywhere.com", None, True) is True
