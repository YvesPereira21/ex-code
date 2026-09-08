"""Metadata and backup management (.excode.json and .excode/backups)."""

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from ex_code.core.models import ProjectConfig

METADATA_FILENAME = ".excode.json"
BACKUPS_DIRNAME = ".excode/backups"


class MetadataManager:
    """Handles saving, loading .excode.json metadata and creating preventive backups."""

    @staticmethod
    def get_metadata_path(project_path: Path | str) -> Path:
        """Return the path to the .excode.json file for a project."""
        return Path(project_path) / METADATA_FILENAME

    @classmethod
    def has_metadata(cls, project_path: Path | str) -> bool:
        """Check if project contains .excode.json."""
        return cls.get_metadata_path(project_path).is_file()

    @classmethod
    def save_metadata(cls, project_path: Path | str, config: ProjectConfig) -> Path:
        """Save ProjectConfig to .excode.json in the project root."""
        root = Path(project_path)
        root.mkdir(parents=True, exist_ok=True)
        file_path = cls.get_metadata_path(root)

        data = config.model_dump(mode="json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return file_path

    @classmethod
    def load_metadata(cls, project_path: Path | str) -> ProjectConfig | None:
        """Load ProjectConfig from .excode.json if it exists."""
        file_path = cls.get_metadata_path(project_path)
        if not file_path.is_file():
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ProjectConfig.model_validate(data)

    @classmethod
    def create_backup(
        cls,
        project_path: Path | str,
        files_to_backup: list[Path | str] | None = None,
    ) -> Path:
        """
        Create a safety backup snapshot under .excode/backups/<timestamp>/.
        If files_to_backup is provided, only those files are copied.
        Otherwise, copies all relevant source files and .excode.json.
        """
        root = Path(project_path).resolve()
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        backup_dir = root / BACKUPS_DIRNAME / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)

        if files_to_backup:
            for file in files_to_backup:
                abs_path = Path(file).resolve()
                if not abs_path.is_file():
                    continue
                try:
                    rel_path = abs_path.relative_to(root)
                except ValueError:
                    rel_path = Path(abs_path.name)
                dest = backup_dir / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(abs_path, dest)
        else:
            # Backup .excode.json if present
            meta = cls.get_metadata_path(root)
            if meta.is_file():
                shutil.copy2(meta, backup_dir / METADATA_FILENAME)

            # Backup source trees excluding venv, git, target, etc.
            ignore_patterns = shutil.ignore_patterns(
                ".git", ".venv", "venv", "__pycache__", "target", ".excode", "*.pyc"
            )
            for item in root.iterdir():
                if item.name in (
                    ".git",
                    ".excode",
                    ".venv",
                    "venv",
                    "target",
                    "__pycache__",
                ):
                    continue
                dest = backup_dir / item.name
                if item.is_dir():
                    shutil.copytree(
                        item, dest, ignore=ignore_patterns, dirs_exist_ok=True
                    )
                elif item.is_file():
                    shutil.copy2(item, dest)

        return backup_dir
