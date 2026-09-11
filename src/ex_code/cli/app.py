"""Main interactive CLI application orchestrator for ex-code."""

import sys

from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from rich.panel import Panel

from ex_code.cli.ui import console, print_error, print_success
from ex_code.cli.wizards.create_wizard import CreateProjectWizard
from ex_code.cli.wizards.edit_wizard import EditProjectWizard

BANNER_ART = """[bold cyan]
  ███████╗██╗  ██╗      ██████╗ ██████╗ ██████╗ ███████╗
  ██╔════╝╚██╗██╔╝     ██╔════╝██╔═══██╗██╔══██╗██╔════╝
  █████╗   ╚███╔╝█████╗██║     ██║   ██║██║  ██║█████╗  
  ██╔══╝   ██╔██╗╚════╝██║     ██║   ██║██║  ██║██╔══╝  
  ███████╗██╔╝ ██╗     ╚██████╗╚██████╔╝██████╔╝███████╗
  ╚══════╝╚═╝  ╚═╝      ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝[/bold cyan]"""


def display_welcome_banner() -> None:
    """Display the introductory welcome banner using Rich."""
    welcome_text = (
        f"{BANNER_ART}\n\n"
        "[bold white]Automação de Scaffolding e Edição Cirúrgica de Backends[/bold white]\n"
        "[dim]Suporte especializado para [cyan]FastAPI[/cyan] e [green]Spring Boot[/green] (Camadas & Domínio)[/dim]"
    )
    console.print(
        Panel(
            welcome_text,
            border_style="cyan",
            padding=(1, 2),
        )
    )


class CLIApplication:
    """Manages the main menu navigation loop and error handling."""

    def __init__(self) -> None:
        self.create_wizard = CreateProjectWizard()
        self.edit_wizard = EditProjectWizard()

    def run(self) -> int:
        """Run the main interactive menu loop."""
        display_welcome_banner()

        while True:
            try:
                choice = inquirer.select(
                    message="O que você deseja fazer?",
                    choices=[
                        Choice("create", "✨  Criar novo projeto"),
                        Choice("edit", "🔧  Editar projeto existente"),
                        Choice("exit", "🚪  Sair"),
                    ],
                    default="create",
                ).execute()

                if not choice or choice == "exit":
                    console.print(
                        "\n[bold green]Obrigado por utilizar o ex-code! Até a próxima.[/bold green]\n"
                    )
                    return 0
                if choice == "create":
                    self._handle_create()
                elif choice == "edit":
                    self._handle_edit()

            except (KeyboardInterrupt, EOFError):
                console.print(
                    "\n\n[yellow]Operação interrompida pelo usuário. Encerrando o ex-code...[/yellow]\n"
                )
                return 0
            except Exception as exc:  # noqa: BLE001
                print_error(f"Ocorreu um erro inesperado: {exc}")
                if not sys.stdin.isatty():
                    # Stop non-interactive loop immediately to avoid infinite recursion/CPU spikes
                    return 1
                console.print("[dim]Retornando ao menu principal...[/dim]\n")

    def _handle_create(self) -> None:
        """Run creation wizard with exception handling."""
        try:
            result = self.create_wizard.run()
            if result:
                print_success(f"Projeto gerado com sucesso em: [bold]{result}[/bold]\n")
        except (KeyboardInterrupt, EOFError):
            console.print(
                "\n[yellow]Criação de projeto cancelada pelo usuário.[/yellow]\n"
            )
        except Exception as exc:  # noqa: BLE001
            print_error(f"Falha durante a criação do projeto: {exc}\n")

    def _handle_edit(self) -> None:
        """Run edit wizard with exception handling."""
        try:
            result = self.edit_wizard.run()
            if result:
                print_success(
                    f"Edição concluída com sucesso no projeto: [bold]{result}[/bold]\n"
                )
        except (KeyboardInterrupt, EOFError):
            console.print(
                "\n[yellow]Edição de projeto cancelada pelo usuário.[/yellow]\n"
            )
        except Exception as exc:  # noqa: BLE001
            print_error(f"Falha durante a edição do projeto: {exc}\n")


def run_app() -> int:
    """CLI entrypoint function."""
    app = CLIApplication()
    return app.run()


if __name__ == "__main__":
    sys.exit(run_app())
