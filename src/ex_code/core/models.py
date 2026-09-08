"""Domain models for ex-code project configuration, entities, and schemas."""

from pydantic import BaseModel, Field, model_validator

from ex_code.core.types import (
    ArchitectureType,
    DatabaseType,
    FrameworkType,
    RelationshipType,
    generate_db_column_name,
    generate_pk_name,
    resolve_framework_type,
    to_snake_case,
)


class FieldDefinition(BaseModel):
    """Definition of a field within an Entity."""

    name: str
    type: str
    agnostic_type: str = "string"
    is_pk: bool = False
    is_nullable: bool = False
    is_unique: bool = False
    default_value: str | None = None
    db_column_name: str | None = None

    @model_validator(mode="after")
    def set_default_db_column(self) -> "FieldDefinition":
        if not self.db_column_name:
            self.db_column_name = generate_db_column_name(self.name)
        return self


class RelationshipDefinition(BaseModel):
    """Definition of a relationship between two Entities."""

    name: str
    relationship_type: RelationshipType
    source_entity: str
    target_entity: str
    join_column: str | None = None
    mapped_by: str | None = None
    is_bidirectional: bool = True
    cascade: str = "all"

    @model_validator(mode="after")
    def set_defaults(self) -> "RelationshipDefinition":
        if not self.join_column and self.relationship_type in (
            RelationshipType.MANY_TO_ONE,
            RelationshipType.ONE_TO_ONE,
        ):
            self.join_column = f"{to_snake_case(self.target_entity)}_id"
        return self


class SchemaFieldDefinition(BaseModel):
    """Definition of a field within a Schema/DTO."""

    name: str
    type: str
    is_nullable: bool = False
    default_value: str | None = None
    is_entity_ref: bool = False
    entity_ref_name: str | None = None


class SchemaDefinition(BaseModel):
    """Definition of a Schema / DTO."""

    name: str
    entity_ref: str | None = None
    fields: list[SchemaFieldDefinition] = Field(default_factory=list)
    description: str | None = None


class EntityDefinition(BaseModel):
    """Definition of an Entity."""

    name: str
    table_name: str | None = None
    fields: list[FieldDefinition] = Field(default_factory=list)
    relationships: list[RelationshipDefinition] = Field(default_factory=list)
    schemas: list[SchemaDefinition] = Field(default_factory=list)

    @model_validator(mode="after")
    def set_default_table_name(self) -> "EntityDefinition":
        if not self.table_name:
            self.table_name = f"{to_snake_case(self.name)}s"
        return self

    def get_pk_field(self) -> FieldDefinition | None:
        """Return the primary key field if present."""
        for field in self.fields:
            if field.is_pk:
                return field
        return None

    def add_field(self, field: FieldDefinition) -> None:
        """Add or update a field by name."""
        for idx, f in enumerate(self.fields):
            if f.name == field.name:
                self.fields[idx] = field
                return
        self.fields.append(field)

    def remove_field(self, field_name: str) -> bool:
        """Remove a field by name."""
        initial_len = len(self.fields)
        self.fields = [f for f in self.fields if f.name != field_name]
        return len(self.fields) < initial_len


class ProjectConfig(BaseModel):
    """Configuration root for a generated or inspected project."""

    name: str
    output_path: str
    description: str | None = None
    framework: FrameworkType
    architecture: ArchitectureType = ArchitectureType.LAYERED
    database: DatabaseType = DatabaseType.POSTGRESQL
    dependencies: list[str] = Field(default_factory=list)
    entities: list[EntityDefinition] = Field(default_factory=list)
    schemas: list[SchemaDefinition] = Field(default_factory=list)
    version: str = "0.1.0"

    def get_entity(self, name: str) -> EntityDefinition | None:
        """Find an entity by name."""
        for ent in self.entities:
            if ent.name.lower() == name.lower():
                return ent
        return None

    def add_entity(self, entity: EntityDefinition) -> None:
        """Add or replace an entity."""
        for idx, ent in enumerate(self.entities):
            if ent.name.lower() == entity.name.lower():
                self.entities[idx] = entity
                return
        self.entities.append(entity)


def create_pk_field(
    entity_name: str, framework: FrameworkType | str
) -> FieldDefinition:
    """Create a standardized UUID primary key field for an entity."""
    pk_name = generate_pk_name(entity_name, framework)
    native_type = resolve_framework_type("uuid", framework)
    return FieldDefinition(
        name=pk_name,
        type=native_type,
        agnostic_type="uuid",
        is_pk=True,
        is_nullable=False,
        is_unique=True,
        db_column_name=generate_db_column_name(pk_name),
    )
