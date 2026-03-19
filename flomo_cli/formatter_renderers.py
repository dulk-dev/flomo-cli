"""Rich rendering functions for Flomo CLI output."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .formatter_utils import format_tags, html_to_text, print_info, truncate

console = Console()


# ─── Memo renderers ───────────────────────────────────────────────────────


def render_memo_list(memos: list[dict[str, Any]], *, has_more: bool = False) -> None:
    """Render a list of memos as a Rich table."""
    if not memos:
        console.print("[dim]暂无笔记[/dim]")
        return

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("时间", style="dim", min_width=16)
    table.add_column("标签", min_width=10)
    table.add_column("内容")

    for i, memo in enumerate(memos, 1):
        content_text = html_to_text(memo.get("content", ""))
        tags = memo.get("tags", [])
        updated_at = memo.get("updated_at", "-")
        # Show only date+time up to minute
        time_short = updated_at[:16] if len(updated_at) >= 16 else updated_at
        tag_str = " ".join(f"#{t}" for t in tags) if tags else "-"

        table.add_row(
            str(i),
            time_short,
            f"[cyan]{tag_str}[/cyan]" if tags else "[dim]-[/dim]",
            truncate(content_text, 55),
        )

    console.print(table)
    if has_more:
        print_info("还有更多笔记，使用 --limit 增大数量或 flomo search 进行搜索")


def render_memo(memo: dict[str, Any]) -> None:
    """Render a single memo as a Rich panel."""
    content_text = html_to_text(memo.get("content", ""))
    tags = memo.get("tags", [])
    tag_str = format_tags(tags)
    files = memo.get("files", [])

    meta_lines = [
        f"[dim]slug   [/dim] {memo.get('slug', '-')}",
        f"[dim]创建时间[/dim] {memo.get('created_at', '-')}",
        f"[dim]更新时间[/dim] {memo.get('updated_at', '-')}",
        f"[dim]标签   [/dim] {tag_str}",
    ]
    if files:
        meta_lines.append(f"[dim]附件   [/dim] {len(files)} 个")

    header = "\n".join(meta_lines)
    body = Text(content_text)

    console.print(Panel(header, title="[bold]笔记信息[/bold]", expand=False))
    console.print(Padding(body, (1, 2)))

    if files:
        file_table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
        file_table.add_column("#", style="dim", width=3, justify="right")
        file_table.add_column("类型", width=6)
        file_table.add_column("文件名")
        file_table.add_column("大小", justify="right", width=10)
        file_table.add_column("URL")
        for i, f in enumerate(files, 1):
            size = f.get("size", 0)
            size_str = f"{size / 1024:.0f} KB" if size else "-"
            url = f.get("url", "")
            url_short = url[:60] + "…" if len(url) > 60 else url
            file_table.add_row(
                str(i),
                f.get("type", "-"),
                f.get("name", "-"),
                size_str,
                f"[link={url}]{url_short}[/link]" if url else "-",
            )
        console.print()
        console.print(Panel(file_table, title="[bold]附件[/bold]", expand=False))


def render_related_memos(related: list[dict[str, Any]]) -> None:
    """Render related memos with similarity scores."""
    if not related:
        console.print("[dim]未找到相关笔记[/dim]")
        return

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("相似度", width=7, justify="right")
    table.add_column("时间", style="dim", min_width=16)
    table.add_column("标签", min_width=8)
    table.add_column("内容")

    for i, item in enumerate(related, 1):
        memo = item.get("memo", {})
        similarity = item.get("similarity", "0")
        try:
            sim_pct = f"{float(similarity) * 100:.1f}%"
        except (ValueError, TypeError):
            sim_pct = "-"

        content_text = html_to_text(memo.get("content", ""))
        tags = memo.get("tags", [])
        updated_at = memo.get("updated_at", memo.get("created_at", "-"))
        time_short = updated_at[:16] if len(updated_at) >= 16 else updated_at
        tag_str = " ".join(f"#{t}" for t in tags) if tags else "-"

        table.add_row(
            str(i),
            f"[green]{sim_pct}[/green]",
            time_short,
            f"[cyan]{tag_str}[/cyan]" if tags else "[dim]-[/dim]",
            truncate(content_text, 50),
        )

    console.print(table)
    console.print(f"[dim]共 {len(related)} 条相关笔记[/dim]")


def render_tag_tree(tags: Any) -> None:
    """Render tag tree from the API response.

    The API returns ``{"tag_tree": ["tag/sub", ...]}`` — a flat list of
    slash-delimited path strings that we render as an indented hierarchy.
    """
    # Unwrap various possible shapes
    tag_strings: list[str] = []
    if isinstance(tags, dict):
        raw = tags.get("tag_tree", tags.get("tags", []))
        if isinstance(raw, list):
            tag_strings = [str(t) for t in raw]
    elif isinstance(tags, list):
        # Could be a list of strings or a list of objects
        if tags and isinstance(tags[0], str):
            tag_strings = tags
        else:
            # Objects with 'name' key
            for node in tags:
                if isinstance(node, dict):
                    tag_strings.append(node.get("name", ""))

    if not tag_strings:
        console.print("[dim]暂无标签[/dim]")
        return

    console.print(f"[bold]标签[/bold] [dim]共 {len(tag_strings)} 个[/dim]")
    for tag in tag_strings:
        parts = tag.split("/")
        indent = "  " * (len(parts) - 1)
        label = parts[-1]
        console.print(f"{indent}[cyan]#{label}[/cyan]")


def render_daily_review(memos: list[dict[str, Any]]) -> None:
    """Render daily review memos."""
    if not memos:
        console.print("[dim]今日暂无回顾笔记[/dim]")
        return

    console.print(f"[bold]每日回顾[/bold] [dim]共 {len(memos)} 条[/dim]\n")
    for i, memo in enumerate(memos, 1):
        content_text = html_to_text(memo.get("content", ""))
        tags = memo.get("tags", [])
        created_at = memo.get("created_at", "-")
        tag_str = format_tags(tags)

        meta = f"[dim]{created_at}[/dim]  {tag_str}" if tags else f"[dim]{created_at}[/dim]"
        console.print(
            Panel(
                f"{meta}\n\n{content_text}",
                title=f"[bold]#{i}[/bold] [dim]{memo.get('slug', '')}[/dim]",
                expand=False,
                padding=(1, 2),
            )
        )


def render_search_results(memos: list[dict[str, Any]], keyword: str) -> None:
    """Render search results with keyword highlighted."""
    if not memos:
        console.print(f'[dim]未找到包含 "{keyword}" 的笔记[/dim]')
        return

    console.print(f'[bold]搜索结果[/bold] [dim]"{keyword}"[/dim] 共 {len(memos)} 条')
    render_memo_list(memos)
