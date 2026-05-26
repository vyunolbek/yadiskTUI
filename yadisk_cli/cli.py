import asyncio
from pathlib import Path
from typing import Optional

import typer

from yadisk_cli.auth import login_device_flow, login_with_token, get_client_from_token
from yadisk_cli.config import load_config, save_config, delete_token, get_download_dir, set_download_dir

app = typer.Typer(invoke_without_command=True, no_args_is_help=False)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    download_dir: Optional[str] = typer.Option(None, "--download-dir", "-d", help="Default download directory"),
):
    if ctx.invoked_subcommand is not None:
        return

    from yadisk_cli.app import YadiskApp
    from yadisk_cli.client import get_async_client
    asyncio.run(run_tui(get_async_client, YadiskApp, download_dir))


async def run_tui(
    get_async_client,
    yadisk_app_cls,
    download_dir: Optional[str] = None,
):
    client = await get_async_client()
    if client is None:
        typer.echo("Not authenticated. Run 'yd login' first.")
        raise typer.Exit(code=1)

    app = yadisk_app_cls(client=client, download_dir=download_dir)
    await app.run_async()


@app.command()
def login(
    client_id: Optional[str] = typer.Option(None, "--client-id", "-i", help="Yandex OAuth client ID"),
    client_secret: Optional[str] = typer.Option(None, "--client-secret", "-s", help="Yandex OAuth client secret"),
    token: Optional[str] = typer.Option(None, "--token", "-t", help="Direct OAuth access token"),
):
    """Authenticate with Yandex.Disk"""
    if token:
        client = login_with_token(token)
    else:
        client = login_device_flow(client_id=client_id or "", client_secret=client_secret or "")
    if client:
        typer.echo("Successfully logged in!")


@app.command()
def logout():
    """Remove authentication token"""
    delete_token()
    typer.echo("Logged out.")


@app.command()
def status():
    """Show Yandex.Disk status and quota"""
    client = get_client_from_token()
    if client is None:
        typer.echo("Not authenticated. Run 'yd login' first.")
        raise typer.Exit(code=1)
    info = client.get_disk_info()
    total = info["total_space"]
    used = info["used_space"]
    free = total - used
    typer.echo(f"Total: {_fmt_size(total)}")
    typer.echo(f"Used:  {_fmt_size(used)}")
    typer.echo(f"Free:  {_fmt_size(free)}")


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
