"""Project scanner for inspecting entities, fields, relationships, and DTOs."""

import ast
import re
from pathlib import Path

from ex_code.analyzer.detector import ProjectDetector
from ex_code.core.metadata import MetadataManager
from ex_code.core.models import (
    EntityDefinition,
    FieldDefinition,
    ProjectConfig,
    RelationshipDefinition,
)
from ex_code.core.types import (
    ArchitectureType,
    DatabaseType,
    FrameworkType,
    RelationshipType,
)


class ProjectScanner:
    """Scans and extracts structural information from existing backend projects."""

    @classmethod
    def scan_project(cls, project_path: Path | str) -> ProjectConfig:
        """Inspect and return the ProjectConfig representing the project."""
        path = Path(project_path).resolve()
        if not path.is_dir():
            raise FileNotFoundError(f"O diretório '{path}' não existe.")

        framework = ProjectDetector.detect_framework(path)
        if not framework:
            raise ValueError(
                f"Não foi possível identificar o framework (FastAPI ou Spring Boot) no diretório '{path}'."
            )

        architecture = ProjectDetector.detect_architecture(path, framework)

        # 1. Primary: load from .excode.json if present
        if MetadataManager.has_metadata(path):
            config = MetadataManager.load_metadata(path)
            if config:
                config.output_path = str(path)
                return config

        # 2. Fallback: static analysis
        entities: list[EntityDefinition] = []
        if framework == FrameworkType.FASTAPI:
            entities = cls._scan_fastapi_entities(path, architecture)
        elif framework == FrameworkType.SPRINGBOOT:
            entities = cls._scan_springboot_entities(path, architecture)

        return ProjectConfig(
            name=path.name,
            output_path=str(path),
            framework=framework,
            architecture=architecture,
            database=DatabaseType.POSTGRESQL,
            entities=entities,
        )

    @classmethod
    def _scan_fastapi_entities(
        cls, root: Path, architecture: ArchitectureType
    ) -> list[EntityDefinition]:
        """Scan Python AST for SQLAlchemy models and Pydantic schemas in FastAPI."""
        entities: list[EntityDefinition] = []

        if architecture == ArchitectureType.LAYERED:
            model_files = list((root / "app" / "models").glob("*.py"))
        else:
            model_files = list((root / "app" / "modules").glob("*/models.py"))

        for m_file in model_files:
            if m_file.name == "__init__.py":
                continue
            try:
                tree = ast.parse(m_file.read_text(encoding="utf-8"))
            except (SyntaxError, OSError):
                # Ignora arquivos que nao puderem ser parseados
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Check if inherits from Base or has Mapped fields
                    fields: list[FieldDefinition] = []
                    relationships: list[RelationshipDefinition] = []

                    for item in node.body:
                        if isinstance(item, ast.AnnAssign) and isinstance(
                            item.target, ast.Name
                        ):
                            field_name = item.target.id
                            if field_name.startswith("_"):
                                continue

                            type_str = ast.unparse(item.annotation)
                            value_str = ast.unparse(item.value) if item.value else ""

                            if "relationship(" in value_str:
                                # Relationship definition
                                rel_type = (
                                    RelationshipType.ONE_TO_MANY
                                    if "list[" in type_str.lower()
                                    else RelationshipType.MANY_TO_ONE
                                )
                                target_match = re.search(r'["\'](\w+)["\']', type_str)
                                target_entity = (
                                    target_match.group(1) if target_match else "Unknown"
                                )
                                relationships.append(
                                    RelationshipDefinition(
                                        name=field_name,
                                        relationship_type=rel_type,
                                        source_entity=node.name,
                                        target_entity=target_entity,
                                    )
                                )
                            else:
                                is_pk = (
                                    "primary_key=True" in value_str
                                    or field_name.endswith("_id")
                                )
                                is_null = (
                                    "None" in type_str or "nullable=True" in value_str
                                )
                                is_uniq = "unique=True" in value_str

                                # Clean type
                                clean_type = (
                                    type_str.replace("Mapped[", "")
                                    .replace("]", "")
                                    .replace(" | None", "")
                                    .strip()
                                )
                                fields.append(
                                    FieldDefinition(
                                        name=field_name,
                                        type=clean_type,
                                        is_pk=is_pk,
                                        is_nullable=is_null,
                                        is_unique=is_uniq,
                                    )
                                )

                    if fields or relationships:
                        entities.append(
                            EntityDefinition(
                                name=node.name,
                                fields=fields,
                                relationships=relationships,
                            )
                        )

        return entities

    @classmethod
    def _scan_springboot_entities(
        cls, root: Path, architecture: ArchitectureType
    ) -> list[EntityDefinition]:
        """Scan Java source files for @Entity classes and fields in Spring Boot."""
        entities: list[EntityDefinition] = []
        java_root = root / "src" / "main" / "java"
        if not java_root.is_dir():
            return entities

        for j_file in java_root.rglob("*.java"):
            content = j_file.read_text(encoding="utf-8", errors="ignore")
            if "@Entity" not in content:
                continue

            # Class name
            class_match = re.search(r"public\s+class\s+(\w+)", content)
            if not class_match:
                continue
            entity_name = class_match.group(1)

            fields: list[FieldDefinition] = []
            relationships: list[RelationshipDefinition] = []

            # Match fields: private Type fieldName;
            field_matches = re.finditer(
                r"(?:@Id\s+)?(?:@Column(?:\([^)]*\))?\s+)?private\s+([\w<>\[\]]+)\s+(\w+);",
                content,
            )
            for m in field_matches:
                f_type, f_name = m.group(1), m.group(2)
                block = content[max(0, m.start() - 100) : m.end()]
                is_pk = "@Id" in block or f_name.endswith("Id")
                is_null = "nullable = false" not in block
                is_uniq = "unique = true" in block

                if "@ManyToOne" in block:
                    relationships.append(
                        RelationshipDefinition(
                            name=f_name,
                            relationship_type=RelationshipType.MANY_TO_ONE,
                            source_entity=entity_name,
                            target_entity=f_type,
                        )
                    )
                elif "@OneToMany" in block:
                    target_match = re.search(r"List<(\w+)>", f_type)
                    target = target_match.group(1) if target_match else "Unknown"
                    relationships.append(
                        RelationshipDefinition(
                            name=f_name,
                            relationship_type=RelationshipType.ONE_TO_MANY,
                            source_entity=entity_name,
                            target_entity=target,
                        )
                    )
                else:
                    fields.append(
                        FieldDefinition(
                            name=f_name,
                            type=f_type,
                            is_pk=is_pk,
                            is_nullable=is_null,
                            is_unique=is_uniq,
                        )
                    )

            entities.append(
                EntityDefinition(
                    name=entity_name,
                    fields=fields,
                    relationships=relationships,
                )
            )

        return entities
