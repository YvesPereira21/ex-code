"""Unit and integration tests for SpringBootGenerator."""

from pathlib import Path

import pytest

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
)
from ex_code.generators.springboot.generator import SpringBootGenerator


@pytest.fixture
def sample_springboot_config(tmp_path: Path) -> ProjectConfig:
    project_dir = tmp_path / "springboot_demo"

    # User Entity
    user_pk = create_pk_field("User", FrameworkType.SPRINGBOOT)
    user_name = FieldDefinition(name="name", type="String")
    user_email = FieldDefinition(name="email", type="String", is_unique=True)
    user_rel = RelationshipDefinition(
        name="orders",
        relationship_type=RelationshipType.ONE_TO_MANY,
        source_entity="User",
        target_entity="Order",
    )
    user_entity = EntityDefinition(
        name="User",
        fields=[user_pk, user_name, user_email],
        relationships=[user_rel],
    )

    # Order Entity
    order_pk = create_pk_field("Order", FrameworkType.SPRINGBOOT)
    order_total = FieldDefinition(name="total", type="Double")
    order_rel = RelationshipDefinition(
        name="user",
        relationship_type=RelationshipType.MANY_TO_ONE,
        source_entity="Order",
        target_entity="User",
    )
    order_entity = EntityDefinition(
        name="Order",
        fields=[order_pk, order_total],
        relationships=[order_rel],
    )

    return ProjectConfig(
        name="springboot-demo",
        output_path=str(project_dir),
        description="Demo Spring Boot project with layered architecture",
        framework=FrameworkType.SPRINGBOOT,
        architecture=ArchitectureType.LAYERED,
        database=DatabaseType.POSTGRESQL,
        dependencies=["security"],
        entities=[user_entity, order_entity],
    )


def test_generate_springboot_layered(sample_springboot_config: ProjectConfig):
    generator = SpringBootGenerator()
    out_dir = generator.generate_project(sample_springboot_config)

    assert out_dir.is_dir()
    assert (out_dir / "pom.xml").is_file()
    assert (out_dir / "README.md").is_file()

    pom_content = (out_dir / "pom.xml").read_text()
    assert "org.mapstruct" in pom_content
    assert "lombok" in pom_content

    app_props = (
        out_dir / "src" / "main" / "resources" / "application.properties"
    ).read_text()
    assert "spring.datasource.url=jdbc:postgresql" in app_props

    java_root = out_dir / "src" / "main" / "java"
    # Find model directory
    model_dirs = list(java_root.rglob("model"))
    assert len(model_dirs) == 1
    model_dir = model_dirs[0]

    # Check Entity classes
    user_java = (model_dir / "User.java").read_text()
    assert "@Entity" in user_java
    assert '@Table(name = "users")' in user_java
    assert "@Id" in user_java
    assert "private UUID userId;" in user_java
    assert "@OneToMany" in user_java
    assert "private List<Order> orders" in user_java

    order_java = (model_dir / "Order.java").read_text()
    assert "@Entity" in order_java
    assert '@Table(name = "orders")' in order_java
    assert "private UUID orderId;" in order_java
    assert "@ManyToOne" in order_java
    assert "private User user;" in order_java

    # Check DTOs (Records)
    dto_dirs = list(java_root.rglob("dto"))
    assert len(dto_dirs) == 1
    dto_dir = dto_dirs[0]
    user_req_dto = (dto_dir / "UserRequestDTO.java").read_text()
    assert "public record UserRequestDTO(" in user_req_dto
    assert "String name" in user_req_dto

    user_res_dto = (dto_dir / "UserResponseDTO.java").read_text()
    assert "public record UserResponseDTO(" in user_res_dto
    assert "UUID userId" in user_res_dto

    # Check Repositories
    repo_dirs = list(java_root.rglob("repository"))
    assert len(repo_dirs) == 1
    repo_dir = repo_dirs[0]
    user_repo = (repo_dir / "UserRepository.java").read_text()
    assert (
        "public interface UserRepository extends JpaRepository<User, UUID>" in user_repo
    )

    # Check Mappers
    mapper_dirs = list(java_root.rglob("mapper"))
    assert len(mapper_dirs) == 1
    mapper_dir = mapper_dirs[0]
    user_mapper = (mapper_dir / "UserMapper.java").read_text()
    assert "@Mapper" in user_mapper
    assert "User toEntity(UserRequestDTO dto);" in user_mapper

    # Check Services & Controllers
    service_dirs = list(java_root.rglob("service"))
    assert len(service_dirs) == 1
    user_service = (service_dirs[0] / "UserService.java").read_text()
    assert "@Service" in user_service
    assert "public class UserService {" in user_service

    controller_dirs = list(java_root.rglob("controller"))
    assert len(controller_dirs) == 1
    user_controller = (controller_dirs[0] / "UserController.java").read_text()
    assert "@RestController" in user_controller
    assert "public class UserController {" in user_controller

    # Check Metadata
    assert MetadataManager.has_metadata(out_dir) is True
    loaded_config = MetadataManager.load_metadata(out_dir)
    assert loaded_config is not None
    assert loaded_config.framework == FrameworkType.SPRINGBOOT


def test_generate_springboot_domain(tmp_path: Path):
    project_dir = tmp_path / "springboot_domain_demo"

    item_pk = create_pk_field("Item", FrameworkType.SPRINGBOOT)
    item_title = FieldDefinition(name="title", type="String")
    item_entity = EntityDefinition(name="Item", fields=[item_pk, item_title])

    config = ProjectConfig(
        name="domain-app",
        output_path=str(project_dir),
        framework=FrameworkType.SPRINGBOOT,
        architecture=ArchitectureType.DOMAIN,
        database=DatabaseType.MYSQL,
        entities=[item_entity],
    )

    generator = SpringBootGenerator()
    out_dir = generator.generate_project(config)

    java_root = out_dir / "src" / "main" / "java"
    item_feature = list(java_root.rglob("domain/item"))
    assert len(item_feature) == 1
    feature_dir = item_feature[0]

    assert (feature_dir / "Item.java").is_file()
    assert (feature_dir / "ItemRequestDTO.java").is_file()
    assert (feature_dir / "ItemResponseDTO.java").is_file()
    assert (feature_dir / "ItemRepository.java").is_file()
    assert (feature_dir / "ItemMapper.java").is_file()
    assert (feature_dir / "ItemService.java").is_file()
    assert (feature_dir / "ItemController.java").is_file()

    item_java = (feature_dir / "Item.java").read_text()
    assert "package " in item_java
    assert ".domain.item;" in item_java
    assert "public class Item {" in item_java
    assert "private UUID itemId;" in item_java
