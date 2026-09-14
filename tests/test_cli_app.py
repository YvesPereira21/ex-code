"""Unit tests for the main CLI application orchestrator."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ex_code.__main__ import main
from ex_code.cli.app import CLIApplication, display_welcome_banner, run_app
from ex_code.cli.ui import select_directory


def test_display_welcome_banner() -> None:
    """Ensure welcome banner renders without exceptions."""
    display_welcome_banner()


def test_cli_app_exit() -> None:
    """Test selecting 'exit' closes the application with status 0."""
    app = CLIApplication()
    with patch("InquirerPy.inquirer.select") as mock_select:
        mock_select.return_value.execute.return_value = "exit"
        result = app.run()
        assert result == 0


def test_cli_app_create_flow() -> None:
    """Test selecting 'create' invokes create wizard and returns to loop until 'exit'."""
    app = CLIApplication()
    app.create_wizard = MagicMock()
    app.create_wizard.run.return_value = Path("/tmp/fake_project")

    with patch("InquirerPy.inquirer.select") as mock_select:
        mock_select.return_value.execute.side_effect = ["create", "exit"]
        result = app.run()
        assert result == 0
        app.create_wizard.run.assert_called_once()


def test_cli_app_edit_flow() -> None:
    """Test selecting 'edit' invokes edit wizard and returns to loop until 'exit'."""
    app = CLIApplication()
    app.edit_wizard = MagicMock()
    app.edit_wizard.run.return_value = Path("/tmp/fake_project")

    with patch("InquirerPy.inquirer.select") as mock_select:
        mock_select.return_value.execute.side_effect = ["edit", "exit"]
        result = app.run()
        assert result == 0
        app.edit_wizard.run.assert_called_once()


def test_cli_app_keyboard_interrupt() -> None:
    """Test graceful handling of KeyboardInterrupt in main menu."""
    app = CLIApplication()
    with patch("InquirerPy.inquirer.select") as mock_select:
        mock_select.return_value.execute.side_effect = KeyboardInterrupt()
        result = app.run()
        assert result == 0


def test_cli_app_unexpected_error_handled_interactive() -> None:
    """Test unexpected exception in interactive terminal recovers until exit."""
    app = CLIApplication()
    with (
        patch("sys.stdin.isatty", return_value=True),
        patch("InquirerPy.inquirer.select") as mock_select,
    ):
        mock_select.return_value.execute.side_effect = [
            RuntimeError("Simulated menu failure"),
            "exit",
        ]
        result = app.run()
        assert result == 0


def test_cli_app_non_interactive_error_exits() -> None:
    """Test unexpected exception in non-interactive environment terminates safely with code 1."""
    app = CLIApplication()
    with (
        patch("sys.stdin.isatty", return_value=False),
        patch("InquirerPy.inquirer.select") as mock_select,
    ):
        mock_select.return_value.execute.side_effect = RuntimeError(
            "Non-interactive error"
        )
        result = app.run()
        assert result == 1


def test_run_app_and_main_entrypoint() -> None:
    """Test run_app and main() entrypoint wrapper."""
    with patch("ex_code.cli.app.CLIApplication.run", return_value=0):
        assert run_app() == 0

    with (
        patch("ex_code.__main__.run_app", return_value=0),
        pytest.raises(SystemExit) as exc_info,
    ):
        main()
    assert exc_info.value.code == 0


def test_select_directory_select_current(tmp_path: Path) -> None:
    """Test selecting current directory immediately."""
    with patch("InquirerPy.inquirer.select") as mock_select:
        mock_select.return_value.execute.return_value = ("select", tmp_path)
        selected = select_directory(start_path=tmp_path)
        assert selected == tmp_path


def test_select_directory_navigate_and_select(tmp_path: Path) -> None:
    """Test navigating to a subdirectory and then selecting it."""
    sub_dir = tmp_path / "subproject"
    sub_dir.mkdir()

    with patch("InquirerPy.inquirer.select") as mock_select:
        mock_select.return_value.execute.side_effect = [
            ("nav", sub_dir),
            ("select", sub_dir),
        ]
        selected = select_directory(start_path=tmp_path)
        assert selected == sub_dir


def test_select_directory_manual_input(tmp_path: Path) -> None:
    """Test choosing manual text input for path."""
    target = tmp_path / "custom_dir"
    with (
        patch("InquirerPy.inquirer.select") as mock_select,
        patch("InquirerPy.inquirer.text") as mock_text,
    ):
        mock_select.return_value.execute.return_value = ("manual", None)
        mock_text.return_value.execute.return_value = str(target)
        selected = select_directory(start_path=tmp_path)
        assert selected == target.resolve()


def test_select_directory_select_file(tmp_path: Path) -> None:
    """Test selecting a file in select_directory."""
    test_file = tmp_path / "model.py"
    test_file.touch()

    with patch("InquirerPy.inquirer.select") as mock_select:
        mock_select.return_value.execute.return_value = ("select", test_file)
        selected = select_directory(start_path=tmp_path, show_files=True)
        assert selected == test_file


def test_display_editable_files_table() -> None:
    """Ensure display_editable_files_table renders without exceptions."""
    from ex_code.cli.ui import display_editable_files_table

    # Empty list
    display_editable_files_table([])

    # Populated list
    display_editable_files_table(
        [
            {
                "type": "Model (Entidade)",
                "entity": "User",
                "filename": "user.py",
                "rel_path": "app/models/user.py",
            }
        ]
    )
