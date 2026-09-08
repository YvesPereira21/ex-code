"""Agnostic and framework-specific types, conversions, and naming conventions."""

import re
from enum import Enum


class FrameworkType(str, Enum):
    FASTAPI = "fastapi"
    SPRINGBOOT = "springboot"


class ArchitectureType(str, Enum):
    LAYERED = "layered"
    DOMAIN = "domain"


class DatabaseType(str, Enum):
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"


class RelationshipType(str, Enum):
    ONE_TO_ONE = "OneToOne"
    ONE_TO_MANY = "OneToMany"
    MANY_TO_ONE = "ManyToOne"
    MANY_TO_MANY = "ManyToMany"


# Agnostic primitive types
FASTAPI_TYPE_MAP: dict[str, str] = {
    "string": "str",
    "integer": "int",
    "bigint": "int",
    "float": "float",
    "decimal": "Decimal",
    "boolean": "bool",
    "datetime": "datetime",
    "date": "date",
    "time": "time",
    "uuid": "UUID",
    "bytes": "bytes",
    "text": "str",
}

SPRINGBOOT_TYPE_MAP: dict[str, str] = {
    "string": "String",
    "integer": "Integer",
    "bigint": "Long",
    "float": "Double",
    "decimal": "BigDecimal",
    "boolean": "Boolean",
    "datetime": "LocalDateTime",
    "date": "LocalDate",
    "time": "LocalTime",
    "uuid": "UUID",
    "bytes": "byte[]",
    "text": "String",
}


def get_supported_types(framework: FrameworkType | str) -> list[str]:
    """Return the list of displayable supported types for a framework."""
    fw = framework.value if isinstance(framework, FrameworkType) else framework.lower()
    if fw == FrameworkType.FASTAPI:
        return list(FASTAPI_TYPE_MAP.values())
    elif fw == FrameworkType.SPRINGBOOT:
        return list(SPRINGBOOT_TYPE_MAP.values())
    raise ValueError(f"Framework '{framework}' não suportado.")


def resolve_framework_type(
    agnostic_or_direct_type: str, framework: FrameworkType | str
) -> str:
    """Resolve an agnostic type or direct type to the framework's native type representation."""
    fw = framework.value if isinstance(framework, FrameworkType) else framework.lower()
    normalized = agnostic_or_direct_type.strip()
    key = normalized.lower()

    if fw == FrameworkType.FASTAPI:
        if key in FASTAPI_TYPE_MAP:
            return FASTAPI_TYPE_MAP[key]
        # If the user directly chose a FastAPI type (e.g. 'str', 'UUID')
        for v in FASTAPI_TYPE_MAP.values():
            if v.lower() == key:
                return v
        return normalized
    elif fw == FrameworkType.SPRINGBOOT:
        if key in SPRINGBOOT_TYPE_MAP:
            return SPRINGBOOT_TYPE_MAP[key]
        for v in SPRINGBOOT_TYPE_MAP.values():
            if v.lower() == key:
                return v
        return normalized
    raise ValueError(f"Framework '{framework}' não suportado.")


def to_snake_case(name: str) -> str:
    """Convert PascalCase or camelCase to snake_case."""
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return s.lower().replace("-", "_")


def to_camel_case(name: str) -> str:
    """Convert snake_case or PascalCase to camelCase."""
    components = to_snake_case(name).split("_")
    return components[0] + "".join(x.capitalize() for x in components[1:])


def to_pascal_case(name: str) -> str:
    """Convert snake_case or camelCase to PascalCase."""
    components = to_snake_case(name).split("_")
    return "".join(x.capitalize() for x in components if x)


def generate_pk_name(entity_name: str, framework: FrameworkType | str) -> str:
    """
    Generate primary key attribute name based on framework conventions:
    - FastAPI: <entity_name>_id (snake_case)
    - Spring Boot: <entityName>Id (camelCase)
    """
    fw = framework.value if isinstance(framework, FrameworkType) else framework.lower()
    entity_clean = to_snake_case(entity_name)

    if fw == FrameworkType.FASTAPI:
        return f"{entity_clean}_id"
    elif fw == FrameworkType.SPRINGBOOT:
        return to_camel_case(f"{entity_clean}_id")
    raise ValueError(f"Framework '{framework}' não suportado.")


def generate_db_column_name(name: str) -> str:
    """Generate database column name in snake_case."""
    return to_snake_case(name)
