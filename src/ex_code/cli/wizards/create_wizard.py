"""Interactive wizard for project creation (Steps 1 to 6) using InquirerPy and Rich."""

from pathlib import Path

from InquirerPy import inquirer
from InquirerPy.base.control import Choice

from ex_code.cli.ui import (
    console,
    display_project_summary,
    print_banner,
    print_success,
)
from ex_code.core.models import (
    EntityDefinition,
    FieldDefinition,
    ProjectConfig,
    RelationshipDefinition,
    SchemaDefinition,
    SchemaFieldDefinition,
    create_pk_field,
)
from ex_code.core.types import (
    ArchitectureType,
    DatabaseType,
    FrameworkType,
    RelationshipType,
    get_supported_types,
    resolve_framework_type,
    to_pascal_case,
    to_snake_case,
)
from ex_code.generators.fastapi.generator import FastAPIGenerator
from ex_code.generators.springboot.generator import SpringBootGenerator


class CreateProjectWizard:
    """Orchestrates interactive questions for creating a new backend project."""

    def run(self) -> Path | None:
        """Execute all 6 wizard steps interactively."""
        print_banner(
            "CRIAR NOVO PROJETO",
            "Assistente de geração de projetos FastAPI e Spring Boot",
        )

        # ETAPA 1: Informações Básicas
        step1_data = self.step_1_basic_info()

        # ETAPA 2: Entidades e Campos
        entities = self.step_2_entities(step1_data["framework"])

        # ETAPA 3: Relacionamentos
        entities = self.step_3_relationships(entities)

        # ETAPA 4: Schemas / DTOs
        entities = self.step_4_schemas(entities)

        # ETAPA 5: Arquitetura
        architecture = self.step_5_architecture()

        # ETAPA 6: Banco de Dados e Dependências
        db_type, dependencies = self.step_6_database_and_dependencies(
            step1_data["framework"]
        )

        # Montar ProjectConfig
        config = ProjectConfig(
            name=step1_data["name"],
            output_path=str(step1_data["output_path"]),
            description=step1_data["description"],
            framework=step1_data["framework"],
            architecture=architecture,
            database=db_type,
            dependencies=dependencies,
            entities=entities,
        )

        # Resumo e Confirmação
        console.print("\n")
        display_project_summary(config)

        confirm = inquirer.confirm(
            message="Deseja gerar o projeto com as configurações acima?",
            default=True,
        ).execute()

        if not confirm:
            console.print("[yellow]Operação cancelada pelo usuário.[/yellow]")
            return None

        # Geração
        with console.status(
            "[bold green]Gerando projeto...[/bold green]", spinner="dots"
        ):
            if config.framework == FrameworkType.FASTAPI:
                generator = FastAPIGenerator()
            else:
                generator = SpringBootGenerator()
            out_dir = generator.generate_project(config)

        print_success(f"Projeto gerado com sucesso em: [bold]{out_dir}[/bold]")
        console.print(
            f"\nPara começar, acesse:\n  [bold cyan]cd {out_dir}[/bold cyan]\n"
        )
        return out_dir

    def step_1_basic_info(self) -> dict:
        """Etapa 1: Caminho do diretório, nome do projeto, descrição e framework."""
        console.print("\n[bold cyan]Etapa 1: Informações Gerais[/bold cyan]")

        out_path = inquirer.text(
            message="Informe o caminho do diretório onde o projeto será criado:",
            default="./meu-projeto",
            validate=lambda x: len(x.strip()) > 0 or "O caminho não pode ser vazio.",
        ).execute()

        name = inquirer.text(
            message="Nome do projeto:",
            default=Path(out_path).name,
            validate=lambda x: len(x.strip()) > 0 or "O nome não pode ser vazio.",
        ).execute()

        description = inquirer.text(
            message="Descrição do projeto (opcional):",
            default="",
        ).execute()

        framework_choice = inquirer.select(
            message="Escolha o framework:",
            choices=[
                Choice(FrameworkType.FASTAPI, "FastAPI (Python)"),
                Choice(FrameworkType.SPRINGBOOT, "Spring Boot (Java 21 / Maven)"),
            ],
            default=FrameworkType.FASTAPI,
        ).execute()

        return {
            "output_path": Path(out_path).resolve(),
            "name": name.strip(),
            "description": description.strip() or None,
            "framework": framework_choice,
        }

    def step_2_entities(self, framework: FrameworkType) -> list[EntityDefinition]:
        """Etapa 2: Definição de entidades e seus respectivos campos."""
        console.print("\n[bold cyan]Etapa 2: Entidades do Projeto[/bold cyan]")
        entities: list[EntityDefinition] = []
        supported_types = get_supported_types(framework)

        while True:
            ent_name = (
                inquirer.text(
                    message="Nome da entidade (ou pressione Enter sem digitar nada para avançar):",
                    validate=lambda x: True,
                )
                .execute()
                .strip()
            )

            if not ent_name:
                if not entities:
                    console.print(
                        "[yellow]Pelo menos uma entidade deve ser cadastrada.[/yellow]"
                    )
                    continue
                break

            ent_pascal = to_pascal_case(ent_name)
            pk_field = create_pk_field(ent_pascal, framework)
            fields: list[FieldDefinition] = [pk_field]
            console.print(
                f"[dim]Chave primária '{pk_field.name}: {pk_field.type}' gerada automaticamente.[/dim]"
            )

            # Adicionar campos
            while True:
                field_name = (
                    inquirer.text(
                        message=f"  Campo para '{ent_pascal}' (ou Enter para finalizar campos):",
                    )
                    .execute()
                    .strip()
                )

                if not field_name:
                    break

                field_type = inquirer.select(
                    message=f"  Tipo do campo '{field_name}':",
                    choices=supported_types,
                ).execute()

                is_nullable = inquirer.confirm(
                    message=f"  O campo '{field_name}' aceita valor nulo (opcional)?",
                    default=False,
                ).execute()

                is_unique = inquirer.confirm(
                    message=f"  O campo '{field_name}' é único (unique)?",
                    default=False,
                ).execute()

                native_type = resolve_framework_type(field_type, framework)
                fields.append(
                    FieldDefinition(
                        name=field_name,
                        type=native_type,
                        is_nullable=is_nullable,
                        is_unique=is_unique,
                    )
                )

            entities.append(EntityDefinition(name=ent_pascal, fields=fields))
            console.print(
                f"[green]✔ Entidade '{ent_pascal}' adicionada com {len(fields)} campos.[/green]"
            )

        return entities

    def step_3_relationships(
        self, entities: list[EntityDefinition]
    ) -> list[EntityDefinition]:
        """Etapa 3: Definição de relacionamentos entre entidades criadas."""
        console.print(
            "\n[bold cyan]Etapa 3: Relacionamentos entre Entidades[/bold cyan]"
        )
        if len(entities) < 2:
            console.print(
                "[dim]Menos de 2 entidades cadastradas. Pulando etapa de relacionamentos.[/dim]"
            )
            return entities

        has_rel = inquirer.confirm(
            message="Deseja definir relacionamentos entre as entidades?",
            default=True,
        ).execute()

        if not has_rel:
            return entities

        entity_names = [e.name for e in entities]

        while True:
            source_name = inquirer.select(
                message="Selecione a entidade de origem (ou 'Finalizar'):",
                choices=entity_names + ["Finalizar relacionamentos"],
            ).execute()

            if source_name == "Finalizar relacionamentos":
                break

            target_choices = [name for name in entity_names if name != source_name]
            if not target_choices:
                continue

            target_name = inquirer.select(
                message=f"Entidade relacionada com '{source_name}':",
                choices=target_choices,
            ).execute()

            rel_type = inquirer.select(
                message=f"Tipo de relacionamento de '{source_name}' para '{target_name}':",
                choices=[
                    Choice(RelationshipType.MANY_TO_ONE, "ManyToOne (N:1)"),
                    Choice(RelationshipType.ONE_TO_MANY, "OneToMany (1:N)"),
                    Choice(RelationshipType.ONE_TO_ONE, "OneToOne (1:1)"),
                    Choice(RelationshipType.MANY_TO_MANY, "ManyToMany (N:N)"),
                ],
            ).execute()

            prop_name = (
                inquirer.text(
                    message=f"Nome da propriedade na entidade '{source_name}':",
                    default=to_snake_case(target_name)
                    if rel_type
                    in (RelationshipType.MANY_TO_ONE, RelationshipType.ONE_TO_ONE)
                    else f"{to_snake_case(target_name)}s",
                )
                .execute()
                .strip()
            )

            is_bidirectional = inquirer.confirm(
                message="Criar relacionamento bidirecional automaticamente na outra entidade?",
                default=True,
            ).execute()

            # Adicionar na entidade de origem
            source_ent = next(e for e in entities if e.name == source_name)
            target_ent = next(e for e in entities if e.name == target_name)

            source_rel = RelationshipDefinition(
                name=prop_name,
                relationship_type=rel_type,
                source_entity=source_name,
                target_entity=target_name,
                is_bidirectional=is_bidirectional,
            )
            source_ent.relationships.append(source_rel)

            # Adicionar na entidade de destino se bidirecional
            if is_bidirectional:
                reverse_type_map = {
                    RelationshipType.MANY_TO_ONE: RelationshipType.ONE_TO_MANY,
                    RelationshipType.ONE_TO_MANY: RelationshipType.MANY_TO_ONE,
                    RelationshipType.ONE_TO_ONE: RelationshipType.ONE_TO_ONE,
                    RelationshipType.MANY_TO_MANY: RelationshipType.MANY_TO_MANY,
                }
                reverse_type = reverse_type_map[rel_type]
                reverse_name = (
                    to_snake_case(source_name)
                    if reverse_type
                    in (RelationshipType.MANY_TO_ONE, RelationshipType.ONE_TO_ONE)
                    else f"{to_snake_case(source_name)}s"
                )
                target_rel = RelationshipDefinition(
                    name=reverse_name,
                    relationship_type=reverse_type,
                    source_entity=target_name,
                    target_entity=source_name,
                    is_bidirectional=True,
                )
                target_ent.relationships.append(target_rel)

            console.print(
                f"[green]✔ Relacionamento '{source_name}.{prop_name}' ({rel_type.value} -> {target_name}) registrado.[/green]"
            )

        return entities

    def step_4_schemas(
        self, entities: list[EntityDefinition]
    ) -> list[EntityDefinition]:
        """Etapa 4: Definição e assistência de Schemas/DTOs."""
        console.print("\n[bold cyan]Etapa 4: Schemas e DTOs[/bold cyan]")

        auto_generate = inquirer.confirm(
            message="Deseja gerar automaticamente os DTOs/Schemas padrões (Request e Response) baseados nos campos das entidades?",
            default=True,
        ).execute()

        for entity in entities:
            if auto_generate:
                req_fields = [
                    SchemaFieldDefinition(
                        name=f.name, type=f.type, is_nullable=f.is_nullable
                    )
                    for f in entity.fields
                    if not f.is_pk
                ]
                res_fields = [
                    SchemaFieldDefinition(
                        name=f.name, type=f.type, is_nullable=f.is_nullable
                    )
                    for f in entity.fields
                ]
                entity.schemas.append(
                    SchemaDefinition(name=f"{entity.name}RequestDTO", fields=req_fields)
                )
                entity.schemas.append(
                    SchemaDefinition(
                        name=f"{entity.name}ResponseDTO", fields=res_fields
                    )
                )

            # Opção de DTOs customizados
            add_custom = inquirer.confirm(
                message=f"Deseja criar DTOs/Schemas customizados para a entidade '{entity.name}'?",
                default=False,
            ).execute()

            while add_custom:
                schema_name = (
                    inquirer.text(
                        message=f"Nome do Schema/DTO customizado para '{entity.name}' (ou Enter para sair):",
                    )
                    .execute()
                    .strip()
                )

                if not schema_name:
                    break

                fields: list[SchemaFieldDefinition] = []
                for f in entity.fields:
                    include = inquirer.confirm(
                        message=f"  Incluir campo '{f.name}: {f.type}' no schema?",
                        default=True,
                    ).execute()
                    if include:
                        fields.append(
                            SchemaFieldDefinition(
                                name=f.name, type=f.type, is_nullable=f.is_nullable
                            )
                        )

                entity.schemas.append(SchemaDefinition(name=schema_name, fields=fields))
                console.print(
                    f"[green]✔ Schema '{schema_name}' adicionado com {len(fields)} campos.[/green]"
                )

        return entities

    def step_5_architecture(self) -> ArchitectureType:
        """Etapa 5: Escolha da estrutura arquitetural e de diretórios."""
        console.print("\n[bold cyan]Etapa 5: Estrutura Arquitetural[/bold cyan]")
        return inquirer.select(
            message="Escolha o padrão de organização arquitetural:",
            choices=[
                Choice(
                    ArchitectureType.LAYERED,
                    "Arquitetura em Camadas (models, schemas/dtos, routers/controllers, services)",
                ),
                Choice(
                    ArchitectureType.DOMAIN,
                    "Arquitetura Separada por Domínio (módulos independentes por funcionalidade)",
                ),
            ],
            default=ArchitectureType.LAYERED,
        ).execute()

    def step_6_database_and_dependencies(
        self, framework: FrameworkType
    ) -> tuple[DatabaseType, list[str]]:
        """Etapa 6: Escolha do banco de dados e dependências adicionais."""
        console.print(
            "\n[bold cyan]Etapa 6: Banco de Dados e Dependências Adicionais[/bold cyan]"
        )

        db_choice = inquirer.select(
            message="Escolha o banco de dados principal:",
            choices=[
                Choice(DatabaseType.POSTGRESQL, "PostgreSQL"),
                Choice(DatabaseType.MYSQL, "MySQL"),
                Choice(DatabaseType.SQLITE, "SQLite / H2 (Em memória / local)"),
            ],
            default=DatabaseType.POSTGRESQL,
        ).execute()

        # Dependências populares curadas
        popular_deps = {
            FrameworkType.FASTAPI: [
                Choice(
                    "pydantic-settings", "Pydantic Settings (gerenciamento de .env)"
                ),
                Choice("python-jose", "JWT Authentication (python-jose)"),
                Choice("passlib", "Password Hashing (passlib com bcrypt)"),
                Choice("redis", "Redis Cache / Celery client"),
            ],
            FrameworkType.SPRINGBOOT: [
                Choice("security", "Spring Security (Autenticação e Autorização)"),
                Choice("actuator", "Spring Boot Actuator (Métricas e Healthchecks)"),
                Choice("springdoc-openapi", "SpringDoc OpenAPI / Swagger UI"),
            ],
        }

        selected_deps = inquirer.checkbox(
            message="Selecione bibliotecas adicionais pré-configuradas (espaço para marcar):",
            choices=popular_deps.get(framework, []),
        ).execute()

        custom_deps_raw = (
            inquirer.text(
                message="Bibliotecas adicionais personalizadas (separadas por vírgula, ou Enter para pular):",
                default="",
            )
            .execute()
            .strip()
        )

        final_deps = list(selected_deps)
        if custom_deps_raw:
            for dep in custom_deps_raw.split(","):
                d = dep.strip()
                if d and d not in final_deps:
                    final_deps.append(d)

        return db_choice, final_deps
