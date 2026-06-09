"""Access allowlist enforced after Google verifies a user's identity."""

import logging

from analytics_mcp.remote.config import Config

log = logging.getLogger("analytics_mcp.remote")


def is_open(cfg: Config) -> bool:
    return not cfg.allowed_emails and not cfg.allowed_google_domains


def identity_allowed(cfg: Config, email, hd, verified) -> bool:
    if is_open(cfg):
        log.warning(
            "access allowlist is OPEN — set ALLOWED_GOOGLE_DOMAINS or "
            "ALLOWED_EMAILS to restrict who can use this server"
        )
        return True
    if not email or not verified:
        return False
    email = email.lower()
    if email in cfg.allowed_emails:
        return True
    domain = (hd or email.split("@")[-1]).lower()
    return domain in cfg.allowed_google_domains
