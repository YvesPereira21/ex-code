"""Surgical Python/FastAPI code modifier using LibCST."""

from pathlib import Path

import libcst as cst

from ex_code.core.models import FieldDefinition, RelationshipDefinition
from ex_code.core.types import ArchitectureType, RelationshipType
from ex_code.modifiers.base import CodeModifier


class AddStatementsTransformer(cst.CSTTransformer):
    """Inserts statements into a target ClassDef body."""

    def __init__(self, target_class: str, stmts: list[cst.BaseStatement]) -> None:
        self.target_class = target_class
        self.stmts = stmts

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        if original_node.name.value == self.target_class:
            new_body = list(updated_node.body.body) + self.stmts
            return updated_node.with_changes(
                body=updated_node.body.with_changes(body=new_body)
            )
        return updated_node


class RemoveFieldTransformer(cst.CSTTransformer):
    """Removes an attribute assignment from a target ClassDef body."""

    def __init__(self, target_class: str, field_name: str) -> None:
        self.target_class = target_class
        self.field_name = field_name

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        if original_node.name.value == self.target_class:
            new_body = []
            for stmt in updated_node.body.body:
                if isinstance(stmt, cst.SimpleStatementLine):
                    matches = any(
                        isinstance(item, cst.AnnAssign)
                        and isinstance(item.target, cst.Name)
                        and item.target.value == self.field_name
                        for item in stmt.body
                    )
                    if not matches:
                        new_body.append(stmt)
                else:
                    new_body.append(stmt)
            return updated_node.with_changes(
                body=updated_node.body.with_changes(body=new_body)
            )
        return updated_node


class FastAPICodeModifier(CodeModifier):
    """Modifies FastAPI SQLAlchemy models and Pydantic schemas surgically."""

    def _get_model_and_schema_paths(self, entity_name: str) -> tuple[Path, Path]:
        """Resolve file paths for the entity model and schema based on architecture."""
        ent_key = entity_name.lower()
        if self.config.architecture == ArchitectureType.LAYERED:
            model_path = self.project_path / "app" / "models" / f"{ent_key}.py"
            schema_path = self.project_path / "app" / "schemas" / f"{ent_key}.py"
        else:
            module_dir = self.project_path / "app" / "modules" / ent_key
            model_path = module_dir / "models.py"
            schema_path = module_dir / "schemas.py"
        return model_path, schema_path

    def add_field(
        self, entity_name: str, field: FieldDefinition
    ) -> list[tuple[Path, str, str]]:
        changes = []
        model_path, schema_path = self._get_model_and_schema_paths(entity_name)

        # 1. Modify Model
        if model_path.is_file():
            orig = model_path.read_text(encoding="utf-8")
            mod_type = f"{field.type} | None" if field.is_nullable else field.type
            nullable_flag = "nullable=True" if field.is_nullable else "nullable=False"
            unique_flag = ", unique=True" if field.is_unique else ""
            code_line = f"{field.name}: Mapped[{mod_type}] = mapped_column({nullable_flag}{unique_flag})\n"

            stmts = list(cst.parse_module(code_line).body)
            mod_tree = cst.parse_module(orig).visit(
                AddStatementsTransformer(entity_name, stmts)
            )
            changes.append((model_path, orig, mod_tree.code))

        # 2. Modify Schema (Base schema)
        if schema_path.is_file():
            orig_s = schema_path.read_text(encoding="utf-8")
            schema_type = (
                f"{field.type} | None = None" if field.is_nullable else field.type
            )
            schema_line = f"{field.name}: {schema_type}\n"
            stmts_s = list(cst.parse_module(schema_line).body)
            mod_tree_s = cst.parse_module(orig_s).visit(
                AddStatementsTransformer(f"{entity_name}Base", stmts_s)
            )
            changes.append((schema_path, orig_s, mod_tree_s.code))

        # Update config model
        ent = self.config.get_entity(entity_name)
        if ent:
            ent.add_field(field)

        return changes

    def remove_field(
        self, entity_name: str, field_name: str
    ) -> list[tuple[Path, str, str]]:
        changes = []
        model_path, schema_path = self._get_model_and_schema_paths(entity_name)

        # 1. Remove from Model
        if model_path.is_file():
            orig = model_path.read_text(encoding="utf-8")
            mod_tree = cst.parse_module(orig).visit(
                RemoveFieldTransformer(entity_name, field_name)
            )
            changes.append((model_path, orig, mod_tree.code))

        # 2. Remove from Schema
        if schema_path.is_file():
            orig_s = schema_path.read_text(encoding="utf-8")
            mod_tree_s = cst.parse_module(orig_s).visit(
                RemoveFieldTransformer(f"{entity_name}Base", field_name)
            )
            changes.append((schema_path, orig_s, mod_tree_s.code))

        ent = self.config.get_entity(entity_name)
        if ent:
            ent.remove_field(field_name)

        return changes

    def update_field(
        self, entity_name: str, old_field_name: str, new_field: FieldDefinition
    ) -> list[tuple[Path, str, str]]:
        # Remove old and add new
        changes_remove = self.remove_field(entity_name, old_field_name)
        # Apply interim content for add
        for path, _, mod_content in changes_remove:
            path.write_text(mod_content, encoding="utf-8")

        changes_add = self.add_field(entity_name, new_field)
        # Return composite
        return changes_add

    def add_relationship(
        self, relationship: RelationshipDefinition
    ) -> list[tuple[Path, str, str]]:
        changes = []
        model_path, _ = self._get_model_and_schema_paths(relationship.source_entity)

        if model_path.is_file():
            orig = model_path.read_text(encoding="utf-8")
            target_key = relationship.target_entity.lower()
            source_key = relationship.source_entity.lower()

            if relationship.relationship_type == RelationshipType.MANY_TO_ONE:
                code_line = (
                    f'{relationship.join_column}: Mapped[uuid.UUID] = mapped_column(ForeignKey("{target_key}s.{target_key}_id"), nullable=False)\n'
                    f'{relationship.name}: Mapped["{relationship.target_entity}"] = relationship(back_populates="{source_key}s")\n'
                )
            elif relationship.relationship_type == RelationshipType.ONE_TO_MANY:
                code_line = f'{relationship.name}: Mapped[list["{relationship.target_entity}"]] = relationship(back_populates="{source_key}", cascade="all, delete-orphan")\n'
            elif relationship.relationship_type == RelationshipType.ONE_TO_ONE:
                code_line = f'{relationship.name}: Mapped["{relationship.target_entity}"] = relationship(back_populates="{source_key}", uselist=False)\n'
            else:
                code_line = f'{relationship.name}: Mapped[list["{relationship.target_entity}"]] = relationship(secondary="{source_key}_{target_key}", back_populates="{source_key}s")\n'

            stmts = list(cst.parse_module(code_line).body)
            mod_tree = cst.parse_module(orig).visit(
                AddStatementsTransformer(relationship.source_entity, stmts)
            )
            changes.append((model_path, orig, mod_tree.code))

        ent = self.config.get_entity(relationship.source_entity)
        if ent:
            ent.relationships.append(relationship)

        return changes

    def remove_relationship(
        self, source_entity: str, relationship_name: str
    ) -> list[tuple[Path, str, str]]:
        changes = []
        model_path, _ = self._get_model_and_schema_paths(source_entity)

        if model_path.is_file():
            orig = model_path.read_text(encoding="utf-8")
            mod_tree = cst.parse_module(orig).visit(
                RemoveFieldTransformer(source_entity, relationship_name)
            )
            changes.append((model_path, orig, mod_tree.code))

        ent = self.config.get_entity(source_entity)
        if ent:
            ent.relationships = [
                r for r in ent.relationships if r.name != relationship_name
            ]

        return changes
