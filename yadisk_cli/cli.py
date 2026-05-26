import asyncio
from pathlib import Path
from typing import Optional

import typer

from yadisk_cli.auth import login_device_flow, login_with_token, get_client_from_token
from yadisk_cli.config import (
    load_config,
    save_config,
    delete_token,
    get_download_dir,
    set_download_dir,
    get_active_account,
    set_active_account,
    list_accounts,
    get_token_path,
)

app = typer.Typer(invoke_without_command=True, no_args_is_help=False)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    download_dir: Optional[str] = typer.Option(None, "--download-dir", "-d", help="Default download directory"),
    account: Optional[str] = typer.Option(None, "--account", "-a", help="Account name"),
):
    if ctx.invoked_subcommand is not None:
        return

    from yadisk_cli.app import YadiskApp
    from yadisk_cli.client import get_async_client

    account_name = account or get_active_account()
    asyncio.run(run_tui(get_async_client, YadiskApp, download_dir, account_name))


async def run_tui(
    get_async_client,
    yadisk_app_cls,
    download_dir: Optional[str] = None,
    account_name: str = "",
):
    if not account_name:
        accounts = list_accounts()
        if not accounts:
            typer.echo("No accounts found. Run 'yd login' first.")
            raise typer.Exit(code=1)
        account_name = accounts[0]
        set_active_account(account_name)

    client = await get_async_client(account_name)
    if client is None:
        typer.echo(f"Account '{account_name}' is not authenticated or token expired.")
        typer.echo("Run 'yd login --account NAME' to authenticate.")
        raise typer.Exit(code=1)

    app = yadisk_app_cls(client=client, account_name=account_name, download_dir=download_dir)
    await app.run_async()


@app.command()
def login(
    account_name: str = typer.Argument("default", help="Account name"),
    client_id: Optional[str] = typer.Option(None, "--client-id", "-i", help="Yandex OAuth client ID"),
    client_secret: Optional[str] = typer.Option(None, "--client-secret", "-s", help="Yandex OAuth client secret"),
    token: Optional[str] = typer.Option(None, "--token", "-t", help="Direct OAuth access token"),
):
    """Authenticate with Yandex.Disk"""
    if token:
        client = login_with_token(token, account_name)
    else:
        client = login_device_flow(client_id=client_id or "", client_secret=client_secret or "", account_name=account_name)
    if client:
        typer.echo(f"Successfully logged in as '{account_name}'!")


@app.command()
def logout(
    account_name: Optional[str] = typer.Argument(None, help="Account name (default: active account)"),
):
    """Remove authentication token"""
    target = account_name or get_active_account()
    if not target:
        typer.echo("No account specified and no active account set.")
        raise typer.Exit(code=1)
    delete_token(target)
    typer.echo(f"Logged out from '{target}'.")


@app.command()
def status(
    account_name: Optional[str] = typer.Option(None, "--account", "-a", help="Account name (default: active account)"),
):
    """Show Yandex.Disk status and quota"""
    target = account_name or get_active_account()
    if not target:
        typer.echo("No account specified and no active account set.")
        raise typer.Exit(code=1)
    client = get_client_from_token(target)
    if client is None:
        typer.echo(f"Account '{target}' is not authenticated.")
        raise typer.Exit(code=1)
    info = client.get_disk_info()
    total = info["total_space"]
    used = info["used_space"]
    free = total - used
    typer.echo(f"Account: {target}")
    typer.echo(f"Total: {_fmt_size(total)}")
    typer.echo(f"Used:  {_fmt_size(used)}")
    typer.echo(f"Free:  {_fmt_size(free)}")


@app.command()
def accounts(
    switch: Optional[str] = typer.Option(None, "--switch", "-s", help="Switch to account"),
    rename: Optional[str] = typer.Option(None, "--rename", "-r", help="Old account name"),
    new_name: Optional[str] = typer.Option(None, "--new-name", "-n", help="New account name"),
):
    """List, switch, or rename accounts"""
    if switch:
        all_accounts = list_accounts()
        if switch not in all_accounts:
            typer.echo(f"Account '{switch}' not found.")
            raise typer.Exit(code=1)
        set_active_account(switch)
        typer.echo(f"Switched to account '{switch}'.")
        return

    if rename and new_name:
        old_path = get_token_path(rename)
        if not old_path.exists():
            typer.echo(f"Account '{rename}' not found.")
            raise typer.Exit(code=1)
        new_path = get_token_path(new_name)
        if new_path.exists():
            typer.echo(f"Account '{new_name}' already exists.")
            raise typer.Exit(code=1)
        old_path.rename(new_path)
        active = get_active_account()
        if active == rename:
            set_active_account(new_name)
        typer.echo(f"Renamed account '{rename}' to '{new_name}'.")
        return

    all_accounts = list_accounts()
    active = get_active_account()
    if not all_accounts:
        typer.echo("No accounts found. Run 'yd login' to add one.")
        return
    typer.echo("Accounts:")
    for name in all_accounts:
        marker = "*" if name == active else " "
        typer.echo(f"  {marker} {name}")
    typer.echo(f"\nActive: {active or '(none)'}")


@app.command()
def config(
    key: Optional[str] = typer.Argument(None, help="Config key to show/set"),
    value: Optional[str] = typer.Argument(None, help="New value"),
):
    """View or change configuration"""
    cfg = load_config()
    if key is None:
        typer.echo("Current config:")
        for k, v in cfg.items():
            typer.echo(f"  {k} = {v}")
        return
    if value is not None:
        cfg[key] = value
        save_config(cfg)
        typer.echo(f"Set {key} = {value}")
    else:
        if key in cfg:
            typer.echo(cfg[key])
        else:
            typer.echo(f"Unknown key: {key}")


def _fmt_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"
