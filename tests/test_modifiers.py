"""Unit tests for surgical code modifiers (FastAPI and Spring Boot)."""

from pathlib import Path

from ex_code.core.models import (
    EntityDefinition,
    FieldDefinition,
    ProjectConfig,
    create_pk_field,
)
from ex_code.core.types import ArchitectureType, FrameworkType
from ex_code.generators.fastapi.generator import FastAPIGenerator
from ex_code.generators.springboot.generator import SpringBootGenerator
from ex_code.modifiers.base import generate_diff
from ex_code.modifiers.fastapi_modifier import FastAPICodeModifier
from ex_code.modifiers.springboot_modifier import SpringBootCodeModifier


def test_generate_diff():
    orig = "line1\nline2\n"
    mod = "line1\nline2_modified\nline3\n"
    diff = generate_diff(orig, mod, "test.py")
    assert "+line2_modified" in diff
    assert "-line2" in diff
    assert "+line3" in diff


def test_fastapi_modifier_add_and_remove_field(tmp_path: Path):
    proj_dir = tmp_path / "fastapi_mod_test"
    pk = create_pk_field("User", FrameworkType.FASTAPI)
    user = EntityDefinition(
        name="User", fields=[pk, FieldDefinition(name="name", type="str")]
    )

    config = ProjectConfig(
        name="fastapi-mod",
        output_path=str(proj_dir),
        framework=FrameworkType.FASTAPI,
        architecture=ArchitectureType.LAYERED,
        entities=[user],
    )
    FastAPIGenerator().generate_project(config)

    # Add a custom method to user.py to verify it will be preserved
    user_file = proj_dir / "app" / "models" / "user.py"
    user_code = user_file.read_text()
    user_code += "\n    def custom_helper(self):\n        # My custom comment\n        return True\n"
    user_file.write_text(user_code)

    modifier = FastAPICodeModifier(proj_dir, config)

    # 1. Add field
    new_field = FieldDefinition(name="age", type="int", is_nullable=True)
    changes = modifier.add_field("User", new_field)
    assert len(changes) >= 1

    # Apply changes with backup
    backup_path = modifier.apply_changes(changes, make_backup=True)
    assert backup_path is not None
    assert backup_path.is_dir()

    # Verify field was added and custom helper preserved
    updated_user_code = user_file.read_text()
    assert "age: Mapped[int | None]" in updated_user_code
    assert "def custom_helper(self):" in updated_user_code
    assert "# My custom comment" in updated_user_code

    # 2. Remove field
    rm_changes = modifier.remove_field("User", "age")
    modifier.apply_changes(rm_changes, make_backup=False)

    post_rm_code = user_file.read_text()
    assert "age: Mapped[int | None]" not in post_rm_code
    assert "def custom_helper(self):" in post_rm_code


def test_springboot_modifier_add_and_remove_field(tmp_path: Path):
    proj_dir = tmp_path / "sb_mod_test"
    pk = create_pk_field("Account", FrameworkType.SPRINGBOOT)
    acc = EntityDefinition(
        name="Account", fields=[pk, FieldDefinition(name="number", type="String")]
    )

    config = ProjectConfig(
        name="sb-mod",
        output_path=str(proj_dir),
        framework=FrameworkType.SPRINGBOOT,
        architecture=ArchitectureType.LAYERED,
        entities=[acc],
    )
    SpringBootGenerator().generate_project(config)

    modifier = SpringBootCodeModifier(proj_dir, config)

    # 1. Add field
    balance_field = FieldDefinition(name="balance", type="BigDecimal")
    changes = modifier.add_field("Account", balance_field)
    assert len(changes) >= 1

    backup_path = modifier.apply_changes(changes, make_backup=True)
    assert backup_path is not None
    assert backup_path.is_dir()

    # Verify Account.java
    java_file = next((proj_dir / "src" / "main" / "java").rglob("Account.java"))
    java_code = java_file.read_text()
    assert "private BigDecimal balance;" in java_code
    assert '@Column(name = "balance"' in java_code

    # 2. Remove field
    rm_changes = modifier.remove_field("Account", "balance")
    modifier.apply_changes(rm_changes, make_backup=False)

    post_rm_java = java_file.read_text()
    assert "private BigDecimal balance;" not in post_rm_java
