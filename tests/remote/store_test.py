import time

from mcp.shared.auth import OAuthClientInformationFull

from analytics_mcp.remote.store import TokenStore


def _store(tmp_path):
    return TokenStore(str(tmp_path / "t.db"))


def test_client_roundtrip_persists_across_reopen(tmp_path):
    s = _store(tmp_path)
    client = OAuthClientInformationFull(
        client_id="c1", client_secret="sec", redirect_uris=["https://x/cb"]
    )
    s.save_client(client)
    assert s.get_client("c1").client_secret == "sec"
    # Reopen the DB (simulates a container redeploy).
    s2 = TokenStore(str(tmp_path / "t.db"))
    assert s2.get_client("c1").redirect_uris[0].encoded_string() == "https://x/cb"


def test_state_pop_is_single_use(tmp_path):
    s = _store(tmp_path)
    s.save_state(
        state="st", client_id="c1", redirect_uri="https://x/cb",
        redirect_uri_provided_explicitly=True, code_challenge="ch",
        scopes=["s"], resource=None, expires_at=time.time() + 60,
    )
    assert s.pop_state("st")["client_id"] == "c1"
    assert s.pop_state("st") is None  # consumed


def test_auth_code_carries_google_tokens(tmp_path):
    s = _store(tmp_path)
    s.save_auth_code(
        code="ac", client_id="c1", redirect_uri="https://x/cb",
        redirect_uri_provided_explicitly=True, code_challenge="ch",
        scopes=["s"], resource=None, subject="u@example.com",
        google_access="ga", google_refresh="gr", google_expiry=time.time() + 3600,
        expires_at=time.time() + 600,
    )
    row = s.get_auth_code("ac")
    assert row["google_refresh"] == "gr"
    s.delete_auth_code("ac")
    assert s.get_auth_code("ac") is None


def test_token_save_lookup_and_rotate(tmp_path):
    s = _store(tmp_path)
    s.save_token(
        access_token="at", refresh_token="rt", client_id="c1", scopes=["s"],
        expires_at=time.time() + 100, google_access="ga", google_refresh="gr",
        google_expiry=time.time() + 3600, subject="u@example.com",
    )
    assert s.get_by_access("at")["refresh_token"] == "rt"
    assert s.get_by_refresh("rt")["access_token"] == "at"
    s.rotate_token(
        old_refresh="rt", access_token="at2", refresh_token="rt2", client_id="c1",
        scopes=["s"], expires_at=time.time() + 100, google_access="ga",
        google_refresh="gr", google_expiry=time.time() + 3600, subject="u@example.com",
    )
    assert s.get_by_refresh("rt") is None
    assert s.get_by_access("at2")["refresh_token"] == "rt2"
    s.delete_by_token("at2")
    assert s.get_by_access("at2") is None


def test_purge_expired_removes_old_codes_and_states(tmp_path):
    s = _store(tmp_path)
    s.save_state(
        state="old", client_id="c1", redirect_uri="https://x/cb",
        redirect_uri_provided_explicitly=True, code_challenge="ch", scopes=[],
        resource=None, expires_at=time.time() - 1,
    )
    s.purge_expired()
    assert s.pop_state("old") is None
