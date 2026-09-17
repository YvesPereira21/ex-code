"""Interactive wizard for editing existing projects (Entities and Schemas/DTOs)."""

from pathlib import Path

from InquirerPy import inquirer
from InquirerPy.base.control import Choice

from ex_code.analyzer.project_scanner import ProjectScanner
from ex_code.cli.ui import (
    console,
    display_diff,
    display_project_summary,
    print_banner,
    print_error,
    print_success,
    print_warning,
    select_project,
)
from ex_code.core.models import (
    FieldDefinition,
    ProjectConfig,
    RelationshipDefinition,
)
from ex_code.core.types import (
    FrameworkType,
    RelationshipType,
    get_supported_types,
    resolve_framework_type,
)
from ex_code.modifiers.base import CodeModifier, generate_diff
from ex_code.modifiers.fastapi_modifier import FastAPICodeModifier
from ex_code.modifiers.springboot_modifier import SpringBootCodeModifier


class EditProjectWizard:
    """Orchestrates interactive questions for safely editing an existing backend project."""

    def run(self) -> Path | None:
        """Run the interactive edit wizard."""
        print_banner(
            "EDITAR PROJETO", "Análise e modificação cirúrgica com backup preventivo"
        )

        selected_project = select_project()
        if not selected_project:
            return None

        try:
            config = ProjectScanner.scan_project(selected_project)
            project_path = Path(config.output_path).resolve()
        except (FileNotFoundError, ValueError, OSError) as e:
            print_error(f"Falha ao analisar projeto: {e}")
            return None

        print_success(f"Projeto identificado com sucesso: [bold]{config.name}[/bold]")
        display_project_summary(config)

        if config.framework == FrameworkType.FASTAPI:
            modifier: CodeModifier = FastAPICodeModifier(project_path, config)
        else:
            modifier: CodeModifier = SpringBootCodeModifier(project_path, config)

        term_schema = "Schema" if config.framework == FrameworkType.FASTAPI else "DTO"

        while True:
            choice = inquirer.select(
                message=f"\nO que deseja alterar no projeto '{config.name}'?",
                choices=[
                    Choice(
                        "entity",
                        f"🏛️  Entidade ({len(config.entities)} disponíveis)",
                    ),
                    Choice(
                        "schema",
                        f"📋 {term_schema} ({len(config.entities)} disponíveis)",
                    ),
                    Choice("exit", "🚪 Finalizar / Sair"),
                ],
            ).execute()

            if choice == "exit":
                break
            elif choice == "entity":
                self._edit_entity_flow(modifier, config)
            elif choice == "schema":
                self._edit_schema_flow(modifier, config)

        print_success("Sessão de edição concluída.")
        return project_path

    def _edit_by_file_flow(
        self,
        modifier: CodeModifier,
        config,
        editable_files: list[dict[str, str]],
    ) -> None:
        """Select a specific file to edit."""
        if not editable_files:
            print_warning("Nenhum arquivo editável encontrado no projeto.")
            return

        choices = [
            Choice(
                value=item,
                name=f"{item['rel_path']}  [{item['type']}: {item['entity']}]",
            )
            for item in editable_files
        ]
        choices.append(Choice(value=None, name="Voltar"))

        selected = inquirer.select(
            message="Selecione o arquivo que deseja editar:",
            choices=choices,
        ).execute()

        if not selected:
            return

        ent_name = selected["entity"]
        file_type = selected["type"]

        if "Schema" in file_type or "DTO" in file_type:
            self._edit_schema_flow(
                modifier, config, editable_files, default_entity_name=ent_name
            )
        else:
            self._edit_entity_flow(modifier, config, default_entity_name=ent_name)

    def _edit_entity_flow(
        self, modifier: CodeModifier, config, default_entity_name: str | None = None
    ) -> None:
        """Submenu for editing entities."""
        if not config.entities:
            print_warning("Nenhuma entidade encontrada no projeto para edição.")
            return

        if default_entity_name:
            selected_ent = config.get_entity(default_entity_name)
        else:
            choices = []
            for e in config.entities:
                file_hint = e.model_path or (
                    f"{config.models_path}/{e.name.lower()}.py"
                    if config.framework == FrameworkType.FASTAPI and config.models_path
                    else f"app/models/{e.name.lower()}.py"
                    if config.framework == FrameworkType.FASTAPI
                    else f"{config.models_path}/{e.name}.java"
                    if config.models_path
                    else f"{e.name}.java"
                )
                choices.append(Choice(value=e.name, name=f"{e.name}  ({file_hint})"))
            choices.append(Choice(value="back", name="Voltar"))

            selected_ent_name = inquirer.select(
                message="Selecione a entidade/model que deseja editar:",
                choices=choices,
            ).execute()

            if selected_ent_name == "back":
                return

            selected_ent = config.get_entity(selected_ent_name)

        if not selected_ent:
            return

        ent_names = [e.name for e in config.entities]
        action = inquirer.select(
            message=f"Ação para a entidade '{selected_ent.name}':",
            choices=[
                Choice("add_field", "Adicionar campo"),
                Choice("remove_field", "Remover campo"),
                Choice("change_field_name", "Alterar nome de um campo"),
                Choice("change_field_type", "Alterar tipo de um campo"),
                Choice("add_rel", "Adicionar relacionamento"),
                Choice("remove_rel", "Remover relacionamento"),
                Choice("back", "Voltar"),
            ],
        ).execute()

        if action == "back":
            return

        changes = []
        if action == "add_field":
            changes = self._action_add_field(modifier, selected_ent, config.framework)
        elif action == "remove_field":
            changes = self._action_remove_field(modifier, selected_ent)
        elif action == "change_field_name":
            changes = self._action_change_field_name(modifier, selected_ent)
        elif action == "change_field_type":
            changes = self._action_change_field_type(
                modifier, selected_ent, config.framework
            )
        elif action == "add_rel":
            changes = self._action_add_rel(modifier, selected_ent, ent_names)
        elif action == "remove_rel":
            changes = self._action_remove_rel(modifier, selected_ent)

        if changes:
            self._preview_and_apply(modifier, changes)

    def _action_add_field(
        self, modifier: CodeModifier, entity, framework: FrameworkType
    ) -> list:
        field_name = inquirer.text(message="Nome do novo campo:").execute().strip()
        if not field_name:
            return []

        supported_types = get_supported_types(framework)
        field_type = inquirer.select(
            message=f"Tipo do campo '{field_name}':",
            choices=supported_types,
        ).execute()

        is_nullable = inquirer.confirm(
            message="Campo aceita nulo (opcional)?", default=False
        ).execute()
        is_unique = inquirer.confirm(
            message="Campo possui valor único (unique)?", default=False
        ).execute()

        native_type = resolve_framework_type(field_type, framework)
        new_field = FieldDefinition(
            name=field_name,
            type=native_type,
            is_nullable=is_nullable,
            is_unique=is_unique,
        )
        return modifier.add_field(entity.name, new_field)

    def _action_remove_field(self, modifier: CodeModifier, entity) -> list:
        field_choices = [f.name for f in entity.fields if not f.is_pk]
        if not field_choices:
            print_warning("Esta entidade não possui campos removíveis.")
            return []

        field_to_remove = inquirer.select(
            message="Selecione o campo a remover:",
            choices=field_choices + ["Cancelar"],
        ).execute()

        if field_to_remove == "Cancelar":
            return []

        return modifier.remove_field(entity.name, field_to_remove)

    def _action_change_field_name(self, modifier: CodeModifier, entity) -> list:
        field_choices = [f.name for f in entity.fields if not f.is_pk]
        if not field_choices:
            return []

        field_name = inquirer.select(
            message="Campo a renomear:", choices=field_choices
        ).execute()
        new_name = (
            inquirer.text(message=f"Novo nome para '{field_name}':").execute().strip()
        )
        if not new_name or new_name == field_name:
            return []

        orig_field = next(f for f in entity.fields if f.name == field_name)
        new_field = orig_field.model_copy(update={"name": new_name})
        return modifier.update_field(entity.name, field_name, new_field)

    def _action_change_field_type(
        self, modifier: CodeModifier, entity, framework: FrameworkType
    ) -> list:
        field_choices = [f.name for f in entity.fields if not f.is_pk]
        if not field_choices:
            return []

        field_name = inquirer.select(
            message="Campo a alterar o tipo:", choices=field_choices
        ).execute()
        new_type = inquirer.select(
            message="Novo tipo:", choices=get_supported_types(framework)
        ).execute()
        native_type = resolve_framework_type(new_type, framework)

        orig_field = next(f for f in entity.fields if f.name == field_name)
        new_field = orig_field.model_copy(update={"type": native_type})
        return modifier.update_field(entity.name, field_name, new_field)

    def _action_add_rel(
        self, modifier: CodeModifier, entity, all_entity_names: list[str]
    ) -> list:
        target_choices = [name for name in all_entity_names if name != entity.name]
        if not target_choices:
            print_warning("Não há outras entidades para relacionar.")
            return []

        target_name = inquirer.select(
            message="Entidade relacionada:", choices=target_choices
        ).execute()
        rel_type = inquirer.select(
            message="Tipo de relacionamento:",
            choices=[
                Choice(RelationshipType.MANY_TO_ONE, "ManyToOne (N:1)"),
                Choice(RelationshipType.ONE_TO_MANY, "OneToMany (1:N)"),
                Choice(RelationshipType.ONE_TO_ONE, "OneToOne (1:1)"),
                Choice(RelationshipType.MANY_TO_MANY, "ManyToMany (N:N)"),
            ],
        ).execute()

        prop_name = (
            inquirer.text(message="Nome da propriedade de relacionamento:")
            .execute()
            .strip()
        )
        if not prop_name:
            return []

        rel = RelationshipDefinition(
            name=prop_name,
            relationship_type=rel_type,
            source_entity=entity.name,
            target_entity=target_name,
        )
        return modifier.add_relationship(rel)

    def _action_remove_rel(self, modifier: CodeModifier, entity) -> list:
        if not entity.relationships:
            print_warning("Esta entidade não possui relacionamentos registrados.")
            return []

        rel_choices = [r.name for r in entity.relationships]
        rel_name = inquirer.select(
            message="Selecione o relacionamento para remover:",
            choices=rel_choices + ["Cancelar"],
        ).execute()

        if rel_name == "Cancelar":
            return []

        return modifier.remove_relationship(entity.name, rel_name)

    def _edit_schema_flow(
        self,
        modifier: CodeModifier,
        config,
        editable_files: list[dict[str, str]] | None = None,
        default_entity_name: str | None = None,
    ) -> None:
        """Submenu for editing Schemas/DTOs."""
        if not config.entities:
            print_warning("Nenhum schema encontrado no projeto para edição.")
            return

        term = "Schema" if config.framework == FrameworkType.FASTAPI else "DTO"
        if default_entity_name:
            selected_ent = config.get_entity(default_entity_name)
        else:
            choices = []
            for e in config.entities:
                file_hint = e.schema_path or (
                    f"{config.schemas_path}/{e.name.lower()}.py"
                    if config.framework == FrameworkType.FASTAPI and config.schemas_path
                    else f"app/schemas/{e.name.lower()}.py"
                    if config.framework == FrameworkType.FASTAPI
                    else f"{config.schemas_path}/{e.name}DTO.java"
                    if config.schemas_path
                    else f"{e.name}DTO.java"
                )
                choices.append(
                    Choice(
                        value=e.name,
                        name=f"{term} de {e.name}  ({file_hint})",
                    )
                )
            choices.append(Choice(value="back", name="Voltar"))

            selected_name = inquirer.select(
                message=f"Selecione o {term} que deseja editar:",
                choices=choices,
            ).execute()

            if selected_name == "back":
                return

            selected_ent = config.get_entity(selected_name)

        if not selected_ent:
            return

        console.print(
            f"\n[cyan]Editando {term} de [bold]{selected_ent.name}[/bold]. As alterações serão sincronizadas com o código do projeto.[/cyan]\n"
        )

        action = inquirer.select(
            message=f"Ação para o {term} '{selected_ent.name}':",
            choices=[
                Choice("add_field", f"Adicionar campo ao {term} (sincroniza Model)"),
                Choice("remove_field", f"Remover campo do {term} (sincroniza Model)"),
                Choice("change_field_name", "Alterar nome de um campo"),
                Choice("change_field_type", "Alterar tipo de um campo"),
                Choice("back", "Voltar"),
            ],
        ).execute()

        if action == "back":
            return

        changes = []
        if action == "add_field":
            changes = self._action_add_field(modifier, selected_ent, config.framework)
        elif action == "remove_field":
            changes = self._action_remove_field(modifier, selected_ent)
        elif action == "change_field_name":
            changes = self._action_change_field_name(modifier, selected_ent)
        elif action == "change_field_type":
            changes = self._action_change_field_type(
                modifier, selected_ent, config.framework
            )

        if changes:
            self._preview_and_apply(modifier, changes)

    def _preview_and_apply(
        self, modifier: CodeModifier, changes: list[tuple[Path, str, str]]
    ) -> None:
        """Display diff and request confirmation before applying changes and creating backup."""
        console.print(
            "\n[bold yellow]PRÉ-VISUALIZAÇÃO DAS ALTERAÇÕES (DIFF):[/bold yellow]\n"
        )

        for path, orig, mod in changes:
            diff_text = generate_diff(orig, mod, path.name)
            display_diff(diff_text, path.name)

        confirm = inquirer.confirm(
            message="Deseja criar backup de segurança e aplicar as alterações acima?",
            default=True,
        ).execute()

        if confirm:
            with console.status(
                "[bold green]Criando backup e aplicando alterações...[/bold green]"
            ):
                backup_dir = modifier.apply_changes(changes, make_backup=True)
            if (
                hasattr(modifier, "config")
                and hasattr(modifier, "project_path")
                and isinstance(getattr(modifier, "config", None), ProjectConfig)
            ):
                from ex_code.core.metadata import MetadataManager

                MetadataManager.save_metadata(modifier.project_path, modifier.config)
            print_success("Alterações aplicadas com sucesso!")
            if backup_dir:
                console.print(
                    f"[dim]Backup de segurança salvo em: {backup_dir}[/dim]\n"
                )
        else:
            print_warning("Alterações descartadas pelo usuário.")
