"""Global user settings and workspace directory resolution."""

import json
import os
from pathlib import Path

ENV_WORKSPACE_DIR = "EXCODE_WORKSPACE_DIR"
CONFIG_DIRNAME = ".excode"
CONFIG_FILENAME = "config.json"


def get_user_config_path() -> Path:
    """Return the path to the global user config file."""
    return Path.home() / CONFIG_DIRNAME / CONFIG_FILENAME


def get_default_workspace_dir() -> Path | None:
    """
    Resolve the default workspace directory for projects.

    Priority:
    1. Environment variable EXCODE_WORKSPACE_DIR
    2. Global config file ~/.excode/config.json ('workspace_dir' key)
    3. None (fallback to current working directory)
    """
    env_dir = os.environ.get(ENV_WORKSPACE_DIR)
    if env_dir and env_dir.strip():
        resolved = Path(env_dir.strip()).expanduser().resolve()
        return resolved

    cfg_file = get_user_config_path()
    if cfg_file.is_file():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            ws = data.get("workspace_dir")
            if ws and str(ws).strip():
                return Path(str(ws).strip()).expanduser().resolve()
        except (json.JSONDecodeError, OSError):
            pass

    return None


def set_default_workspace_dir(path: Path | str) -> Path:
    """
    Persist the default workspace directory in ~/.excode/config.json.
    """
    resolved = Path(path).expanduser().resolve()
    cfg_file = get_user_config_path()
    cfg_file.parent.mkdir(parents=True, exist_ok=True)

    data: dict[str, str] = {}
    if cfg_file.is_file():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}

    data["workspace_dir"] = str(resolved)

    with open(cfg_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return resolved
