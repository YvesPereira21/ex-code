"""Unit tests for ProjectDetector and ProjectScanner."""

from pathlib import Path

import pytest

from ex_code.analyzer.detector import ProjectDetector
from ex_code.analyzer.project_scanner import ProjectScanner
from ex_code.core.models import (
    EntityDefinition,
    FieldDefinition,
    ProjectConfig,
    create_pk_field,
)
from ex_code.core.types import ArchitectureType, FrameworkType
from ex_code.generators.fastapi.generator import FastAPIGenerator


def test_detect_framework_fastapi(tmp_path: Path):
    fastapi_dir = tmp_path / "fastapi_app"
    fastapi_dir.mkdir()
    (fastapi_dir / "pyproject.toml").write_text(
        "[project]\ndependencies = ['fastapi']\n"
    )
    assert ProjectDetector.detect_framework(fastapi_dir) == FrameworkType.FASTAPI


def test_detect_framework_springboot(tmp_path: Path):
    sb_dir = tmp_path / "sb_app"
    sb_dir.mkdir()
    (sb_dir / "pom.xml").write_text(
        "<project><groupId>org.springframework.boot</groupId></project>\n"
    )
    assert ProjectDetector.detect_framework(sb_dir) == FrameworkType.SPRINGBOOT


def test_detect_framework_unknown(tmp_path: Path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    assert ProjectDetector.detect_framework(empty_dir) is None


def test_scan_project_with_metadata(tmp_path: Path):
    """Verify that a project generated with .excode.json is loaded accurately."""
    proj_dir = tmp_path / "meta_proj"
    pk = create_pk_field("Item", FrameworkType.FASTAPI)
    item = EntityDefinition(
        name="Item", fields=[pk, FieldDefinition(name="price", type="float")]
    )

    config = ProjectConfig(
        name="meta-proj",
        output_path=str(proj_dir),
        framework=FrameworkType.FASTAPI,
        architecture=ArchitectureType.LAYERED,
        entities=[item],
    )
    FastAPIGenerator().generate_project(config)

    scanned = ProjectScanner.scan_project(proj_dir)
    assert scanned.framework == FrameworkType.FASTAPI
    assert scanned.architecture == ArchitectureType.LAYERED
    assert len(scanned.entities) == 1
    assert scanned.entities[0].name == "Item"
    assert len(scanned.entities[0].fields) == 2


def test_scan_fastapi_without_metadata(tmp_path: Path):
    """Test AST scanning of a FastAPI project when .excode.json is removed."""
    proj_dir = tmp_path / "ast_proj"
    pk = create_pk_field("Task", FrameworkType.FASTAPI)
    task = EntityDefinition(
        name="Task", fields=[pk, FieldDefinition(name="title", type="str")]
    )

    config = ProjectConfig(
        name="ast-proj",
        output_path=str(proj_dir),
        framework=FrameworkType.FASTAPI,
        architecture=ArchitectureType.LAYERED,
        entities=[task],
    )
    FastAPIGenerator().generate_project(config)

    # Delete .excode.json to force AST static analysis
    (proj_dir / ".excode.json").unlink()

    scanned = ProjectScanner.scan_project(proj_dir)
    assert scanned.framework == FrameworkType.FASTAPI
    assert scanned.architecture == ArchitectureType.LAYERED
    assert len(scanned.entities) >= 1
    task_scanned = next(e for e in scanned.entities if e.name == "Task")
    assert any(f.name == "title" for f in task_scanned.fields)


def test_scan_invalid_path():
    with pytest.raises(FileNotFoundError):
        ProjectScanner.scan_project("/path/that/does/not/exist")


def test_find_project_root_and_scan_subfolder(tmp_path: Path):
    proj_dir = tmp_path / "subfolder_proj"
    pk = create_pk_field("Client", FrameworkType.FASTAPI)
    client = EntityDefinition(
        name="Client", fields=[pk, FieldDefinition(name="email", type="str")]
    )

    config = ProjectConfig(
        name="subfolder-proj",
        output_path=str(proj_dir),
        framework=FrameworkType.FASTAPI,
        architecture=ArchitectureType.LAYERED,
        entities=[client],
    )
    FastAPIGenerator().generate_project(config)

    subfolder = proj_dir / "app" / "models"
    model_file = subfolder / "client.py"
    assert model_file.is_file()

    # Find project root from subfolder and from file
    assert ProjectDetector.find_project_root(subfolder) == proj_dir
    assert ProjectDetector.find_project_root(model_file) == proj_dir

    # Scan project passing subfolder and file
    scanned_from_sub = ProjectScanner.scan_project(subfolder)
    assert scanned_from_sub.name == "subfolder-proj"
    assert len(scanned_from_sub.entities) == 1

    scanned_from_file = ProjectScanner.scan_project(model_file)
    assert scanned_from_file.name == "subfolder-proj"


def test_get_editable_files_fastapi(tmp_path: Path):
    proj_dir = tmp_path / "editable_proj"
    pk = create_pk_field("Product", FrameworkType.FASTAPI)
    product = EntityDefinition(
        name="Product", fields=[pk, FieldDefinition(name="sku", type="str")]
    )

    config = ProjectConfig(
        name="editable-proj",
        output_path=str(proj_dir),
        framework=FrameworkType.FASTAPI,
        architecture=ArchitectureType.LAYERED,
        entities=[product],
    )
    FastAPIGenerator().generate_project(config)

    files = ProjectScanner.get_editable_files(proj_dir, config)
    assert len(files) >= 2
    types = [f["type"] for f in files]
    assert "Model (Entidade)" in types
    assert "Schema / DTO" in types
    assert any("product.py" in f["filename"] for f in files)
