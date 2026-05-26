# AGENTS.md — yadisk-cli

## Quick reference

```bash
# venv and editable install
python3 -m venv .venv && .venv/bin/pip install -e .

# CLI entry point (after install: yd → yadisk_cli.cli:app)
.venv/bin/yd                        # launch TUI
.venv/bin/yd login --token <TOKEN>  # auth with OAuth token
.venv/bin/yd login                  # device-flow auth (needs client_id/secret in config)
.venv/bin/yd status                 # show disk info
.venv/bin/yd config <key> <value>   # set config key
```

## Architecture

- **TUI app** built on [Textual](https://textual.textualize.io/) (>=1.0). The `App` subclass is `YadiskApp` in `yadisk_cli/app.py`.
- **Two-panel layout**: left = file browser (ListView), right = file preview (Static). Footer at bottom.
- **`yadisk_cli.client`** wraps `yadisk.AsyncClient` — all TUI I/O is async.
- **`yadisk_cli.auth`** uses **synchronous** `yadisk.Client` for login/token-refresh flows.
- **`yadisk_cli.config`** stores config at `~/.config/yadisk_cli/config.toml` (TOML) and tokens at `~/.config/yadisk_cli/token.json`.
- **Entry point**: `yd` console script defined in `pyproject.toml` → `yadisk_cli.cli:app` (Typer).

## Packages

Defined explicitly in `pyproject.toml` (`[tool.setuptools]`):
- `yadisk_cli` — app, auth, client, config, cli
- `yadisk_cli.widgets` — file_browser, file_preview, footer, dialogs

If you add a new subpackage, add it to the `packages` list in `pyproject.toml`.

## Build & dev

- **Build backend**: setuptools (pyproject.toml only — no `setup.py` or `setup.cfg`).
- **No tests, no lint config, no CI, no pre-commit hooks exist.**
- CSS is defined inline as a class-string on `YadiskApp` (`CSS = """..."""`) — there is no `.tcss` file.
- All user-facing strings and docs are in Russian.

## Gotchas

- `format_size` / `_fmt_size` is duplicated in `app.py`, `file_browser.py`, and `file_preview.py`. Consolidate into a shared utility before changing its behavior.
- `FileBrowser._load_id` is a concurrent-load-cancellation counter. New `load_directory` calls bump it; stale async loads check it and silently abort.
- `yadisk_cli.auth.get_client_from_token()` mutates the token file (refreshes or deletes on failure). Do not call it in read-only contexts.
- Config keys are validated ad-hoc in `cli.py` — `yandex_client_id`, `yandex_client_secret`, `download_dir` are the only recognized keys.
