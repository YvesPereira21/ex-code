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


class RenameFieldTransformer(cst.CSTTransformer):
    """Renames an attribute in target ClassDefs (or all ClassDefs if target_classes is None)."""

    def __init__(
        self,
        old_field_name: str,
        new_field_name: str,
        target_classes: list[str] | None = None,
        new_type: str | None = None,
        is_nullable: bool | None = None,
    ) -> None:
        self.old_field_name = old_field_name
        self.new_field_name = new_field_name
        self.target_classes = target_classes
        self.new_type = new_type
        self.is_nullable = is_nullable

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        if self.target_classes and original_node.name.value not in self.target_classes:
            return updated_node

        new_body = []
        for stmt in updated_node.body.body:
            if isinstance(stmt, cst.SimpleStatementLine):
                new_small_stmts = []
                for item in stmt.body:
                    if (
                        isinstance(item, cst.AnnAssign)
                        and isinstance(item.target, cst.Name)
                        and item.target.value == self.old_field_name
                    ):
                        updated_ann = item.annotation
                        if self.new_type:
                            inner = item.annotation.annotation
                            is_mapped = (
                                isinstance(inner, cst.Subscript)
                                and isinstance(inner.value, cst.Name)
                                and inner.value.value == "Mapped"
                            )
                            inner_code = cst.Module([]).code_for_node(inner)
                            had_none = (
                                "| None" in inner_code or "Optional[" in inner_code
                            )
                            should_be_nullable = self.is_nullable or had_none

                            if is_mapped:
                                mod_type = (
                                    f"{self.new_type} | None"
                                    if self.is_nullable
                                    else self.new_type
                                )
                                updated_ann = item.annotation.with_changes(
                                    annotation=cst.parse_expression(
                                        f"Mapped[{mod_type}]"
                                    )
                                )
                            else:
                                s_type = (
                                    f"{self.new_type} | None"
                                    if should_be_nullable
                                    else self.new_type
                                )
                                updated_ann = item.annotation.with_changes(
                                    annotation=cst.parse_expression(s_type)
                                )

                        new_item = item.with_changes(
                            target=cst.Name(value=self.new_field_name),
                            annotation=updated_ann,
                        )
                        new_small_stmts.append(new_item)
                    else:
                        new_small_stmts.append(item)
                new_body.append(stmt.with_changes(body=new_small_stmts))
            else:
                new_body.append(stmt)

        return updated_node.with_changes(
            body=updated_node.body.with_changes(body=new_body)
        )


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
        changes = []
        model_path, schema_path = self._get_model_and_schema_paths(entity_name)

        # 1. Update in Model
        if model_path.is_file():
            orig_m = model_path.read_text(encoding="utf-8")
            mod_tree_m = cst.parse_module(orig_m).visit(
                RenameFieldTransformer(
                    old_field_name=old_field_name,
                    new_field_name=new_field.name,
                    target_classes=[entity_name],
                    new_type=new_field.type,
                    is_nullable=new_field.is_nullable,
                )
            )
            if mod_tree_m.code != orig_m:
                changes.append((model_path, orig_m, mod_tree_m.code))

        # 2. Update in Schema (Base, Update, and any custom schemas in this file)
        if schema_path.is_file():
            orig_s = schema_path.read_text(encoding="utf-8")
            mod_tree_s = cst.parse_module(orig_s).visit(
                RenameFieldTransformer(
                    old_field_name=old_field_name,
                    new_field_name=new_field.name,
                    target_classes=None,
                    new_type=new_field.type,
                    is_nullable=new_field.is_nullable,
                )
            )
            if mod_tree_s.code != orig_s:
                changes.append((schema_path, orig_s, mod_tree_s.code))

        # 3. Synchronize in config models
        self.config.update_entity_field(entity_name, old_field_name, new_field)

        return changes

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
