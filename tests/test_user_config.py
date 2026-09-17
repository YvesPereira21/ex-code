"""Unit tests for user workspace configuration management."""

from pathlib import Path
from unittest.mock import patch

import pytest

from ex_code.cli.ui import select_directory
from ex_code.core.user_config import (
    ENV_WORKSPACE_DIR,
    get_default_workspace_dir,
    set_default_workspace_dir,
)


@pytest.fixture(autouse=True)
def isolate_test_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ensure tests run in a clean isolated directory without picking up repository .env."""
    monkeypatch.chdir(tmp_path)


def test_get_default_workspace_dir_from_env(tmp_path: Path):
    custom_dir = tmp_path / "env_projects"
    custom_dir.mkdir()

    with patch.dict("os.environ", {ENV_WORKSPACE_DIR: str(custom_dir)}):
        result = get_default_workspace_dir()
        assert result == custom_dir.resolve()


def test_get_default_workspace_dir_from_config_file(tmp_path: Path):
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    config_file = fake_home / ".excode" / "config.json"
    config_file.parent.mkdir(parents=True)
    target_workspace = tmp_path / "saved_projects"
    target_workspace.mkdir()

    config_file.write_text(
        f'{{"workspace_dir": "{target_workspace}"}}', encoding="utf-8"
    )

    with (
        patch.dict("os.environ", {}, clear=True),
        patch("pathlib.Path.home", return_value=fake_home),
    ):
        result = get_default_workspace_dir()
        assert result == target_workspace.resolve()


def test_env_takes_precedence_over_config_file(tmp_path: Path):
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    config_file = fake_home / ".excode" / "config.json"
    config_file.parent.mkdir(parents=True)
    file_workspace = tmp_path / "file_workspace"
    file_workspace.mkdir()
    config_file.write_text(f'{{"workspace_dir": "{file_workspace}"}}', encoding="utf-8")

    env_workspace = tmp_path / "env_workspace"
    env_workspace.mkdir()

    with (
        patch.dict("os.environ", {ENV_WORKSPACE_DIR: str(env_workspace)}),
        patch("pathlib.Path.home", return_value=fake_home),
    ):
        result = get_default_workspace_dir()
        assert result == env_workspace.resolve()


def test_set_default_workspace_dir(tmp_path: Path):
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    new_workspace = tmp_path / "my_new_workspace"
    new_workspace.mkdir()

    with patch("pathlib.Path.home", return_value=fake_home):
        saved = set_default_workspace_dir(new_workspace)
        assert saved == new_workspace.resolve()

        # Verify read back
        read_back = get_default_workspace_dir()
        assert read_back == new_workspace.resolve()


def test_select_directory_uses_default_workspace(tmp_path: Path):
    workspace = tmp_path / "auto_workspace"
    workspace.mkdir()

    with (
        patch("ex_code.cli.ui.get_default_workspace_dir", return_value=workspace),
        patch("InquirerPy.inquirer.select") as mock_select,
    ):
        mock_select.return_value.execute.return_value = ("select", workspace)
        selected = select_directory(start_path=None)
        assert selected == workspace


def test_get_default_workspace_dir_from_local_env(tmp_path: Path):
    proj_dir = tmp_path / "proj"
    proj_dir.mkdir()
    target_workspace = tmp_path / "env_file_projects"
    target_workspace.mkdir()

    env_file = proj_dir / ".env"
    env_file.write_text(f"EXCODE_WORKSPACE_DIR={target_workspace}\n", encoding="utf-8")

    with (
        patch.dict("os.environ", {}, clear=True),
        patch("pathlib.Path.cwd", return_value=proj_dir),
    ):
        result = get_default_workspace_dir(start_path=proj_dir)
        assert result == target_workspace.resolve()


def test_local_env_takes_precedence_over_config_file(tmp_path: Path):
    proj_dir = tmp_path / "proj"
    proj_dir.mkdir()
    env_workspace = tmp_path / "env_workspace"
    env_workspace.mkdir()
    (proj_dir / ".env").write_text(
        f"EXCODE_WORKSPACE_DIR={env_workspace}\n", encoding="utf-8"
    )

    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    config_file = fake_home / ".excode" / "config.json"
    config_file.parent.mkdir(parents=True)
    file_workspace = tmp_path / "file_workspace"
    file_workspace.mkdir()
    config_file.write_text(f'{{"workspace_dir": "{file_workspace}"}}', encoding="utf-8")

    with (
        patch.dict("os.environ", {}, clear=True),
        patch("pathlib.Path.home", return_value=fake_home),
        patch("pathlib.Path.cwd", return_value=proj_dir),
    ):
        result = get_default_workspace_dir(start_path=proj_dir)
        assert result == env_workspace.resolve()


def test_set_default_workspace_dir_writes_to_env(tmp_path: Path):
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    target_env = tmp_path / "custom_proj" / ".env"
    new_workspace = tmp_path / "auto_persisted_workspace"
    new_workspace.mkdir()

    with patch("pathlib.Path.home", return_value=fake_home):
        saved = set_default_workspace_dir(
            new_workspace, target_env_file=target_env, write_to_env=True
        )
        assert saved == new_workspace.resolve()
        assert target_env.is_file()
        content = target_env.read_text(encoding="utf-8")
        assert f"EXCODE_WORKSPACE_DIR={new_workspace.resolve()}" in content
