"""Auth commands: login / logout / status."""

from __future__ import annotations

import click

from ..auth import clear_token, get_token, load_user_info, save_token
from ..client import FlomoClient
from ..exceptions import FlomoApiError, NotAuthenticatedError
from ..formatter_utils import emit_error, error_payload, print_error, print_success, success_payload
from ._common import json_option


@click.command()
@click.option("--email", prompt="Email / Phone", help="Flomo account email or phone.")
@click.option(
    "--password",
    prompt=True,
    hide_input=True,
    help="Flomo account password.",
)
@json_option
def login(email: str, password: str, as_json: bool) -> None:
    """Login with email and password, save token locally."""
    try:
        user = FlomoClient.login(email, password)
        save_token(user)
        if as_json:
            click.echo(
                __import__("json").dumps(
                    success_payload({"name": user.get("name"), "email": user.get("email")}),
                    ensure_ascii=False,
                )
            )
        else:
            print_success(f"登录成功，欢迎 {user.get('name', email)}")
    except FlomoApiError as exc:
        _exit_error(exc, as_json=as_json)


@click.command()
@json_option
def logout(as_json: bool) -> None:
    """Remove locally cached token."""
    existed = clear_token()
    if as_json:
        import json
        click.echo(json.dumps(success_payload({"cleared": existed}), ensure_ascii=False))
    elif existed:
        print_success("已退出登录，本地 Token 已清除")
    else:
        click.echo("当前未登录")


@click.command()
@json_option
@click.pass_context
def status(ctx: click.Context, as_json: bool) -> None:
    """Show current login status and user info."""
    token_override = ctx.obj.get("token") if ctx.obj else None
    try:
        token = get_token(token_override)
    except NotAuthenticatedError:
        if as_json:
            import json
            click.echo(
                json.dumps({"ok": False, "authenticated": False}, ensure_ascii=False)
            )
        else:
            click.echo("未登录。请执行 flomo login 或设置 FLOMO_TOKEN 环境变量。")
        return

    # Try to use cached info first, fall back to live API call
    user = load_user_info()
    if not user or not user.get("name"):
        try:
            with FlomoClient(token) as client:
                user = client.get_me()
        except FlomoApiError as exc:
            _exit_error(exc, as_json=as_json)
            return

    if as_json:
        import json
        payload = {
            "authenticated": True,
            "name": user.get("name"),
            "email": user.get("email"),
            "pro_type": user.get("pro_type"),
        }
        click.echo(json.dumps(success_payload(payload), ensure_ascii=False, indent=2))
    else:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_row("[dim]用户[/dim]", user.get("name", "-"))
        table.add_row("[dim]账号[/dim]", user.get("email", "-"))
        table.add_row("[dim]类型[/dim]", user.get("pro_type", "-"))
        console.print(table)


def _exit_error(exc: FlomoApiError, *, as_json: bool) -> None:
    from ..error_codes import error_code_for_exception

    code = error_code_for_exception(exc)
    if as_json:
        import json
        click.echo(json.dumps(error_payload(code, str(exc)), ensure_ascii=False))
    else:
        print_error(str(exc))
    raise SystemExit(1) from None
