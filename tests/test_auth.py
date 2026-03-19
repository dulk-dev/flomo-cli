"""Unit tests for token management."""

import json
from pathlib import Path

import pytest

from flomo_cli.exceptions import NotAuthenticatedError


def test_get_token_with_override(monkeypatch):
    """--token parameter takes highest priority."""
    monkeypatch.delenv("FLOMO_TOKEN", raising=False)
    from flomo_cli.auth import get_token
    assert get_token(token_override="override-tok") == "override-tok"


def test_get_token_from_env(monkeypatch):
    """FLOMO_TOKEN environment variable is second priority."""
    monkeypatch.setenv("FLOMO_TOKEN", "env-token-123")
    from flomo_cli.auth import get_token
    assert get_token() == "env-token-123"


def test_get_token_override_beats_env(monkeypatch):
    monkeypatch.setenv("FLOMO_TOKEN", "env-token")
    from flomo_cli.auth import get_token
    assert get_token(token_override="cli-token") == "cli-token"


def test_get_token_from_cache(tmp_path, monkeypatch):
    """Falls back to ~/.flomo-cli/token.json."""
    monkeypatch.delenv("FLOMO_TOKEN", raising=False)
    monkeypatch.setattr("flomo_cli.auth._TOKEN_PATH", tmp_path / "token.json")
    (tmp_path / "token.json").write_text(
        json.dumps({"access_token": "cached-token", "name": "Test"}),
        encoding="utf-8",
    )
    from importlib import reload
    import flomo_cli.auth as auth_mod
    assert auth_mod.get_token() == "cached-token"


def test_get_token_raises_when_missing(tmp_path, monkeypatch):
    """Raises NotAuthenticatedError when no token is available."""
    monkeypatch.delenv("FLOMO_TOKEN", raising=False)
    monkeypatch.setattr("flomo_cli.auth._TOKEN_PATH", tmp_path / "token.json")
    from flomo_cli.auth import get_token
    with pytest.raises(NotAuthenticatedError):
        get_token()

def test_get_token_raises_when_cache_json_corrupted(tmp_path, monkeypatch):
    """Invalid token.json should be treated as unauthenticated."""
    monkeypatch.delenv("FLOMO_TOKEN", raising=False)
    token_file = tmp_path / "token.json"
    token_file.write_text("{not-valid-json", encoding="utf-8")
    monkeypatch.setattr("flomo_cli.auth._TOKEN_PATH", token_file)

    from flomo_cli.auth import get_token

    with pytest.raises(NotAuthenticatedError):
        get_token()


def test_get_token_raises_when_cache_read_fails(monkeypatch):
    """I/O error while reading token cache should not crash."""
    monkeypatch.delenv("FLOMO_TOKEN", raising=False)

    class _BrokenPath:
        def exists(self):
            return True

        def read_text(self, encoding="utf-8"):
            raise OSError("disk read failed")

    monkeypatch.setattr("flomo_cli.auth._TOKEN_PATH", _BrokenPath())

    from flomo_cli.auth import get_token

    with pytest.raises(NotAuthenticatedError):
        get_token()


def test_save_and_clear_token(tmp_path, monkeypatch):
    monkeypatch.setattr("flomo_cli.auth._TOKEN_PATH", tmp_path / "token.json")
    from flomo_cli.auth import clear_token, save_token

    save_token({"access_token": "tok", "name": "Alice"})
    token_file = tmp_path / "token.json"
    assert token_file.exists()
    data = json.loads(token_file.read_text())
    assert data["access_token"] == "tok"
    # Permissions
    import stat
    mode = token_file.stat().st_mode & 0o777
    assert mode == 0o600

    assert clear_token() is True
    assert not token_file.exists()
    assert clear_token() is False  # already cleared


def test_html_to_text():
    from flomo_cli.formatter_utils import html_to_text

    assert html_to_text("<p>Hello</p>") == "Hello"
    assert html_to_text("<p>Line 1</p><p>Line 2</p>") == "Line 1 Line 2"
    assert html_to_text("") == ""
    assert html_to_text("<p><br></p>") == ""


def test_error_codes():
    from flomo_cli.error_codes import error_code_for_exception
    from flomo_cli.exceptions import (
        FlomoApiError,
        NotAuthenticatedError,
        NotFoundError,
        ValidationError,
    )

    assert error_code_for_exception(NotAuthenticatedError("x")) == "not_authenticated"
    assert error_code_for_exception(NotFoundError("x")) == "not_found"
    assert error_code_for_exception(ValidationError("x")) == "validation_error"
    assert error_code_for_exception(FlomoApiError("x")) == "api_error"
    assert error_code_for_exception(RuntimeError("x")) == "unknown_error"
