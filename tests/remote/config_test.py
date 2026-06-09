import importlib

from analytics_mcp.remote import config as config_mod


def _load(monkeypatch, **env):
    for key in [
        "PORT", "BASE_URL", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "JWT_SECRET",
        "ALLOWED_HOSTS", "ALLOWED_EMAILS", "ALLOWED_GOOGLE_DOMAINS",
        "ACCESS_TOKEN_TTL_SECONDS", "TRUST_PROXY", "LOG_LEVEL", "TOKEN_DB_PATH",
    ]:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    importlib.reload(config_mod)
    return config_mod.load()


def test_domains_unset_means_open(monkeypatch):
    # No domain/email is baked into the code; the allowlist is configured purely
    # via env vars (a Docker variable in deployment). Unset => open mode.
    cfg = _load(monkeypatch)
    assert cfg.allowed_google_domains == set()
    assert cfg.port == 8080
    assert cfg.token_db_path == "/data/tokens.db"
    assert cfg.trust_proxy is False


def test_env_configures_the_allowlist(monkeypatch):
    cfg = _load(
        monkeypatch,
        ALLOWED_GOOGLE_DOMAINS="example.com, Foo.Org",
        ALLOWED_EMAILS="a@b.com",
        TRUST_PROXY="true",
        ACCESS_TOKEN_TTL_SECONDS="3600",
        BASE_URL="https://ga.example.com/",
    )
    assert cfg.allowed_google_domains == {"example.com", "foo.org"}
    assert cfg.allowed_emails == {"a@b.com"}
    assert cfg.trust_proxy is True
    assert cfg.access_token_ttl.total_seconds() == 3600
    assert cfg.base_url == "https://ga.example.com"  # trailing slash stripped


def test_empty_domains_env_means_open(monkeypatch):
    cfg = _load(monkeypatch, ALLOWED_GOOGLE_DOMAINS="")
    assert cfg.allowed_google_domains == set()
