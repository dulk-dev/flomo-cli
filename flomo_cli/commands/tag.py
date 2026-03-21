"""Tag commands: rename."""

from __future__ import annotations

from typing import Any

import click

from ..formatter_utils import print_success
from ._common import handle_command, json_option


def _strip_hash(name: str) -> str:
    """Remove leading '#' if present — users may type ``#tag`` habitually."""
    return name.lstrip("#")


# ─── rename ───────────────────────────────────────────────────────────────


@click.command()
@click.argument("old_tag")
@click.argument("new_tag")
@json_option
@click.pass_context
def rename(ctx: click.Context, old_tag: str, new_tag: str, as_json: bool) -> None:
    """Rename a tag across all memos.

    OLD_TAG is the current tag name, NEW_TAG is the desired new name.
    Leading '#' is stripped automatically (e.g. '#work' → 'work').

    \b
    Examples:
      flomo tag rename 旧标签 新标签
      flomo tag rename "读书/旧子标签" "读书/新子标签"
    """
    old_tag = _strip_hash(old_tag)
    new_tag = _strip_hash(new_tag)

    if not old_tag or not new_tag:
        raise click.UsageError("标签名不能为空")
    if old_tag == new_tag:
        raise click.UsageError("新旧标签名相同，无需重命名")

    def _action(client: Any) -> dict[str, Any]:
        result = client.rename_tag(old_tag, new_tag)
        updated_num = result.get("updated_num", 0) if isinstance(result, dict) else 0
        return {
            "old_tag": old_tag,
            "new_tag": new_tag,
            "updated_num": updated_num,
        }

    def _render(data: dict[str, Any]) -> None:
        n = data.get("updated_num", 0)
        print_success(f"标签已重命名：#{old_tag} → #{new_tag}（影响 {n} 条笔记）")

    handle_command(ctx, action=_action, render=_render, as_json=as_json)
