import os
from pathlib import Path
from typing import Optional

import tomllib
import tomli_w

CONFIG_DIR = Path.home() / ".config" / "yadisk_cli"
CONFIG_PATH = CONFIG_DIR / "config.toml"
TOKEN_PATH = CONFIG_DIR / "token.json"

DEFAULT_CONFIG = {
    "download_dir": str(Path.home() / "Downloads"),
    "yandex_client_id": "",
    "yandex_client_secret": "",
}


def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    ensure_config_dir()
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


def save_token(token_data):
    ensure_config_dir()
    import json
    if hasattr(token_data, "__annotations__"):
        data = {}
        for field in token_data.__annotations__:
            val = getattr(token_data, field, None)
            if val is not None:
                data[field] = val
    else:
        data = dict(token_data)
    with open(TOKEN_PATH, "w") as f:
        json.dump(data, f)


def load_token() -> Optional[dict]:
    if TOKEN_PATH.exists():
        import json
        with open(TOKEN_PATH) as f:
            return json.load(f)
    return None


def delete_token():
    if TOKEN_PATH.exists():
        TOKEN_PATH.unlink()
