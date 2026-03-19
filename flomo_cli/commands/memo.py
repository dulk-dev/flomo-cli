"""Memo commands: list / get / new / edit / delete / search / related / tags."""

from __future__ import annotations

import re
from typing import Any

import click

from ..constants import DEFAULT_LIST_LIMIT
from ..formatter_renderers import (
    render_daily_review,
    render_memo,
    render_memo_list,
    render_related_memos,
    render_search_results,
    render_tag_tree,
)
from ..formatter_utils import html_to_text, print_success, success_payload
from ._common import exit_for_error, handle_command, json_option, run_client_action


# ─── Helpers ──────────────────────────────────────────────────────────────


def _text_to_html(content: str) -> str:
    """Wrap plain text in <p> tags. Preserves content already in HTML."""
    if content.startswith("<"):
        return content
    lines = content.split("\n")
    return "".join(
        f"<p>{line}</p>" if line.strip() else "<p><br></p>" for line in lines
    )


def _format_file(f: dict[str, Any]) -> dict[str, Any]:
    """Extract useful fields from a file/attachment object."""
    return {
        "id": f.get("id"),
        "type": f.get("type"),
        "name": f.get("name"),
        "size": f.get("size"),
        "url": f.get("url"),
        "thumbnail_url": f.get("thumbnail_url"),
    }


def _format_memo(memo: dict[str, Any]) -> dict[str, Any]:
    """Return a clean memo dict suitable for JSON output."""
    raw_files = memo.get("files", [])
    result: dict[str, Any] = {
        "slug": memo.get("slug"),
        "content": memo.get("content"),
        "content_text": html_to_text(memo.get("content", "")),
        "tags": memo.get("tags", []),
        "created_at": memo.get("created_at"),
        "updated_at": memo.get("updated_at"),
        "deleted_at": memo.get("deleted_at"),
        "files": [_format_file(f) for f in raw_files],
    }
    return result


def _format_memos(memos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_format_memo(m) for m in memos]


# ─── list ──────────────────────────────────────────────────────────────────


@click.command("list")
@click.option(
    "--limit",
    default=DEFAULT_LIST_LIMIT,
    show_default=True,
    help="Number of memos to show.",
)
@click.option(
    "--sort",
    type=click.Choice(["newest", "oldest"]),
    default="newest",
    show_default=True,
    help="Sort order: newest-first or oldest-first.",
)
@json_option
@click.pass_context
def list_memos(ctx: click.Context, limit: int, sort: str, as_json: bool) -> None:
    """List memos."""
    try:
        if sort == "oldest":
            memos = run_client_action(
                ctx, lambda c: c.list_memos_ascending(limit=limit)
            )
        else:
            memos = run_client_action(ctx, lambda c: c.list_memos(limit=limit))
        has_more = len(memos) >= limit
        formatted = _format_memos(memos)
        if as_json:
            import json as _json
            from ._common import _emit_json
            _emit_json(success_payload(formatted, has_more=has_more))
        else:
            render_memo_list(memos, has_more=has_more)
    except Exception as exc:
        from ..exceptions import FlomoApiError
        if isinstance(exc, FlomoApiError):
            exit_for_error(exc, as_json=as_json)
        raise


# ─── get ───────────────────────────────────────────────────────────────────


@click.command()
@click.argument("slug")
@json_option
@click.pass_context
def get(ctx: click.Context, slug: str, as_json: bool) -> None:
    """Get a single memo by slug."""
    handle_command(
        ctx,
        action=lambda c: _format_memo(c.get_memo(slug)),
        render=lambda data: render_memo(data),
        as_json=as_json,
    )


# ─── new ───────────────────────────────────────────────────────────────────


@click.command()
@click.argument("content", required=False, default=None)
@click.option("-f", "--file", "file_path", type=click.Path(exists=True), help="Read content from file.")
@json_option
@click.pass_context
def new(ctx: click.Context, content: str | None, file_path: str | None, as_json: bool) -> None:
    """Create a new memo. Use #tag syntax in content to add tags.

    Content can be provided as an argument, from a file (--file path), or via stdin (echo "..." | flomo new).
    """
    import sys

    if file_path:
        content = open(file_path, encoding="utf-8").read()
    elif content is None:
        if not sys.stdin.isatty():
            content = sys.stdin.read()
        else:
            raise click.UsageError("需要提供内容：flomo new \"内容\" 或 flomo new -f file.txt 或 echo \"内容\" | flomo new")

    if not content or not content.strip():
        raise click.UsageError("内容不能为空")

    html_content = _text_to_html(content.strip())

    def _action(client):
        memo = client.create_memo(html_content)
        return _format_memo(memo)

    def _render(data: dict[str, Any]) -> None:
        print_success(f"笔记已创建（slug: {data.get('slug')}）")
        tags = data.get("tags", [])
        if tags:
            from ..formatter_utils import print_info
            print_info(f"自动提取标签：{', '.join('#' + t for t in tags)}")

    handle_command(ctx, action=_action, render=_render, as_json=as_json)


# ─── edit ──────────────────────────────────────────────────────────────────


@click.command()
@click.argument("slug")
@click.argument("content")
@json_option
@click.pass_context
def edit(ctx: click.Context, slug: str, content: str, as_json: bool) -> None:
    """Update an existing memo's content."""
    html_content = _text_to_html(content)

    def _action(client):
        memo = client.update_memo(slug, html_content)
        return _format_memo(memo)

    def _render(data: dict[str, Any]) -> None:
        print_success(f"笔记已更新（slug: {data.get('slug')}）")

    handle_command(ctx, action=_action, render=_render, as_json=as_json)


# ─── delete ────────────────────────────────────────────────────────────────


@click.command()
@click.argument("slug")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompt.")
@json_option
@click.pass_context
def delete(ctx: click.Context, slug: str, yes: bool, as_json: bool) -> None:
    """Delete (soft) a memo by slug."""
    if not yes and not as_json:
        click.confirm(f"确认删除笔记 {slug}？", abort=True)

    def _action(client):
        client.delete_memo(slug)
        return {"slug": slug, "deleted": True}

    def _render(data: dict[str, Any]) -> None:
        print_success(f"笔记已删除（slug: {slug}）")

    handle_command(ctx, action=_action, render=_render, as_json=as_json)


# ─── search ────────────────────────────────────────────────────────────────


@click.command()
@click.argument("keyword")
@click.option("--tag", default=None, help="Filter by tag name.")
@json_option
@click.pass_context
def search(ctx: click.Context, keyword: str, tag: str | None, as_json: bool) -> None:
    """Search memos by keyword (fetches all memos, filters locally)."""
    from ..formatter_utils import print_info

    if not as_json:
        print_info("正在拉取全量笔记进行搜索…")

    try:
        all_memos = run_client_action(ctx, lambda c: c.list_all_memos())
    except Exception as exc:
        from ..exceptions import FlomoApiError
        if isinstance(exc, FlomoApiError):
            exit_for_error(exc, as_json=as_json)
        raise

    keyword_lower = keyword.lower()

    def _matches(memo: dict[str, Any]) -> bool:
        text = html_to_text(memo.get("content", "")).lower()
        tags = [t.lower() for t in memo.get("tags", [])]
        if tag and tag.lower() not in tags:
            return False
        return keyword_lower in text or any(keyword_lower in t for t in tags)

    results = [m for m in all_memos if _matches(m)]
    formatted = _format_memos(results)

    if as_json:
        from ._common import _emit_json
        _emit_json(success_payload(formatted, total=len(results)))
    else:
        render_search_results(results, keyword)


# ─── related ───────────────────────────────────────────────────────────────


@click.command()
@click.argument("slug")
@json_option
@click.pass_context
def related(ctx: click.Context, slug: str, as_json: bool) -> None:
    """Show memos semantically related to a given memo."""
    handle_command(
        ctx,
        action=lambda c: c.get_related_memos(slug),
        render=render_related_memos,
        as_json=as_json,
    )


# ─── tags ──────────────────────────────────────────────────────────────────


@click.command()
@json_option
@click.pass_context
def tags(ctx: click.Context, as_json: bool) -> None:
    """Show the tag tree."""
    handle_command(
        ctx,
        action=lambda c: c.get_tag_tree(),
        render=render_tag_tree,
        as_json=as_json,
    )


# ─── review ────────────────────────────────────────────────────────────────


@click.command()
@json_option
@click.pass_context
def review(ctx: click.Context, as_json: bool) -> None:
    """Show today's daily review memos."""
    handle_command(
        ctx,
        action=lambda c: _format_memos(c.get_daily_review()),
        render=render_daily_review,
        as_json=as_json,
    )
