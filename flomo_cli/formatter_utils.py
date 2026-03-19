"""Base formatting utilities shared across formatter modules."""

from __future__ import annotations

import json
import sys
from html.parser import HTMLParser
from typing import Any

import click
from rich.console import Console

console = Console(stderr=True)
error_console = Console(stderr=True)
_stdout_console = Console()


# ─── Envelope helpers ──────────────────────────────────────────────────────


def success_payload(data: Any, **extra: Any) -> dict[str, Any]:
    """Wrap data in a standard success envelope."""
    payload: dict[str, Any] = {"ok": True, "data": data}
    payload.update(extra)
    return payload


def error_payload(code: str, message: str) -> dict[str, Any]:
    """Wrap error info in a standard error envelope."""
    return {"ok": False, "error": code, "message": message}


# ─── Structured output ─────────────────────────────────────────────────────


def print_json(data: Any) -> None:
    """Pretty-print JSON to stdout."""
    _stdout_console.print_json(json.dumps(data, ensure_ascii=False, indent=2))


def maybe_print_structured(data: Any, *, as_json: bool) -> bool:
    """If as_json is True (or stdout is non-TTY), print JSON and return True."""
    if not as_json and sys.stdout.isatty():
        return False
    # Non-TTY pipelines get JSON automatically so Agents don't need --json
    if not as_json and not sys.stdout.isatty():
        as_json = True
    if not as_json:
        return False
    print_json(success_payload(data))
    return True


def emit_error(code: str, message: str, *, as_json: bool) -> bool:
    """Emit a structured error and return True; False if not in JSON mode."""
    if not as_json:
        return False
    print_json(error_payload(code, message))
    return True


# ─── UI helpers ────────────────────────────────────────────────────────────


def print_error(message: str) -> None:
    """Print error message to stderr."""
    error_console.print(f"[red]✗[/red] {message}")


def print_success(message: str) -> None:
    """Print success message to stderr."""
    console.print(f"[green]✓[/green] {message}")


def print_info(message: str) -> None:
    """Print informational message to stderr."""
    console.print(f"[dim]ℹ[/dim] {message}")


# ─── Text utilities ────────────────────────────────────────────────────────


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if stripped:
            self._parts.append(stripped)

    def get_text(self) -> str:
        return " ".join(self._parts)


def html_to_text(html_content: str) -> str:
    """Strip HTML tags and return plain text."""
    if not html_content:
        return ""
    extractor = _HTMLTextExtractor()
    extractor.feed(html_content)
    return extractor.get_text()


def truncate(text: str, max_len: int = 60) -> str:
    """Truncate text to max_len characters, appending '…' if cut."""
    return text if len(text) <= max_len else text[:max_len] + "…"


def format_tags(tags: list[str]) -> str:
    """Format a list of tag strings for display."""
    if not tags:
        return "[dim]-[/dim]"
    return " ".join(f"[cyan]#{t}[/cyan]" for t in tags)
