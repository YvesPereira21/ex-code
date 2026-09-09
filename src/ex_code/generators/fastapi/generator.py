"""FastAPI project generator implementing FrameworkGenerator."""

import os
import shutil
import subprocess
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ex_code.core.metadata import MetadataManager
from ex_code.core.models import ProjectConfig
from ex_code.core.types import ArchitectureType
from ex_code.generators.base import FrameworkGenerator


class FastAPIGenerator(FrameworkGenerator):
    """Generator for scaffolding asynchronous FastAPI projects with SQLAlchemy 2.0 and Alembic."""

    def __init__(self) -> None:
        templates_dir = Path(__file__).parent / "templates"
        self.env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate_project(self, config: ProjectConfig) -> Path:
        """Generate the complete project tree for FastAPI."""
        output_dir = Path(config.output_path).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        # 1. Base project files
        self._render_file(
            "pyproject.toml.jinja", output_dir / "pyproject.toml", config=config
        )
        self._render_file(
            "requirements.txt.jinja", output_dir / "requirements.txt", config=config
        )
        self._render_file("README.md.jinja", output_dir / "README.md", config=config)
        self._render_file(
            "alembic.ini.jinja", output_dir / "alembic.ini", config=config
        )

        # 2. Alembic migrations setup
        alembic_dir = output_dir / "alembic"
        (alembic_dir / "versions").mkdir(parents=True, exist_ok=True)
        (alembic_dir / "versions" / ".gitkeep").touch()
        self._render_file("alembic/env.py.jinja", alembic_dir / "env.py", config=config)
        self._render_file(
            "alembic/script.py.mako.jinja",
            alembic_dir / "script.py.mako",
            config=config,
        )

        # 3. Core app directory
        app_dir = output_dir / "app"
        app_dir.mkdir(parents=True, exist_ok=True)
        (app_dir / "__init__.py").touch()

        core_dir = app_dir / "core"
        core_dir.mkdir(parents=True, exist_ok=True)
        (core_dir / "__init__.py").touch()
        self._render_file("config.py.jinja", core_dir / "config.py", config=config)
        self._render_file("database.py.jinja", core_dir / "database.py", config=config)

        # 4. Architecture-specific structure
        if config.architecture == ArchitectureType.LAYERED:
            self._generate_layered(app_dir, config)
        else:
            self._generate_domain(app_dir, config)

        # 5. Main application entrypoint
        self._render_file("main.py.jinja", app_dir / "main.py", config=config)

        # 6. Save metadata (.excode.json)
        MetadataManager.save_metadata(output_dir, config)

        # 7. Format generated code if ruff is available
        self._format_code(output_dir)

        return output_dir

    def _generate_layered(self, app_dir: Path, config: ProjectConfig) -> None:
        """Generate layered architecture: app/models/, app/schemas/, app/api/routers/."""
        models_dir = app_dir / "models"
        schemas_dir = app_dir / "schemas"
        routers_dir = app_dir / "api" / "routers"

        models_dir.mkdir(parents=True, exist_ok=True)
        schemas_dir.mkdir(parents=True, exist_ok=True)
        routers_dir.mkdir(parents=True, exist_ok=True)

        (models_dir / "__init__.py").touch()
        (schemas_dir / "__init__.py").touch()
        (app_dir / "api" / "__init__.py").touch()
        (routers_dir / "__init__.py").touch()

        for entity in config.entities:
            entity_key = entity.name.lower()
            self._render_file(
                "model.py.jinja",
                models_dir / f"{entity_key}.py",
                config=config,
                entity=entity,
            )
            self._render_file(
                "schema.py.jinja",
                schemas_dir / f"{entity_key}.py",
                config=config,
                entity=entity,
            )
            self._render_file(
                "router.py.jinja",
                routers_dir / f"{entity_key}.py",
                config=config,
                entity=entity,
            )

    def _generate_domain(self, app_dir: Path, config: ProjectConfig) -> None:
        """Generate domain architecture: app/modules/<feature>/(models.py, schemas.py, router.py)."""
        modules_dir = app_dir / "modules"
        modules_dir.mkdir(parents=True, exist_ok=True)
        (modules_dir / "__init__.py").touch()

        for entity in config.entities:
            entity_key = entity.name.lower()
            feature_dir = modules_dir / entity_key
            feature_dir.mkdir(parents=True, exist_ok=True)
            (feature_dir / "__init__.py").touch()

            self._render_file(
                "model.py.jinja",
                feature_dir / "models.py",
                config=config,
                entity=entity,
            )
            self._render_file(
                "schema.py.jinja",
                feature_dir / "schemas.py",
                config=config,
                entity=entity,
            )
            self._render_file(
                "router.py.jinja",
                feature_dir / "router.py",
                config=config,
                entity=entity,
            )

    def _render_file(self, template_name: str, target_path: Path, **context) -> None:
        """Render a Jinja2 template and write to target path."""
        template = self.env.get_template(template_name)
        content = template.render(**context)
        target_path.write_text(content, encoding="utf-8")

    def _format_code(self, project_dir: Path) -> None:
        """Try running ruff format on the generated project to ensure clean code."""
        ruff_bin = shutil.which("ruff")
        if not ruff_bin:
            # Check virtualenv bin
            venv_ruff = Path(os.environ.get("VIRTUAL_ENV", "")) / "bin" / "ruff"
            if venv_ruff.is_file():
                ruff_bin = str(venv_ruff)

        if ruff_bin:
            try:
                subprocess.run(
                    [ruff_bin, "format", str(project_dir / "app")],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except (subprocess.SubprocessError, OSError):
                # Formatador opcional; se falhar ou nao estiver disponivel, mantem o arquivo gerado
                return
