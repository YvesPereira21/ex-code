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
        raw_path = Path(project_path).resolve()
        if not raw_path.exists():
            raise FileNotFoundError(f"O diretório ou arquivo '{raw_path}' não existe.")

        path = ProjectDetector.find_project_root(raw_path)
        if not path.is_dir():
            raise FileNotFoundError(f"O diretório '{path}' não existe.")

        # 1. Primary: load from .excode.json if present
        if MetadataManager.has_metadata(path):
            config = MetadataManager.load_metadata(path)
            if config:
                config.output_path = str(path)
                cls._ensure_entity_paths(path, config)
                MetadataManager.save_metadata(path, config)
                return config

        framework = ProjectDetector.detect_framework(path)
        if not framework:
            raise ValueError(
                f"Não foi possível identificar o framework (FastAPI ou Spring Boot) no diretório '{path}'."
            )

        architecture = ProjectDetector.detect_architecture(path, framework)

        # 2. Fallback: static analysis
        entities: list[EntityDefinition] = []
        if framework == FrameworkType.FASTAPI:
            entities = cls._scan_fastapi_entities(path, architecture)
        elif framework == FrameworkType.SPRINGBOOT:
            entities = cls._scan_springboot_entities(path, architecture)

        config = ProjectConfig(
            name=path.name,
            output_path=str(path),
            framework=framework,
            architecture=architecture,
            database=DatabaseType.POSTGRESQL,
            entities=entities,
        )
        cls._ensure_entity_paths(path, config)
        MetadataManager.save_metadata(path, config)
        return config

    @classmethod
    def _ensure_entity_paths(cls, root: Path, config: ProjectConfig) -> None:
        """Ensure every entity in config has relative paths populated for model, schema, repo, controller."""
        if config.framework == FrameworkType.FASTAPI:
            if config.architecture == ArchitectureType.LAYERED:
                config.models_path = config.models_path or "app/models"
                config.schemas_path = config.schemas_path or "app/schemas"
                config.controllers_path = config.controllers_path or "app/api/routers"
                for entity in config.entities:
                    ek = entity.name.lower()
                    if (
                        not entity.model_path
                        and (root / "app" / "models" / f"{ek}.py").is_file()
                    ):
                        entity.model_path = f"app/models/{ek}.py"
                    if (
                        not entity.schema_path
                        and (root / "app" / "schemas" / f"{ek}.py").is_file()
                    ):
                        entity.schema_path = f"app/schemas/{ek}.py"
                    if (
                        not entity.controller_path
                        and (root / "app" / "api" / "routers" / f"{ek}.py").is_file()
                    ):
                        entity.controller_path = f"app/api/routers/{ek}.py"
            else:
                config.models_path = config.models_path or "app/modules"
                config.schemas_path = config.schemas_path or "app/modules"
                config.controllers_path = config.controllers_path or "app/modules"
                for entity in config.entities:
                    ek = entity.name.lower()
                    if (
                        not entity.model_path
                        and (root / "app" / "modules" / ek / "models.py").is_file()
                    ):
                        entity.model_path = f"app/modules/{ek}/models.py"
                    if (
                        not entity.schema_path
                        and (root / "app" / "modules" / ek / "schemas.py").is_file()
                    ):
                        entity.schema_path = f"app/modules/{ek}/schemas.py"
                    if (
                        not entity.controller_path
                        and (root / "app" / "modules" / ek / "router.py").is_file()
                    ):
                        entity.controller_path = f"app/modules/{ek}/router.py"
                    if (
                        not entity.repository_path
                        and (root / "app" / "modules" / ek / "repository.py").is_file()
                    ):
                        entity.repository_path = f"app/modules/{ek}/repository.py"
        elif config.framework == FrameworkType.SPRINGBOOT:
            java_root = root / "src" / "main" / "java"
            if java_root.is_dir():
                java_files = list(java_root.rglob("*.java"))
                for entity in config.entities:
                    en = entity.name
                    for jf in java_files:
                        rel = str(jf.relative_to(root))
                        if not entity.model_path and jf.name == f"{en}.java":
                            entity.model_path = rel
                        elif not entity.schema_path and (
                            jf.name == f"{en}DTO.java" or jf.name == f"{en}Record.java"
                        ):
                            entity.schema_path = rel
                        elif (
                            not entity.repository_path
                            and jf.name == f"{en}Repository.java"
                        ):
                            entity.repository_path = rel
                        elif (
                            not entity.controller_path
                            and jf.name == f"{en}Controller.java"
                        ):
                            entity.controller_path = rel

                # Ensure schemas_path for Spring Boot
                if not config.schemas_path:
                    for entity in config.entities:
                        if entity.schema_path:
                            config.schemas_path = str(Path(entity.schema_path).parent)
                            break
                    if not config.schemas_path:
                        for d in java_root.rglob("*"):
                            if d.is_dir() and d.name.lower() in (
                                "dto",
                                "dtos",
                                "records",
                                "record",
                            ):
                                config.schemas_path = str(d.relative_to(root))
                                break
                    if (
                        not config.schemas_path
                        and config.architecture == ArchitectureType.DOMAIN
                    ):
                        for d in java_root.rglob("*"):
                            if d.is_dir() and d.name.lower() == "domain":
                                config.schemas_path = str(d.relative_to(root))
                                break

                # Ensure models_path for Spring Boot
                if not config.models_path:
                    for entity in config.entities:
                        if entity.model_path:
                            config.models_path = str(Path(entity.model_path).parent)
                            break
                    if not config.models_path:
                        for d in java_root.rglob("*"):
                            if d.is_dir() and d.name.lower() in (
                                "model",
                                "models",
                                "entity",
                                "entities",
                            ):
                                config.models_path = str(d.relative_to(root))
                                break
                    if (
                        not config.models_path
                        and config.architecture == ArchitectureType.DOMAIN
                    ):
                        for d in java_root.rglob("*"):
                            if d.is_dir() and d.name.lower() == "domain":
                                config.models_path = str(d.relative_to(root))
                                break

                # Ensure repositories_path for Spring Boot
                if not config.repositories_path:
                    for entity in config.entities:
                        if entity.repository_path:
                            config.repositories_path = str(
                                Path(entity.repository_path).parent
                            )
                            break
                    if not config.repositories_path:
                        for d in java_root.rglob("*"):
                            if d.is_dir() and d.name.lower() in (
                                "repository",
                                "repositories",
                            ):
                                config.repositories_path = str(d.relative_to(root))
                                break

                # Ensure controllers_path for Spring Boot
                if not config.controllers_path:
                    for entity in config.entities:
                        if entity.controller_path:
                            config.controllers_path = str(
                                Path(entity.controller_path).parent
                            )
                            break
                    if not config.controllers_path:
                        for d in java_root.rglob("*"):
                            if d.is_dir() and d.name.lower() in (
                                "controller",
                                "controllers",
                                "rest",
                            ):
                                config.controllers_path = str(d.relative_to(root))
                                break

    @classmethod
    def get_editable_files(
        cls, project_path: Path | str, config: ProjectConfig | None = None
    ) -> list[dict[str, str]]:
        """List all editable model and schema/DTO files in the project."""
        raw_path = Path(project_path).resolve()
        root = ProjectDetector.find_project_root(raw_path)
        if config is None:
            config = cls.scan_project(root)

        files: list[dict[str, str]] = []
        seen_paths: set[str] = set()

        # 1. Primary: paths registered in entities (.excode.json)
        term_schema = "Schema" if config.framework == FrameworkType.FASTAPI else "DTO"
        for entity in config.entities:
            if entity.model_path:
                abs_p = root / entity.model_path
                if abs_p.is_file() and entity.model_path not in seen_paths:
                    seen_paths.add(entity.model_path)
                    files.append(
                        {
                            "type": "Model (Entidade)",
                            "entity": entity.name,
                            "filename": abs_p.name,
                            "rel_path": entity.model_path,
                            "abs_path": str(abs_p),
                        }
                    )
            if entity.schema_path:
                abs_p = root / entity.schema_path
                if abs_p.is_file() and entity.schema_path not in seen_paths:
                    seen_paths.add(entity.schema_path)
                    files.append(
                        {
                            "type": term_schema,
                            "entity": entity.name,
                            "filename": abs_p.name,
                            "rel_path": entity.schema_path,
                            "abs_path": str(abs_p),
                        }
                    )
            if entity.repository_path:
                abs_p = root / entity.repository_path
                if abs_p.is_file() and entity.repository_path not in seen_paths:
                    seen_paths.add(entity.repository_path)
                    files.append(
                        {
                            "type": "Repository",
                            "entity": entity.name,
                            "filename": abs_p.name,
                            "rel_path": entity.repository_path,
                            "abs_path": str(abs_p),
                        }
                    )
            if entity.controller_path:
                abs_p = root / entity.controller_path
                if abs_p.is_file() and entity.controller_path not in seen_paths:
                    seen_paths.add(entity.controller_path)
                    files.append(
                        {
                            "type": (
                                "Controller"
                                if config.framework == FrameworkType.SPRINGBOOT
                                else "Router"
                            ),
                            "entity": entity.name,
                            "filename": abs_p.name,
                            "rel_path": entity.controller_path,
                            "abs_path": str(abs_p),
                        }
                    )

        # 2. Fallback scan for unmapped files
        if config.framework == FrameworkType.FASTAPI:
            if config.architecture == ArchitectureType.LAYERED:
                models_dir = root / "app" / "models"
                schemas_dir = root / "app" / "schemas"
                if models_dir.is_dir():
                    for f in sorted(models_dir.glob("*.py")):
                        rel_path = str(f.relative_to(root))
                        if f.name == "__init__.py" or rel_path in seen_paths:
                            continue
                        seen_paths.add(rel_path)
                        ent_name = f.stem.capitalize()
                        matched_ent = next(
                            (
                                e.name
                                for e in config.entities
                                if e.name.lower() == f.stem.lower()
                            ),
                            ent_name,
                        )
                        files.append(
                            {
                                "type": "Model (Entidade)",
                                "entity": matched_ent,
                                "filename": f.name,
                                "rel_path": rel_path,
                                "abs_path": str(f),
                            }
                        )
                if schemas_dir.is_dir():
                    for f in sorted(schemas_dir.glob("*.py")):
                        rel_path = str(f.relative_to(root))
                        if f.name == "__init__.py" or rel_path in seen_paths:
                            continue
                        seen_paths.add(rel_path)
                        ent_name = f.stem.capitalize()
                        matched_ent = next(
                            (
                                e.name
                                for e in config.entities
                                if e.name.lower() == f.stem.lower()
                            ),
                            ent_name,
                        )
                        files.append(
                            {
                                "type": "Schema",
                                "entity": matched_ent,
                                "filename": f.name,
                                "rel_path": rel_path,
                                "abs_path": str(f),
                            }
                        )
            else:
                modules_dir = root / "app" / "modules"
                if modules_dir.is_dir():
                    for mod in sorted(modules_dir.iterdir()):
                        if mod.is_dir():
                            m_file = mod / "models.py"
                            s_file = mod / "schemas.py"
                            ent_name = mod.name.capitalize()
                            matched_ent = next(
                                (
                                    e.name
                                    for e in config.entities
                                    if e.name.lower() == mod.name.lower()
                                ),
                                ent_name,
                            )
                            if (
                                m_file.is_file()
                                and str(m_file.relative_to(root)) not in seen_paths
                            ):
                                seen_paths.add(str(m_file.relative_to(root)))
                                files.append(
                                    {
                                        "type": "Model (Entidade)",
                                        "entity": matched_ent,
                                        "filename": f"{mod.name}/models.py",
                                        "rel_path": str(m_file.relative_to(root)),
                                        "abs_path": str(m_file),
                                    }
                                )
                            if (
                                s_file.is_file()
                                and str(s_file.relative_to(root)) not in seen_paths
                            ):
                                seen_paths.add(str(s_file.relative_to(root)))
                                files.append(
                                    {
                                        "type": "Schema",
                                        "entity": matched_ent,
                                        "filename": f"{mod.name}/schemas.py",
                                        "rel_path": str(s_file.relative_to(root)),
                                        "abs_path": str(s_file),
                                    }
                                )

        elif config.framework == FrameworkType.SPRINGBOOT:
            java_root = root / "src" / "main" / "java"
            if java_root.is_dir():
                for f in sorted(java_root.rglob("*.java")):
                    rel_path = str(f.relative_to(root))
                    if rel_path in seen_paths:
                        continue
                    seen_paths.add(rel_path)
                    name = f.stem
                    if "DTO" in name or "Record" in name:
                        ent_name = name.replace("DTO", "").replace("Record", "")
                        files.append(
                            {
                                "type": "DTO",
                                "entity": ent_name,
                                "filename": f.name,
                                "rel_path": rel_path,
                                "abs_path": str(f),
                            }
                        )
                    elif any(e.name.lower() == name.lower() for e in config.entities):
                        matched_ent = next(
                            e.name
                            for e in config.entities
                            if e.name.lower() == name.lower()
                        )
                        files.append(
                            {
                                "type": "Model (Entidade)",
                                "entity": matched_ent,
                                "filename": f.name,
                                "rel_path": rel_path,
                                "abs_path": str(f),
                            }
                        )

        return files

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
