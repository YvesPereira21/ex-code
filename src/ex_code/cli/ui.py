"""Rich UI styling, tables, banners, and feedback utilities."""

from pathlib import Path

from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ex_code.core.user_config import get_default_workspace_dir

console = Console()


def print_banner(title: str, subtitle: str = "") -> None:
    """Display an attractive panel banner."""
    content = f"[bold cyan]{title}[/bold cyan]"
    if subtitle:
        content += f"\n[dim]{subtitle}[/dim]"
    console.print(Panel(content, border_style="cyan", padding=(1, 2)))


def print_success(message: str) -> None:
    """Print success message."""
    console.print(f"[bold green]✔[/bold green] {message}")


def print_error(message: str) -> None:
    """Print error message."""
    console.print(f"[bold red]✖[/bold red] [red]{message}[/red]")


def print_warning(message: str) -> None:
    """Print warning message."""
    console.print(f"[bold yellow]⚠[/bold yellow] [yellow]{message}[/yellow]")


def display_project_summary(config) -> None:
    """Display a formatted Rich table summarizing project configuration and entities."""
    summary_table = Table(
        title="Resumo do Projeto", border_style="cyan", show_header=True
    )
    summary_table.add_column("Propriedade", style="bold")
    summary_table.add_column("Valor", style="green")

    summary_table.add_row("Nome", config.name)
    summary_table.add_row("Diretório", str(config.output_path))
    summary_table.add_row("Framework", config.framework.value.upper())
    summary_table.add_row(
        "Arquitetura",
        "Em Camadas" if config.architecture.value == "layered" else "Por Domínio",
    )
    summary_table.add_row("Banco de Dados", config.database.value.upper())
    if getattr(config, "group_id", None):
        summary_table.add_row("Group ID", config.group_id)
    if getattr(config, "artifact_id", None):
        summary_table.add_row("Artifact ID", config.artifact_id)
    if config.dependencies:
        summary_table.add_row("Dependências", ", ".join(config.dependencies))

    console.print(summary_table)

    if config.entities:
        ent_table = Table(
            title="Entidades e Campos", border_style="magenta", show_header=True
        )
        ent_table.add_column("Entidade", style="bold yellow")
        ent_table.add_column("Campos", style="white")
        ent_table.add_column("Relacionamentos", style="cyan")

        for entity in config.entities:
            fields_str = ", ".join(
                f"{f.name}: {f.type}" + (" (PK)" if f.is_pk else "")
                for f in entity.fields
            )
            rels_str = (
                ", ".join(
                    f"{r.name} ({r.relationship_type.value} -> {r.target_entity})"
                    for r in entity.relationships
                )
                or "-"
            )
            ent_table.add_row(entity.name, fields_str, rels_str)

        console.print(ent_table)


def display_editable_files_table(files: list[dict[str, str]]) -> None:
    """Display a Rich table of editable project files."""
    if not files:
        console.print("[dim]Nenhum arquivo editável (models/schemas) encontrado.[/dim]")
        return

    table = Table(
        title="Arquivos Editáveis Encontrados",
        border_style="cyan",
        show_header=True,
    )
    table.add_column("Tipo", style="bold cyan")
    table.add_column("Entidade", style="bold yellow")
    table.add_column("Arquivo", style="white")
    table.add_column("Caminho Relativo", style="dim")

    for item in files:
        table.add_row(
            item.get("type", "Arquivo"),
            item.get("entity", "-"),
            item.get("filename", "-"),
            item.get("rel_path", "-"),
        )

    console.print(table)


def display_diff(diff_text: str, filename: str) -> None:
    """Display a colored syntax-highlighted diff in the terminal."""
    from rich.syntax import Syntax

    if not diff_text.strip():
        console.print(f"[dim]Nenhuma alteração detectada em {filename}[/dim]")
        return

    syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=False)
    console.print(
        Panel(
            syntax,
            title=f"[bold]Alterações planejadas: {filename}[/bold]",
            border_style="yellow",
        )
    )


def select_directory(
    message: str = "Selecione o diretório:",
    start_path: Path | None = None,
    show_files: bool = True,
) -> Path:
    """Interactively browse and select a directory or file from the filesystem."""
    from InquirerPy import inquirer
    from InquirerPy.base.control import Choice

    default_workspace = get_default_workspace_dir()
    if start_path is None:
        if default_workspace and default_workspace.is_dir():
            current = default_workspace.resolve()
        else:
            current = Path.cwd().resolve()
    else:
        current = start_path.resolve()

    if current.is_file():
        current = current.parent

    while True:
        subdirs: list[Path] = []
        files: list[Path] = []
        try:
            for entry in sorted(current.iterdir(), key=lambda p: p.name.lower()):
                if entry.name.startswith("."):
                    continue
                if entry.is_dir():
                    subdirs.append(entry)
                elif show_files and entry.is_file():
                    files.append(entry)
        except (PermissionError, OSError):
            pass

        choices = [
            Choice(
                value=("select", current),
                name=f"✔  Selecionar esta pasta ({current})",
            )
        ]

        if (
            default_workspace
            and default_workspace.is_dir()
            and current != default_workspace
        ):
            choices.append(
                Choice(
                    value=("nav", default_workspace),
                    name=f"🏠 Ir para pasta padrão ({default_workspace.name or str(default_workspace)})",
                )
            )

        if current.parent != current:
            choices.append(
                Choice(
                    value=("nav", current.parent),
                    name=f"📂 .. (Subir para {current.parent.name or '/'})",
                )
            )

        for d in subdirs[:30]:
            tag = ""
            if (d / ".excode.json").is_file():
                tag = " [.excode]"
            elif (d / "pom.xml").is_file():
                tag = " [Spring Boot]"
            elif (d / "pyproject.toml").is_file() or (d / "main.py").is_file():
                tag = " [FastAPI]"

            choices.append(
                Choice(
                    value=("nav", d),
                    name=f"📁 {d.name}/{tag}",
                )
            )

        if show_files:
            for f in files[:30]:
                if f.name.endswith(".py"):
                    prefix = "🐍 "
                elif f.name.endswith(".java"):
                    prefix = "☕ "
                elif f.name.endswith((".json", ".toml", ".xml", ".yml", ".yaml")):
                    prefix = "⚙️  "
                else:
                    prefix = "📄 "

                choices.append(
                    Choice(
                        value=("select", f),
                        name=f"{prefix}{f.name}",
                    )
                )

        choices.append(
            Choice(
                value=("manual", None),
                name="✏️   Digitar outro caminho manualmente...",
            )
        )

        selected_action, selected_target = inquirer.select(
            message=f"{message} [Pasta atual: {current.name or '/'}]",
            choices=choices,
            default=choices[0].value,
        ).execute()

        if selected_action == "select":
            return selected_target
        if selected_action == "nav":
            current = selected_target
        elif selected_action == "manual":
            raw = (
                inquirer.text(
                    message="Digite o caminho:",
                    default=str(current),
                    validate=lambda x: (
                        len(x.strip()) > 0 or "O caminho não pode ser vazio."
                    ),
                )
                .execute()
                .strip()
            )
            return Path(raw).resolve()


def select_project(workspace_dir: Path | None = None) -> Path | None:
    """
    List available projects in workspace or current working directory and allow direct selection.
    Avoids tedious folder-by-folder navigation or browsing internal files.
    """
    default_ws = workspace_dir or get_default_workspace_dir()
    cwd = Path.cwd().resolve()

    def _is_project(p: Path) -> bool:
        if not p.is_dir():
            return False
        return (
            (p / ".excode.json").is_file()
            or (p / "ex-code.json").is_file()
            or (p / "pom.xml").is_file()
            or (p / "build.gradle").is_file()
            or (p / "build.gradle.kts").is_file()
            or (p / "pyproject.toml").is_file()
            or (p / "requirements.txt").is_file()
            or (p / "app" / "main.py").is_file()
            or (p / "main.py").is_file()
        )

    def _project_tag(p: Path) -> str:
        tags = []
        if (
            (p / "pom.xml").is_file()
            or (p / "build.gradle").is_file()
            or (p / "build.gradle.kts").is_file()
        ):
            tags.append("Spring Boot")
        elif (
            (p / "app" / "main.py").is_file()
            or (p / "main.py").is_file()
            or (p / "pyproject.toml").is_file()
        ):
            tags.append("FastAPI")
        if (p / ".excode.json").is_file() or (p / "ex-code.json").is_file():
            tags.append("ex-code")
        return f"[{' | '.join(tags)}]" if tags else ""

    candidate_paths: list[Path] = []
    seen: set[Path] = set()

    def _add_candidate(p: Path) -> None:
        resolved = p.resolve()
        if resolved not in seen and resolved.is_dir():
            seen.add(resolved)
            candidate_paths.append(resolved)

    # 1. Check if cwd is itself a project
    if _is_project(cwd):
        _add_candidate(cwd)

    # 2. Check subdirectories of default workspace
    search_roots = []
    if default_ws and default_ws.is_dir():
        search_roots.append(default_ws)
    if cwd not in search_roots:
        search_roots.append(cwd)

    for s_root in search_roots:
        try:
            for item in sorted(s_root.iterdir()):
                if (
                    item.is_dir()
                    and not item.name.startswith((".", "_"))
                    and item.name not in ("venv", "node_modules", "target")
                    and (_is_project(item) or s_root == default_ws)
                ):
                    _add_candidate(item)
        except OSError:
            pass

    choices = []
    for cp in candidate_paths:
        tag = _project_tag(cp)
        tag_str = f"  {tag}" if tag else ""
        label = f"📦 {cp.name}{tag_str}  ({cp})"
        choices.append(Choice(value=cp, name=label))

    choices.append(Choice(value="__browse__", name="📂 Navegar por outra pasta..."))
    choices.append(
        Choice(value="__manual__", name="✏️   Digitar caminho do projeto manualmente...")
    )
    choices.append(Choice(value=None, name="🚪 Cancelar / Voltar"))

    selected = inquirer.select(
        message="Selecione o projeto que deseja editar:",
        choices=choices,
        default=choices[0].value,
    ).execute()

    if selected is None:
        return None
    if isinstance(selected, Path):
        return selected
    if selected == "__browse__":
        return select_directory(
            message="Selecione a pasta do projeto existente:", show_files=False
        )
    if selected == "__manual__":
        raw = (
            inquirer.text(
                message="Digite o caminho da pasta do projeto:",
                default=str(cwd),
                validate=lambda x: (
                    len(x.strip()) > 0 or "O caminho não pode ser vazio."
                ),
            )
            .execute()
            .strip()
        )
        cand = Path(raw).expanduser().resolve()
        if not cand.exists():
            print_error(f"O caminho '{cand}' não existe.")
            return None
        return cand

    return None
