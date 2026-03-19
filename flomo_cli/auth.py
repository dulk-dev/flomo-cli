"""Token management for Flomo CLI.

Token resolution priority (high → low):
  1. --token CLI parameter
  2. FLOMO_TOKEN environment variable
  3. ~/.flomo-cli/token.json (written by `flomo login`)
  4. → raises NotAuthenticatedError
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from .constants import CONFIG_DIR, TOKEN_FILE
from .exceptions import NotAuthenticatedError

logger = logging.getLogger(__name__)

_TOKEN_PATH = CONFIG_DIR / TOKEN_FILE


def get_token(token_override: str | None = None) -> str:
    """Resolve the authentication token using the priority chain."""
    if token_override:
        return token_override

    env = os.environ.get("FLOMO_TOKEN")
    if env:
        return env

    cached = _load_token_cache()
    if cached and cached.get("access_token"):
        return cached["access_token"]

    raise NotAuthenticatedError(
        "未找到认证信息，请先执行 flomo login 或设置 FLOMO_TOKEN 环境变量"
    )


def save_token(user_data: dict[str, Any]) -> None:
    """Persist the access_token and user info to the config file (chmod 0o600)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _TOKEN_PATH.write_text(
        json.dumps(user_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _TOKEN_PATH.chmod(0o600)
    logger.debug("Token saved to %s", _TOKEN_PATH)


def clear_token() -> bool:
    """Remove the cached token. Returns True if a token existed."""
    if _TOKEN_PATH.exists():
        _TOKEN_PATH.unlink()
        return True
    return False


def load_user_info() -> dict[str, Any] | None:
    """Return cached user info, or None if not logged in."""
    return _load_token_cache()


def _load_token_cache() -> dict[str, Any] | None:
    if not _TOKEN_PATH.exists():
        return None
    try:
        return json.loads(_TOKEN_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.debug("Failed to read token cache: %s", exc)
        return None
