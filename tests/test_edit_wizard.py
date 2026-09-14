"""Unit tests for EditProjectWizard."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from ex_code.cli.wizards.edit_wizard import EditProjectWizard
from ex_code.core.models import (
    EntityDefinition,
    FieldDefinition,
    ProjectConfig,
    create_pk_field,
)
from ex_code.core.types import ArchitectureType, FrameworkType
from ex_code.modifiers.fastapi_modifier import FastAPICodeModifier


def test_edit_wizard_actions(tmp_path: Path):
    proj_dir = tmp_path / "edit_wiz_test"
    proj_dir.mkdir()

    pk = create_pk_field("Item", FrameworkType.FASTAPI)
    item = EntityDefinition(
        name="Item", fields=[pk, FieldDefinition(name="name", type="str")]
    )

    config = ProjectConfig(
        name="edit-wiz",
        output_path=str(proj_dir),
        framework=FrameworkType.FASTAPI,
        architecture=ArchitectureType.LAYERED,
        entities=[item],
    )

    modifier = FastAPICodeModifier(proj_dir, config)
    wizard = EditProjectWizard()

    # Test _action_add_field with mock input
    with (
        patch("InquirerPy.inquirer.text") as mock_text,
        patch("InquirerPy.inquirer.select") as mock_select,
        patch("InquirerPy.inquirer.confirm") as mock_confirm,
    ):
        mock_text.return_value.execute.return_value = "description"
        mock_select.return_value.execute.return_value = "str"
        mock_confirm.return_value.execute.side_effect = [True, False]

        changes = wizard._action_add_field(modifier, item, FrameworkType.FASTAPI)
        assert (
            len(changes) == 0
        )  # Files do not physically exist on disk in empty dir, but method executes cleanly


def test_edit_wizard_preview_and_apply(tmp_path: Path):
    wizard = EditProjectWizard()
    mock_modifier = MagicMock()
    mock_modifier.apply_changes.return_value = tmp_path / ".excode/backups/123"

    sample_changes = [
        (tmp_path / "model.py", "class Item:\n", "class Item:\n    age: int\n")
    ]

    with patch("InquirerPy.inquirer.confirm") as mock_confirm:
        mock_confirm.return_value.execute.return_value = True
        wizard._preview_and_apply(mock_modifier, sample_changes)
        mock_modifier.apply_changes.assert_called_once_with(
            sample_changes, make_backup=True
        )


def test_edit_wizard_by_file_flow(tmp_path: Path):
    wizard = EditProjectWizard()
    config = MagicMock()
    modifier = MagicMock()

    editable_files = [
        {
            "type": "Model (Entidade)",
            "entity": "User",
            "filename": "user.py",
            "rel_path": "app/models/user.py",
            "abs_path": str(tmp_path / "app/models/user.py"),
        }
    ]

    with (
        patch("InquirerPy.inquirer.select") as mock_select,
        patch.object(wizard, "_edit_entity_flow") as mock_edit_entity,
    ):
        mock_select.return_value.execute.return_value = editable_files[0]
        wizard._edit_by_file_flow(modifier, config, editable_files)
        mock_edit_entity.assert_called_once_with(
            modifier, config, default_entity_name="User"
        )


def test_edit_wizard_schema_flow(tmp_path: Path):
    wizard = EditProjectWizard()
    pk = create_pk_field("Account", FrameworkType.FASTAPI)
    account = EntityDefinition(
        name="Account", fields=[pk, FieldDefinition(name="balance", type="float")]
    )
    config = ProjectConfig(
        name="schema-proj",
        output_path=str(tmp_path),
        framework=FrameworkType.FASTAPI,
        architecture=ArchitectureType.LAYERED,
        entities=[account],
    )
    modifier = FastAPICodeModifier(tmp_path, config)

    with (
        patch("InquirerPy.inquirer.select") as mock_select,
        patch.object(
            wizard,
            "_action_add_field",
            return_value=[(tmp_path / "dummy.py", "orig", "mod")],
        ),
        patch.object(wizard, "_preview_and_apply") as mock_preview,
    ):
        mock_select.return_value.execute.side_effect = [
            "Account",  # selected schema
            "add_field",  # action
        ]

        wizard._edit_schema_flow(modifier, config)
        mock_preview.assert_called_once()
