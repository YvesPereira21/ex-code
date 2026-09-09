"""Unit and integration tests for FastAPIGenerator."""

import py_compile
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
from ex_code.generators.fastapi.generator import FastAPIGenerator


@pytest.fixture
def sample_fastapi_config(tmp_path: Path) -> ProjectConfig:
    project_dir = tmp_path / "fastapi_demo"

    # User Entity
    user_pk = create_pk_field("User", FrameworkType.FASTAPI)
    user_name = FieldDefinition(name="name", type="str")
    user_email = FieldDefinition(name="email", type="str", is_unique=True)
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
    order_pk = create_pk_field("Order", FrameworkType.FASTAPI)
    order_total = FieldDefinition(name="total", type="float")
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
        name="fastapi-demo",
        output_path=str(project_dir),
        description="Demo FastAPI project with layered architecture",
        framework=FrameworkType.FASTAPI,
        architecture=ArchitectureType.LAYERED,
        database=DatabaseType.POSTGRESQL,
        dependencies=["python-jose", "passlib"],
        entities=[user_entity, order_entity],
    )


def assert_all_python_files_compile(root_dir: Path) -> None:
    """Recursively verify all .py files compile without syntax errors."""
    for py_file in root_dir.rglob("*.py"):
        try:
            py_compile.compile(str(py_file), doraise=True)
        except py_compile.PyCompileError as e:
            pytest.fail(f"Syntax error in generated file {py_file}:\n{e}")


def test_generate_fastapi_layered(sample_fastapi_config: ProjectConfig):
    generator = FastAPIGenerator()
    out_dir = generator.generate_project(sample_fastapi_config)

    assert out_dir.is_dir()
    assert (out_dir / "pyproject.toml").is_file()
    assert (out_dir / "requirements.txt").is_file()
    assert (out_dir / "README.md").is_file()
    assert (out_dir / "alembic.ini").is_file()
    assert (out_dir / "alembic" / "env.py").is_file()

    # Core
    assert (out_dir / "app" / "core" / "database.py").is_file()
    assert (out_dir / "app" / "core" / "config.py").is_file()
    assert (out_dir / "app" / "main.py").is_file()

    # Layered directories
    assert (out_dir / "app" / "models" / "user.py").is_file()
    assert (out_dir / "app" / "models" / "order.py").is_file()
    assert (out_dir / "app" / "schemas" / "user.py").is_file()
    assert (out_dir / "app" / "schemas" / "order.py").is_file()
    assert (out_dir / "app" / "api" / "routers" / "user.py").is_file()
    assert (out_dir / "app" / "api" / "routers" / "order.py").is_file()

    # Content checks
    user_model_content = (out_dir / "app" / "models" / "user.py").read_text()
    assert "class User(Base):" in user_model_content
    assert "user_id: Mapped[uuid.UUID]" in user_model_content
    assert 'orders: Mapped[list["Order"]]' in user_model_content

    order_model_content = (out_dir / "app" / "models" / "order.py").read_text()
    assert "class Order(Base):" in order_model_content
    assert "order_id: Mapped[uuid.UUID]" in order_model_content
    assert (
        'user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id"), nullable=False)'
        in order_model_content
    )
    assert (
        'user: Mapped["User"] = relationship(back_populates="orders")'
        in order_model_content
    )

    # Dependencies check
    reqs = (out_dir / "requirements.txt").read_text()
    assert "fastapi" in reqs
    assert "asyncpg" in reqs
    assert "python-jose" in reqs
    assert "passlib" in reqs

    # Metadata check
    assert MetadataManager.has_metadata(out_dir) is True
    loaded_config = MetadataManager.load_metadata(out_dir)
    assert loaded_config is not None
    assert loaded_config.name == "fastapi-demo"
    assert len(loaded_config.entities) == 2

    # Verify all Python files are syntactically valid
    assert_all_python_files_compile(out_dir)


def test_generate_fastapi_domain(tmp_path: Path):
    project_dir = tmp_path / "fastapi_domain_demo"

    prod_pk = create_pk_field("Product", FrameworkType.FASTAPI)
    prod_name = FieldDefinition(name="title", type="str")
    prod_price = FieldDefinition(name="price", type="Decimal")
    prod_entity = EntityDefinition(
        name="Product",
        fields=[prod_pk, prod_name, prod_price],
    )

    config = ProjectConfig(
        name="domain-store",
        output_path=str(project_dir),
        framework=FrameworkType.FASTAPI,
        architecture=ArchitectureType.DOMAIN,
        database=DatabaseType.SQLITE,
        entities=[prod_entity],
    )

    generator = FastAPIGenerator()
    out_dir = generator.generate_project(config)

    # Domain structure
    product_module = out_dir / "app" / "modules" / "product"
    assert product_module.is_dir()
    assert (product_module / "models.py").is_file()
    assert (product_module / "schemas.py").is_file()
    assert (product_module / "router.py").is_file()

    # SQLite driver check
    reqs = (out_dir / "requirements.txt").read_text()
    assert "aiosqlite" in reqs

    # Verify all Python files are syntactically valid
    assert_all_python_files_compile(out_dir)
