import json
import os
from pathlib import Path
from typing import Optional

import tomllib
import tomli_w

CONFIG_DIR = Path.home() / ".config" / "yadisk_cli"
CONFIG_PATH = CONFIG_DIR / "config.toml"
TOKEN_PATH = CONFIG_DIR / "token.json"
ACCOUNTS_DIR = CONFIG_DIR / "accounts"

DEFAULT_CONFIG = {
    "download_dir": str(Path.home() / "Downloads"),
    "yandex_client_id": "",
    "yandex_client_secret": "",
    "active_account": "",
}


def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)


def _migrate_old_token():
    if TOKEN_PATH.exists():
        data = json.loads(TOKEN_PATH.read_text())
        with open(get_token_path("default"), "w") as f:
            json.dump(data, f)
        TOKEN_PATH.unlink()
        config = load_config()
        config["active_account"] = "default"
        save_config(config)


def load_config() -> dict:
    ensure_config_dir()
    _migrate_old_token()
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "rb") as f:
            return {**DEFAULT_CONFIG, **tomllib.load(f)}
    return dict(DEFAULT_CONFIG)


def save_config(config: dict):
    ensure_config_dir()
    with open(CONFIG_PATH, "wb") as f:
        tomli_w.dump(config, f)


def get_download_dir() -> str:
    return load_config().get("download_dir", str(Path.home() / "Downloads"))


def set_download_dir(path: str):
    config = load_config()
    config["download_dir"] = path
    save_config(config)


def get_active_account() -> str:
    config = load_config()
    return config.get("active_account", "") or ""


def set_active_account(name: str):
    config = load_config()
    config["active_account"] = name
    save_config(config)


def get_token_path(name: str) -> Path:
    return ACCOUNTS_DIR / f"{name}.json"


def list_accounts() -> list[str]:
    ensure_config_dir()
    names = []
    for f in sorted(ACCOUNTS_DIR.iterdir()):
        if f.suffix == ".json":
            names.append(f.stem)
    return names


def save_token(token_data, name: str):
    ensure_config_dir()
    if hasattr(token_data, "__annotations__"):
        data = {}
        for field in token_data.__annotations__:
            val = getattr(token_data, field, None)
            if val is not None:
                data[field] = val
    else:
        data = dict(token_data)
    path = get_token_path(name)
    with open(path, "w") as f:
        json.dump(data, f)


def load_token(name: Optional[str] = None) -> Optional[dict]:
    if name is None:
        name = get_active_account()
    if not name:
        return None
    path = get_token_path(name)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


def delete_token(name: Optional[str] = None):
    if name is None:
        name = get_active_account()
    if not name:
        return
    path = get_token_path(name)
    if path.exists():
        path.unlink()
