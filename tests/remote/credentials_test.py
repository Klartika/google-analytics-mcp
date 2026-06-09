import asyncio

import analytics_mcp.tools.client as client_mod
from analytics_mcp.remote import credentials


def test_patch_falls_back_to_adc_when_unset(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(credentials, "_original_get_credentials", lambda: sentinel)
    credentials.apply_patch()
    assert client_mod._get_credentials() is sentinel


def test_contextvar_overrides_adc():
    credentials.apply_patch()
    user_creds = object()
    with credentials.use_credentials(user_creds):
        assert client_mod._get_credentials() is user_creds
    assert credentials.current_credentials.get() is None


def test_contextvar_is_task_isolated():
    credentials.apply_patch()

    async def worker(value):
        with credentials.use_credentials(value):
            await asyncio.sleep(0)
            return client_mod._get_credentials()

    async def main():
        return await asyncio.gather(worker("a"), worker("b"))

    assert asyncio.run(main()) == ["a", "b"]
