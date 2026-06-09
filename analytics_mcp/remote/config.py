"""Environment configuration for the remote MCP server."""

import os
from dataclasses import dataclass
from datetime import timedelta

ANALYTICS_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"


@dataclass(frozen=True)
class Config:
    port: int
    base_url: str
    google_client_id: str
    google_client_secret: str
    jwt_secret: str
    allowed_hosts: list[str]
    allowed_emails: set[str]
    allowed_google_domains: set[str]
    access_token_ttl: timedelta
    trust_proxy: bool
    log_level: str
    token_db_path: str


def _csv_set(value: str) -> set[str]:
    return {item.strip().lower() for item in value.split(",") if item.strip()}


def _csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def load() -> Config:
    # The access allowlist is configured exclusively via environment variables
    # (set as Docker variables in deployment). No domain or email is ever hard
    # coded — this repo is public and must contain no deployment-specific values.
    return Config(
        port=int(os.getenv("PORT", "8080")),
        base_url=os.getenv("BASE_URL", "http://localhost:8080").rstrip("/"),
        google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
        google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
        jwt_secret=os.getenv("JWT_SECRET", ""),
        allowed_hosts=_csv_list(os.getenv("ALLOWED_HOSTS", "")),
        allowed_emails=_csv_set(os.getenv("ALLOWED_EMAILS", "")),
        allowed_google_domains=_csv_set(os.getenv("ALLOWED_GOOGLE_DOMAINS", "")),
        access_token_ttl=timedelta(
            seconds=int(os.getenv("ACCESS_TOKEN_TTL_SECONDS", "86400"))
        ),
        trust_proxy=os.getenv("TRUST_PROXY", "false").lower() in ("1", "true", "yes"),
        log_level=os.getenv("LOG_LEVEL", "info"),
        token_db_path=os.getenv("TOKEN_DB_PATH", "/data/tokens.db"),
    )
