"""Unit tests for ex_code.core (types, models, and metadata)."""

from pathlib import Path

from ex_code.core.metadata import MetadataManager
from ex_code.core.models import (
    EntityDefinition,
    FieldDefinition,
    ProjectConfig,
    RelationshipDefinition,
    create_pk_field,
)
from ex_code.core.types import (
    ArchitectureType,
    DatabaseType,
    FrameworkType,
    RelationshipType,
    generate_db_column_name,
    generate_pk_name,
    get_supported_types,
    resolve_framework_type,
    to_camel_case,
    to_pascal_case,
    to_snake_case,
)


class TestTypes:
    def test_case_conversions(self):
        assert to_snake_case("UserProfile") == "user_profile"
        assert to_snake_case("userProfile") == "user_profile"
        assert to_camel_case("user_profile") == "userProfile"
        assert to_camel_case("UserProfile") == "userProfile"
        assert to_pascal_case("user_profile") == "UserProfile"

    def test_get_supported_types(self):
        fastapi_types = get_supported_types(FrameworkType.FASTAPI)
        assert "str" in fastapi_types
        assert "int" in fastapi_types
        assert "UUID" in fastapi_types

        sb_types = get_supported_types(FrameworkType.SPRINGBOOT)
        assert "String" in sb_types
        assert "Integer" in sb_types
        assert "UUID" in sb_types

    def test_resolve_framework_type(self):
        assert resolve_framework_type("string", FrameworkType.FASTAPI) == "str"
        assert resolve_framework_type("string", FrameworkType.SPRINGBOOT) == "String"
        assert resolve_framework_type("uuid", FrameworkType.FASTAPI) == "UUID"
        assert resolve_framework_type("uuid", FrameworkType.SPRINGBOOT) == "UUID"
        assert resolve_framework_type("bigint", FrameworkType.SPRINGBOOT) == "Long"

    def test_pk_naming_conventions(self):
        # FastAPI: <entity_name>_id in snake_case
        assert generate_pk_name("User", FrameworkType.FASTAPI) == "user_id"
        assert (
            generate_pk_name("UserProfile", FrameworkType.FASTAPI) == "user_profile_id"
        )

        # Spring Boot: <entityName>Id in camelCase
        assert generate_pk_name("User", FrameworkType.SPRINGBOOT) == "userId"
        assert (
            generate_pk_name("UserProfile", FrameworkType.SPRINGBOOT) == "userProfileId"
        )

    def test_db_column_naming(self):
        assert generate_db_column_name("userId") == "user_id"
        assert generate_db_column_name("createdAt") == "created_at"


class TestModels:
    def test_create_pk_field(self):
        fastapi_pk = create_pk_field("User", FrameworkType.FASTAPI)
        assert fastapi_pk.name == "user_id"
        assert fastapi_pk.type == "UUID"
        assert fastapi_pk.is_pk is True
        assert fastapi_pk.is_nullable is False
        assert fastapi_pk.db_column_name == "user_id"

        sb_pk = create_pk_field("User", FrameworkType.SPRINGBOOT)
        assert sb_pk.name == "userId"
        assert sb_pk.type == "UUID"
        assert sb_pk.is_pk is True
        assert sb_pk.is_nullable is False
        assert sb_pk.db_column_name == "user_id"

    def test_field_definition_db_column_default(self):
        field = FieldDefinition(name="firstName", type="String")
        assert field.db_column_name == "first_name"

    def test_relationship_defaults(self):
        rel = RelationshipDefinition(
            name="orders",
            relationship_type=RelationshipType.ONE_TO_MANY,
            source_entity="User",
            target_entity="Order",
        )
        assert rel.is_bidirectional is True
        assert rel.cascade == "all"

        m2o = RelationshipDefinition(
            name="user",
            relationship_type=RelationshipType.MANY_TO_ONE,
            source_entity="Order",
            target_entity="User",
        )
        assert m2o.join_column == "user_id"

    def test_entity_definition_methods(self):
        entity = EntityDefinition(name="Product")
        assert entity.table_name == "products"

        pk = create_pk_field("Product", FrameworkType.FASTAPI)
        entity.add_field(pk)
        assert entity.get_pk_field() == pk

        field2 = FieldDefinition(name="price", type="float")
        entity.add_field(field2)
        assert len(entity.fields) == 2

        assert entity.remove_field("price") is True
        assert len(entity.fields) == 1
        assert entity.remove_field("non_existent") is False

    def test_project_config(self):
        config = ProjectConfig(
            name="my-api",
            output_path="/tmp/my-api",
            framework=FrameworkType.FASTAPI,
            architecture=ArchitectureType.LAYERED,
            database=DatabaseType.POSTGRESQL,
        )
        assert config.name == "my-api"
        assert config.framework == FrameworkType.FASTAPI

        ent = EntityDefinition(name="Customer")
        config.add_entity(ent)
        assert config.get_entity("customer") is not None
        assert config.get_entity("Customer").name == "Customer"
        assert config.get_entity("Unknown") is None


class TestMetadataManager:
    def test_save_and_load_metadata(self, tmp_path: Path):
        project_dir = tmp_path / "test_project"
        config = ProjectConfig(
            name="demo-proj",
            output_path=str(project_dir),
            framework=FrameworkType.SPRINGBOOT,
            architecture=ArchitectureType.DOMAIN,
            database=DatabaseType.MYSQL,
            dependencies=["validation", "security"],
        )
        pk = create_pk_field("Item", FrameworkType.SPRINGBOOT)
        item_entity = EntityDefinition(name="Item", fields=[pk])
        config.add_entity(item_entity)

        # Initially no metadata
        assert MetadataManager.has_metadata(project_dir) is False

        # Save metadata
        saved_path = MetadataManager.save_metadata(project_dir, config)
        assert saved_path.is_file()
        assert MetadataManager.has_metadata(project_dir) is True

        # Load metadata
        loaded_config = MetadataManager.load_metadata(project_dir)
        assert loaded_config is not None
        assert loaded_config.name == "demo-proj"
        assert loaded_config.framework == FrameworkType.SPRINGBOOT
        assert loaded_config.architecture == ArchitectureType.DOMAIN
        assert len(loaded_config.entities) == 1
        assert loaded_config.entities[0].name == "Item"
        assert loaded_config.entities[0].fields[0].name == "itemId"

    def test_create_backup(self, tmp_path: Path):
        project_dir = tmp_path / "backup_project"
        project_dir.mkdir()
        dummy_file = project_dir / "Main.java"
        dummy_file.write_text("class Main {}", encoding="utf-8")

        config = ProjectConfig(
            name="backup-proj",
            output_path=str(project_dir),
            framework=FrameworkType.SPRINGBOOT,
        )
        MetadataManager.save_metadata(project_dir, config)

        backup_path = MetadataManager.create_backup(project_dir)
        assert backup_path.is_dir()
        assert (backup_path / ".excode.json").is_file()
        assert (backup_path / "Main.java").is_file()
        assert (backup_path / "Main.java").read_text(
            encoding="utf-8"
        ) == "class Main {}"
