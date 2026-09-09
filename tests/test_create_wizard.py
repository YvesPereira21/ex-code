"""Unit tests for CreateProjectWizard and CLI UI utilities."""

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


def test_wizard_schemas_step():
    """Test schema auto-generation in step 4."""
    wizard = CreateProjectWizard()

    pk = create_pk_field("Customer", FrameworkType.FASTAPI)
    name_field = FieldDefinition(name="fullName", type="str")
    ent = EntityDefinition(name="Customer", fields=[pk, name_field])

    with patch("InquirerPy.inquirer.confirm") as mock_confirm:
        # 1st confirm: auto generate DTOs? -> True
        # 2nd confirm: add custom schemas? -> False
        mock_confirm.return_value.execute.side_effect = [True, False]

        result = wizard.step_4_schemas([ent])
        customer = result[0]
        assert len(customer.schemas) == 2

        schema_names = [s.name for s in customer.schemas]
        assert "CustomerRequestDTO" in schema_names
        assert "CustomerResponseDTO" in schema_names

        req_schema = next(s for s in customer.schemas if s.name == "CustomerRequestDTO")
        assert len(req_schema.fields) == 1
        assert req_schema.fields[0].name == "fullName"

        res_schema = next(
            s for s in customer.schemas if s.name == "CustomerResponseDTO"
        )
        assert len(res_schema.fields) == 2
