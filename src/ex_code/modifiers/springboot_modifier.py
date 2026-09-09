"""Surgical Java/Spring Boot code modifier."""

import re
from pathlib import Path

from ex_code.core.models import FieldDefinition, RelationshipDefinition
from ex_code.core.types import RelationshipType
from ex_code.modifiers.base import CodeModifier


class SpringBootCodeModifier(CodeModifier):
    """Modifies Spring Boot Java @Entity classes and Record DTOs surgically."""

    def _find_entity_and_dto_files(
        self, entity_name: str
    ) -> tuple[Path | None, list[Path]]:
        """Find the Java file for the entity and its corresponding DTO records."""
        java_root = self.project_path / "src" / "main" / "java"
        entity_file: Path | None = None
        dto_files: list[Path] = []

        if java_root.is_dir():
            for f in java_root.rglob("*.java"):
                if f.name == f"{entity_name}.java":
                    entity_file = f
                elif f.name.startswith(entity_name) and "DTO" in f.name:
                    dto_files.append(f)

        return entity_file, dto_files

    def add_field(
        self, entity_name: str, field: FieldDefinition
    ) -> list[tuple[Path, str, str]]:
        changes = []
        entity_file, dto_files = self._find_entity_and_dto_files(entity_name)

        # 1. Modify @Entity class
        if entity_file and entity_file.is_file():
            orig = entity_file.read_text(encoding="utf-8")
            null_clause = "" if field.is_nullable else ", nullable = false"
            uniq_clause = ", unique = true" if field.is_unique else ""
            field_snippet = (
                f'\n    @Column(name = "{field.db_column_name}"{null_clause}{uniq_clause})\n'
                f"    private {field.type} {field.name};\n}}\n"
            )
            # Replace the last closing brace
            last_brace_idx = orig.rfind("}")
            if last_brace_idx != -1:
                modified = orig[:last_brace_idx].rstrip() + field_snippet
                changes.append((entity_file, orig, modified))

        # 2. Modify Record DTOs
        for d_file in dto_files:
            orig_dto = d_file.read_text(encoding="utf-8")
            # Insert into record parameters: record Name(..., Type name) {}
            match = re.search(
                r"public\s+record\s+\w+\((.*?)\)\s*\{", orig_dto, re.DOTALL
            )
            if match:
                inner_params = match.group(1).strip()
                sep = ",\n    " if inner_params else ""
                new_param = f"{inner_params}{sep}{field.type} {field.name}"
                modified_dto = (
                    orig_dto[: match.start(1)]
                    + "\n    "
                    + new_param
                    + "\n"
                    + orig_dto[match.end(1) :]
                )
                changes.append((d_file, orig_dto, modified_dto))

        ent = self.config.get_entity(entity_name)
        if ent:
            ent.add_field(field)

        return changes

    def remove_field(
        self, entity_name: str, field_name: str
    ) -> list[tuple[Path, str, str]]:
        changes = []
        entity_file, dto_files = self._find_entity_and_dto_files(entity_name)

        # 1. Remove from @Entity class
        if entity_file and entity_file.is_file():
            orig = entity_file.read_text(encoding="utf-8")
            # Pattern matching field and preceding @Column
            pattern = (
                rf"\s*(?:@Column\([^)]*\)\s+)?private\s+[\w<>\[\]]+\s+{field_name};"
            )
            modified = re.sub(pattern, "", orig)
            if modified != orig:
                changes.append((entity_file, orig, modified))

        # 2. Remove from Record DTOs
        for d_file in dto_files:
            orig_dto = d_file.read_text(encoding="utf-8")
            pattern = rf"\s*[\w<>\[\]]+\s+{field_name}\s*(?:,|$)"
            modified_dto = re.sub(pattern, "", orig_dto)
            # Clean trailing commas if needed
            modified_dto = re.sub(r",\s*\)", ")", modified_dto)
            if modified_dto != orig_dto:
                changes.append((d_file, orig_dto, modified_dto))

        ent = self.config.get_entity(entity_name)
        if ent:
            ent.remove_field(field_name)

        return changes

    def update_field(
        self, entity_name: str, old_field_name: str, new_field: FieldDefinition
    ) -> list[tuple[Path, str, str]]:
        changes_remove = self.remove_field(entity_name, old_field_name)
        for path, _, mod_content in changes_remove:
            path.write_text(mod_content, encoding="utf-8")
        return self.add_field(entity_name, new_field)

    def add_relationship(
        self, relationship: RelationshipDefinition
    ) -> list[tuple[Path, str, str]]:
        changes = []
        entity_file, _ = self._find_entity_and_dto_files(relationship.source_entity)

        if entity_file and entity_file.is_file():
            orig = entity_file.read_text(encoding="utf-8")
            source_key = relationship.source_entity.lower()
            if relationship.relationship_type == RelationshipType.MANY_TO_ONE:
                rel_snippet = (
                    f"\n    @ManyToOne(fetch = FetchType.LAZY)\n"
                    f'    @JoinColumn(name = "{relationship.join_column}", nullable = false)\n'
                    f"    private {relationship.target_entity} {relationship.name};\n}}\n"
                )
            elif relationship.relationship_type == RelationshipType.ONE_TO_MANY:
                rel_snippet = (
                    f'\n    @OneToMany(mappedBy = "{source_key}", cascade = CascadeType.ALL, orphanRemoval = true)\n'
                    f"    @Builder.Default\n"
                    f"    private List<{relationship.target_entity}> {relationship.name} = new ArrayList<>();\n}}\n"
                )
            elif relationship.relationship_type == RelationshipType.ONE_TO_ONE:
                rel_snippet = (
                    f"\n    @OneToOne(fetch = FetchType.LAZY)\n"
                    f'    @JoinColumn(name = "{relationship.join_column}")\n'
                    f"    private {relationship.target_entity} {relationship.name};\n}}\n"
                )
            else:
                rel_snippet = (
                    f"\n    @ManyToMany\n"
                    f"    @Builder.Default\n"
                    f"    private List<{relationship.target_entity}> {relationship.name} = new ArrayList<>();\n}}\n"
                )

            last_brace_idx = orig.rfind("}")
            if last_brace_idx != -1:
                modified = orig[:last_brace_idx].rstrip() + rel_snippet
                changes.append((entity_file, orig, modified))

        ent = self.config.get_entity(relationship.source_entity)
        if ent:
            ent.relationships.append(relationship)

        return changes

    def remove_relationship(
        self, source_entity: str, relationship_name: str
    ) -> list[tuple[Path, str, str]]:
        changes = []
        entity_file, _ = self._find_entity_and_dto_files(source_entity)

        if entity_file and entity_file.is_file():
            orig = entity_file.read_text(encoding="utf-8")
            pattern = rf"\s*(?:@(?:ManyToOne|OneToMany|OneToOne|ManyToMany)\([^)]*\)\s+)?(?:@JoinColumn\([^)]*\)\s+)?(?:@Builder\.Default\s+)?private\s+[\w<>\[\]]+\s+{relationship_name}(?:\s*=[^;]+)?;"
            modified = re.sub(pattern, "", orig)
            if modified != orig:
                changes.append((entity_file, orig, modified))

        ent = self.config.get_entity(source_entity)
        if ent:
            ent.relationships = [
                r for r in ent.relationships if r.name != relationship_name
            ]

        return changes
