"""Unit tests for user workspace configuration management."""

from pathlib import Path
from unittest.mock import patch

from ex_code.cli.ui import select_directory
from ex_code.core.user_config import (
    ENV_WORKSPACE_DIR,
    get_default_workspace_dir,
    set_default_workspace_dir,
)


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
