import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

REPO_DIR = Path(__file__).resolve().parent.parent
VENV_DIR = Path(sys.prefix)


def get_current_version() -> str:
    pyproject = REPO_DIR / "pyproject.toml"
    if not pyproject.exists():
        return "0.0.0"
    import tomllib
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    return data.get("project", {}).get("version", "0.0.0")


def check_latest_version() -> Optional[str]:
    import urllib.request
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/vyunolbek/yadiskTUI/releases/latest",
            headers={
                "User-Agent": "yadisk-cli/update",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return data.get("tag_name", "")
    except Exception:
        return None


def is_newer(latest: str, current: str) -> bool:
    def parse(v: str) -> tuple:
        v = v.lstrip("v")
        parts = v.split(".")
        return tuple(int(p) if p.isdigit() else 0 for p in parts)

    return parse(latest) > parse(current)


def do_update() -> str:
    pip = VENV_DIR / "bin" / "pip"
    try:
        result = subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=str(REPO_DIR),
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return f"Git pull failed:\n{result.stderr.strip()}"

        result = subprocess.run(
            [str(pip), "install", "-e", str(REPO_DIR)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            return f"Dependency update failed:\n{result.stderr.strip()}"

        return f"Updated to {get_current_version()}"
    except subprocess.TimeoutExpired:
        return "Update timed out"
    except FileNotFoundError as e:
        return f"Command not found: {e.filename}"
    except Exception as e:
        return f"Update failed: {e}"
