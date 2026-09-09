"""Base classes and diff generation utilities for surgical code modification."""

import difflib
from abc import ABC, abstractmethod
from pathlib import Path

from ex_code.core.metadata import MetadataManager
from ex_code.core.models import FieldDefinition, ProjectConfig, RelationshipDefinition


def generate_diff(original: str, modified: str, filename: str = "file") -> str:
    """Generate a unified diff between original and modified file contents."""
    orig_lines = original.splitlines(keepends=True)
    mod_lines = modified.splitlines(keepends=True)
    diff = difflib.unified_diff(
        orig_lines,
        mod_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
    )
    return "".join(diff)


class CodeModifier(ABC):
    """Abstract base class for framework-specific surgical code modifiers."""

    def __init__(self, project_path: Path | str, config: ProjectConfig) -> None:
        self.project_path = Path(project_path).resolve()
        self.config = config

    @abstractmethod
    def add_field(
        self, entity_name: str, field: FieldDefinition
    ) -> list[tuple[Path, str, str]]:
        """Plan adding a field to an entity (and associated schemas). Returns (path, orig, mod)."""
        raise NotImplementedError

    @abstractmethod
    def remove_field(
        self, entity_name: str, field_name: str
    ) -> list[tuple[Path, str, str]]:
        """Plan removing a field from an entity. Returns (path, orig, mod)."""
        raise NotImplementedError

    @abstractmethod
    def update_field(
        self, entity_name: str, old_field_name: str, new_field: FieldDefinition
    ) -> list[tuple[Path, str, str]]:
        """Plan updating an existing field. Returns (path, orig, mod)."""
        raise NotImplementedError

    @abstractmethod
    def add_relationship(
        self, relationship: RelationshipDefinition
    ) -> list[tuple[Path, str, str]]:
        """Plan adding a relationship to an entity. Returns (path, orig, mod)."""
        raise NotImplementedError

    @abstractmethod
    def remove_relationship(
        self, source_entity: str, relationship_name: str
    ) -> list[tuple[Path, str, str]]:
        """Plan removing a relationship. Returns (path, orig, mod)."""
        raise NotImplementedError

    def apply_changes(
        self, changes: list[tuple[Path, str, str]], make_backup: bool = True
    ) -> Path | None:
        """
        Create preventive backup in .excode/backups/ and apply planned changes to disk.
        Also updates .excode.json metadata.
        """
        if not changes:
            return None

        backup_path = None
        if make_backup:
            files_to_backup = [path for path, _, _ in changes]
            backup_path = MetadataManager.create_backup(
                self.project_path, files_to_backup=files_to_backup
            )

        for path, _, modified_content in changes:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(modified_content, encoding="utf-8")

        # Synchronize .excode.json
        MetadataManager.save_metadata(self.project_path, self.config)
        return backup_path
