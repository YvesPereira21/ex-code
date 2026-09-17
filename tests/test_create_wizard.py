"""Unit tests for CreateProjectWizard and CLI UI utilities."""

from pathlib import Path
from unittest.mock import patch

from ex_code.cli.ui import (
    display_project_summary,
    print_banner,
    print_error,
    print_success,
    print_warning,
)
from ex_code.cli.wizards.create_wizard import CreateProjectWizard
from ex_code.core.models import (
    EntityDefinition,
    FieldDefinition,
    ProjectConfig,
    create_pk_field,
)
from ex_code.core.types import (
    ArchitectureType,
    DatabaseType,
    FrameworkType,
    RelationshipType,
)


def test_ui_renderers(capsys):
    """Test that all UI rendering functions execute cleanly."""
    print_banner("TEST TITLE", "subtitle")
    print_success("Operation completed")
    print_error("Error occurred")
    print_warning("Warning check")

    config = ProjectConfig(
        name="test-app",
        output_path="/tmp/test",
        framework=FrameworkType.FASTAPI,
        architecture=ArchitectureType.LAYERED,
        database=DatabaseType.POSTGRESQL,
        dependencies=["redis"],
        entities=[
            EntityDefinition(
                name="User",
                fields=[create_pk_field("User", FrameworkType.FASTAPI)],
            )
        ],
    )
    display_project_summary(config)


def test_wizard_relationship_creation():
    """Test relationship configuration logic in step 3."""
    wizard = CreateProjectWizard()

    ent1 = EntityDefinition(
        name="User",
        fields=[create_pk_field("User", FrameworkType.FASTAPI)],
    )
    ent2 = EntityDefinition(
        name="Order",
        fields=[create_pk_field("Order", FrameworkType.FASTAPI)],
    )

    with (
        patch("InquirerPy.inquirer.confirm") as mock_confirm,
        patch("InquirerPy.inquirer.select") as mock_select,
        patch("InquirerPy.inquirer.text") as mock_text,
    ):
        mock_confirm.return_value.execute.side_effect = [True, True]
        mock_select.return_value.execute.side_effect = [
            "Order",
            "User",
            RelationshipType.MANY_TO_ONE,
            "Finalizar relacionamentos",
        ]
        mock_text.return_value.execute.return_value = "user"

        result = wizard.step_3_relationships([ent1, ent2])
        assert len(result) == 2

        # Check Order has ManyToOne -> User
        order = next(e for e in result if e.name == "Order")
        assert len(order.relationships) == 1
        assert order.relationships[0].relationship_type == RelationshipType.MANY_TO_ONE
        assert order.relationships[0].target_entity == "User"

        # Check User has OneToMany -> Order (bidirectional)
        user = next(e for e in result if e.name == "User")
        assert len(user.relationships) == 1
        assert user.relationships[0].relationship_type == RelationshipType.ONE_TO_MANY
        assert user.relationships[0].target_entity == "Order"


def test_step_4_schemas_auto_fastapi():
    """Test schema auto-generation in step 4 for FastAPI (no DTO suffix)."""
    wizard = CreateProjectWizard()

    pk = create_pk_field("Customer", FrameworkType.FASTAPI)
    name_field = FieldDefinition(name="fullName", type="str")
    ent = EntityDefinition(name="Customer", fields=[pk, name_field])

    with patch("InquirerPy.inquirer.confirm") as mock_confirm:
        # 1st confirm: auto generate schemas? -> True
        # 2nd confirm: add custom schemas? -> False
        mock_confirm.return_value.execute.side_effect = [True, False]

        result = wizard.step_4_schemas([ent], framework=FrameworkType.FASTAPI)
        customer = result[0]
        assert len(customer.schemas) == 3

        schema_names = [s.name for s in customer.schemas]
        assert "Customer" in schema_names
        assert "CustomerList" in schema_names
        assert "CustomerUpdate" in schema_names

        main_schema = next(s for s in customer.schemas if s.name == "Customer")
        assert len(main_schema.fields) == 2

        list_schema = next(s for s in customer.schemas if s.name == "CustomerList")
        assert len(list_schema.fields) == 2

        up_schema = next(s for s in customer.schemas if s.name == "CustomerUpdate")
        assert len(up_schema.fields) == 1
        assert up_schema.fields[0].is_nullable is True


def test_step_4_schemas_auto_springboot():
    """Test schema auto-generation in step 4 for Spring Boot (NomeDTO, NomeListDTO, NomeUpdateDTO)."""
    wizard = CreateProjectWizard()

    pk = create_pk_field("Customer", FrameworkType.SPRINGBOOT)
    name_field = FieldDefinition(name="fullName", type="str")
    ent = EntityDefinition(name="Customer", fields=[pk, name_field])

    with patch("InquirerPy.inquirer.confirm") as mock_confirm:
        # 1st confirm: auto generate DTOs? -> True
        # 2nd confirm: add custom DTOs? -> False
        mock_confirm.return_value.execute.side_effect = [True, False]

        result = wizard.step_4_schemas([ent], framework=FrameworkType.SPRINGBOOT)
        customer = result[0]
        assert len(customer.schemas) == 3

        schema_names = [s.name for s in customer.schemas]
        assert "CustomerDTO" in schema_names
        assert "CustomerListDTO" in schema_names
        assert "CustomerUpdateDTO" in schema_names

        main_dto = next(s for s in customer.schemas if s.name == "CustomerDTO")
        assert len(main_dto.fields) == 2

        up_dto = next(s for s in customer.schemas if s.name == "CustomerUpdateDTO")
        assert len(up_dto.fields) == 1
        assert up_dto.fields[0].is_nullable is True


def test_step_4_schemas_no_auto_fastapi():
    """Test schema generation when auto-generation is declined for FastAPI."""
    wizard = CreateProjectWizard()

    pk = create_pk_field("Customer", FrameworkType.FASTAPI)
    name_field = FieldDefinition(name="fullName", type="str")
    ent = EntityDefinition(name="Customer", fields=[pk, name_field])

    with patch("InquirerPy.inquirer.confirm") as mock_confirm:
        # 1st confirm: auto generate schemas? -> False
        # 2nd confirm: add custom schemas? -> False
        mock_confirm.return_value.execute.side_effect = [False, False]

        result = wizard.step_4_schemas([ent], framework=FrameworkType.FASTAPI)
        customer = result[0]
        assert len(customer.schemas) == 3
        assert wizard.auto_generate_schemas is False

        schema_names = [s.name for s in customer.schemas]
        assert "Customer" in schema_names
        assert "CustomerList" in schema_names
        assert "CustomerUpdate" in schema_names

        for s in customer.schemas:
            assert len(s.fields) == 0


def test_step_4_schemas_no_auto_springboot():
    """Test schema generation when auto-generation is declined for Spring Boot."""
    wizard = CreateProjectWizard()

    pk = create_pk_field("Customer", FrameworkType.SPRINGBOOT)
    name_field = FieldDefinition(name="fullName", type="str")
    ent = EntityDefinition(name="Customer", fields=[pk, name_field])

    with patch("InquirerPy.inquirer.confirm") as mock_confirm:
        # 1st confirm: auto generate DTOs? -> False
        # 2nd confirm: add custom DTOs? -> False
        mock_confirm.return_value.execute.side_effect = [False, False]

        result = wizard.step_4_schemas([ent], framework=FrameworkType.SPRINGBOOT)
        customer = result[0]
        assert len(customer.schemas) == 3
        assert wizard.auto_generate_schemas is False

        schema_names = [s.name for s in customer.schemas]
        assert "CustomerDTO" in schema_names
        assert "CustomerListDTO" in schema_names
        assert "CustomerUpdateDTO" in schema_names

        for s in customer.schemas:
            assert len(s.fields) == 0


def test_step_1_basic_info_springboot(tmp_path: Path):
    wizard = CreateProjectWizard()

    with (
        patch(
            "ex_code.cli.wizards.create_wizard.select_directory",
            return_value=tmp_path,
        ),
        patch(
            "ex_code.cli.wizards.create_wizard.get_default_workspace_dir",
            return_value=tmp_path,
        ),
        patch("InquirerPy.inquirer.text") as mock_text,
        patch("InquirerPy.inquirer.select") as mock_select,
    ):
        mock_text.return_value.execute.side_effect = [
            "demo-service",  # project name
            "Demo description",  # description
            "com.empresa.departamento",  # groupId
            "servico-pedidos",  # artifactId
        ]
        mock_select.return_value.execute.return_value = FrameworkType.SPRINGBOOT

        info = wizard.step_1_basic_info()
        assert info["name"] == "demo-service"
        assert info["description"] == "Demo description"
        assert info["framework"] == FrameworkType.SPRINGBOOT
        assert info["group_id"] == "com.empresa.departamento"
        assert info["artifact_id"] == "servico-pedidos"
