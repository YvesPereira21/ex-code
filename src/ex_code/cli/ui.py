"""Rich UI styling, tables, banners, and feedback utilities."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

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
