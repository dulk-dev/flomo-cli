"""Common helpers for CLI commands."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import Any, TypeVar

import click

from ..auth import get_token
from ..client import FlomoClient
from ..error_codes import error_code_for_exception
from ..exceptions import FlomoApiError
from ..formatter_utils import error_payload, print_error, success_payload

T = TypeVar("T")


# ─── Reusable decorators ──────────────────────────────────────────────────


def json_option(command: Callable) -> Callable:
    """Add --json flag to a Click command."""
    return click.option(
        "--json", "as_json", is_flag=True, help="Output as JSON (Agent-friendly)."
    )(command)


# ─── Client factory ───────────────────────────────────────────────────────


def get_client(ctx: click.Context) -> FlomoClient:
    """Build a FlomoClient using the token resolution chain."""
    token_override = ctx.obj.get("token") if ctx.obj else None
    token = get_token(token_override)
    return FlomoClient(token)


# ─── Core command runner ──────────────────────────────────────────────────


def run_client_action(ctx: click.Context, action: Callable[[FlomoClient], T]) -> T:
    """Execute action(client) inside a managed FlomoClient context."""
    with get_client(ctx) as client:
        return action(client)


def handle_command(
    ctx: click.Context,
    *,
    action: Callable[[FlomoClient], Any],
    render: Callable[[Any], None] | None = None,
    as_json: bool = False,
    json_extra: dict[str, Any] | None = None,
) -> None:
    """Standard command flow: authenticate → run → format output → handle errors.

    ``json_extra`` lets callers inject top-level fields (e.g. ``has_more``) next to
    the ``data`` key in the JSON envelope.
    """
    try:
        data = run_client_action(ctx, action)
        if as_json or not sys.stdout.isatty():
            payload = success_payload(data, **(json_extra or {}))
            _emit_json(payload)
        elif render:
            render(data)
    except FlomoApiError as exc:
        exit_for_error(exc, as_json=as_json)


# ─── Error handling ───────────────────────────────────────────────────────


def exit_for_error(exc: Exception, *, as_json: bool) -> None:
    """Print a structured or plain error and terminate with exit code 1."""
    code = error_code_for_exception(exc)
    message = str(exc)
    if as_json or not sys.stdout.isatty():
        _emit_json(error_payload(code, message))
    else:
        print_error(message)
    raise SystemExit(1) from None


def _emit_json(payload: Any) -> None:
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
