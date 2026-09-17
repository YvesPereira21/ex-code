"""Global user settings, local .env files, and workspace directory resolution."""

import json
import os
from pathlib import Path

ENV_WORKSPACE_DIR = "EXCODE_WORKSPACE_DIR"
CONFIG_DIRNAME = ".excode"
CONFIG_FILENAME = "config.json"


def get_user_config_path() -> Path:
    """Return the path to the global user config file."""
    return Path.home() / CONFIG_DIRNAME / CONFIG_FILENAME


def find_local_env_file(start_path: Path | None = None) -> Path | None:
    """Find .env file in start_path or traversing up to the project root."""
    curr = (start_path or Path.cwd()).resolve()
    for parent in [curr, *curr.parents]:
        env_file = parent / ".env"
        if env_file.is_file():
            return env_file
        if parent == Path.home() or parent == parent.parent:
            break
    return None


def read_env_file(env_path: Path) -> dict[str, str]:
    """Read key-value pairs from a .env file."""
    values: dict[str, str] = {}
    if not env_path.is_file():
        return values
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k:
                    values[k] = v
    except OSError:
        pass
    return values


def write_env_var(env_path: Path, key: str, value: str) -> None:
    """Update or append an environment variable in a .env file."""
    lines: list[str] = []
    found = False
    if env_path.is_file():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#") and "=" in stripped:
                        k, _ = stripped.split("=", 1)
                        if k.strip() == key:
                            lines.append(f"{key}={value}\n")
                            found = True
                            continue
                    lines.append(line)
        except OSError:
            lines = []

    if not found:
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append(f"{key}={value}\n")

    env_path.parent.mkdir(parents=True, exist_ok=True)
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def get_default_workspace_dir(start_path: Path | None = None) -> Path | None:
    """
    Resolve the default workspace directory for projects.

    Priority:
    1. Environment variable EXCODE_WORKSPACE_DIR
    2. Local .env file (EXCODE_WORKSPACE_DIR key)
    3. Global config file ~/.excode/config.json ('workspace_dir' key)
    4. None (fallback to current working directory)
    """
    env_dir = os.environ.get(ENV_WORKSPACE_DIR)
    if env_dir and env_dir.strip():
        resolved = Path(env_dir.strip()).expanduser().resolve()
        return resolved

    # Check local .env file
    env_file = find_local_env_file(start_path)
    if env_file:
        env_vars = read_env_file(env_file)
        val = env_vars.get(ENV_WORKSPACE_DIR)
        if val and val.strip():
            return Path(val.strip()).expanduser().resolve()

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


def set_default_workspace_dir(
    path: Path | str,
    target_env_file: Path | None = None,
    write_to_env: bool = True,
) -> Path:
    """Persist the default workspace directory in ~/.excode/config.json and .env."""
    resolved = Path(path).expanduser().resolve()

    # 1. Update ~/.excode/config.json
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

    # 2. Update or create .env if found or target specified
    if write_to_env:
        env_file = target_env_file or find_local_env_file()
        if env_file:
            try:
                write_env_var(env_file, ENV_WORKSPACE_DIR, str(resolved))
            except OSError:
                pass

    return resolved
