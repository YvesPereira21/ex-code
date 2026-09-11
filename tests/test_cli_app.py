"""Unit tests for the main CLI application orchestrator."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ex_code.__main__ import main
from ex_code.cli.app import CLIApplication, display_welcome_banner, run_app


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
        mock_select.return_value.execute.side_effect = RuntimeError("Non-interactive error")
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
