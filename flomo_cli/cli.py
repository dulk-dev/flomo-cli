"""CLI entry point for flomo-cli."""

from __future__ import annotations

import logging

import click

from . import __version__
from .commands import auth, memo


@click.group()
@click.version_option(version=__version__, prog_name="flomo")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
@click.option("--token", default=None, help="Override authentication token.")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, token: str | None) -> None:
    """flomo — Flomo CLI via reverse-engineered API."""
    ctx.ensure_object(dict)
    ctx.obj["token"] = token

    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(name)s %(levelname)s %(message)s")


# ─── Auth commands ─────────────────────────────────────────────────────────

cli.add_command(auth.login)
cli.add_command(auth.logout)
cli.add_command(auth.status)

# ─── Memo commands ─────────────────────────────────────────────────────────

cli.add_command(memo.list_memos)
cli.add_command(memo.get)
cli.add_command(memo.new)
cli.add_command(memo.edit)
cli.add_command(memo.delete)
cli.add_command(memo.search)
cli.add_command(memo.related)
cli.add_command(memo.tags)
cli.add_command(memo.review)

if __name__ == "__main__":
    cli()
