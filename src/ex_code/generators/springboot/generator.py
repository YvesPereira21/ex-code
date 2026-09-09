"""Spring Boot project generator implementing FrameworkGenerator."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ex_code.core.metadata import MetadataManager
from ex_code.core.models import ProjectConfig
from ex_code.core.types import ArchitectureType, to_snake_case
from ex_code.generators.base import FrameworkGenerator
from ex_code.generators.springboot.initializr import SpringInitializrClient


class SpringBootGenerator(FrameworkGenerator):
    """Generator for scaffolding Spring Boot 3.x/4.x projects with Maven, JPA, Lombok, and MapStruct."""

    def __init__(self) -> None:
        templates_dir = Path(__file__).parent / "templates"
        self.env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate_project(self, config: ProjectConfig) -> Path:
        """Generate Spring Boot project using start.spring.io and templates."""
        target_dir = Path(config.output_path).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)

        # 1. Download/extract starter from start.spring.io (or offline fallback)
        SpringInitializrClient.download_and_extract(config, target_dir)

        # 2. Enrich pom.xml with MapStruct and compiler plugin
        pom_path = target_dir / "pom.xml"
        if pom_path.is_file():
            self._enrich_pom_xml(pom_path)

        # 3. Configure application.properties
        res_dir = target_dir / "src" / "main" / "resources"
        res_dir.mkdir(parents=True, exist_ok=True)
        self._render_file(
            "application.properties.jinja",
            res_dir / "application.properties",
            config=config,
        )

        # 4. Generate README.md
        self._render_file("README.md.jinja", target_dir / "README.md", config=config)

        # 5. Detect or create base package directory
        base_pkg_dir, base_pkg_name = self._resolve_base_package(target_dir, config)

        # 6. Generate architecture components
        if config.architecture == ArchitectureType.LAYERED:
            self._generate_layered(base_pkg_dir, base_pkg_name, config)
        else:
            self._generate_domain(base_pkg_dir, base_pkg_name, config)

        # 7. Save metadata (.excode.json)
        MetadataManager.save_metadata(target_dir, config)

        return target_dir

    def _resolve_base_package(
        self, target_dir: Path, config: ProjectConfig
    ) -> tuple[Path, str]:
        """Find the Java package directory where Application.java resides."""
        java_root = target_dir / "src" / "main" / "java"
        if not java_root.is_dir():
            java_root.mkdir(parents=True, exist_ok=True)

        # Search for existing Application.java
        app_files = list(java_root.rglob("*Application.java"))
        if app_files:
            base_dir = app_files[0].parent
            rel_parts = base_dir.relative_to(java_root).parts
            pkg_name = ".".join(rel_parts)
            return base_dir, pkg_name

        # Default fallback package
        pkg_suffix = to_snake_case(config.name).replace("-", "").replace("_", "")
        pkg_name = f"com.excode.{pkg_suffix}"
        base_dir = java_root / Path(*pkg_name.split("."))
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir, pkg_name

    def _generate_layered(
        self, base_dir: Path, base_pkg: str, config: ProjectConfig
    ) -> None:
        """Generate layered architecture: model/, dto/, repository/, mapper/, service/, controller/."""
        model_dir = base_dir / "model"
        dto_dir = base_dir / "dto"
        repo_dir = base_dir / "repository"
        mapper_dir = base_dir / "mapper"
        service_dir = base_dir / "service"
        controller_dir = base_dir / "controller"

        for d in (
            model_dir,
            dto_dir,
            repo_dir,
            mapper_dir,
            service_dir,
            controller_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

        for entity in config.entities:
            # 1. Entity
            self._render_file(
                "Entity.java.jinja",
                model_dir / f"{entity.name}.java",
                package_name=f"{base_pkg}.model",
                entity=entity,
                relationship_imports=[],
            )

            # 2. DTOs (Records)
            dto_imports = []
            dtos_for_mapper = []
            # Generate default Request and Response DTOs
            req_schema = type(
                "ReqSchema",
                (),
                {
                    "name": f"{entity.name}RequestDTO",
                    "fields": [f for f in entity.fields if not f.is_pk],
                },
            )()
            res_schema = type(
                "ResSchema",
                (),
                {"name": f"{entity.name}ResponseDTO", "fields": entity.fields},
            )()

            all_dtos = [req_schema, res_schema]
            all_dtos.extend(entity.schemas)

            for d_item in all_dtos:
                self._render_file(
                    "RecordDTO.java.jinja",
                    dto_dir / f"{d_item.name}.java",
                    package_name=f"{base_pkg}.dto",
                    schema=d_item,
                )
                dto_imports.append(f"{base_pkg}.dto.{d_item.name}")
                dtos_for_mapper.append(d_item)

            # 3. Repository
            self._render_file(
                "Repository.java.jinja",
                repo_dir / f"{entity.name}Repository.java",
                package_name=f"{base_pkg}.repository",
                entity=entity,
                entity_import=f"{base_pkg}.model.{entity.name}",
            )

            # 4. Mapper
            self._render_file(
                "Mapper.java.jinja",
                mapper_dir / f"{entity.name}Mapper.java",
                package_name=f"{base_pkg}.mapper",
                entity=entity,
                entity_import=f"{base_pkg}.model.{entity.name}",
                dto_imports=dto_imports,
                dtos=dtos_for_mapper,
            )

            # 5. Service stub
            self._render_file(
                "Service.java.jinja",
                service_dir / f"{entity.name}Service.java",
                package_name=f"{base_pkg}.service",
                entity=entity,
                entity_import=f"{base_pkg}.model.{entity.name}",
                repository_import=f"{base_pkg}.repository.{entity.name}Repository",
                mapper_import=f"{base_pkg}.mapper.{entity.name}Mapper",
            )

            # 6. Controller stub
            self._render_file(
                "Controller.java.jinja",
                controller_dir / f"{entity.name}Controller.java",
                package_name=f"{base_pkg}.controller",
                entity=entity,
                entity_import=f"{base_pkg}.model.{entity.name}",
                service_import=f"{base_pkg}.service.{entity.name}Service",
            )

    def _generate_domain(
        self, base_dir: Path, base_pkg: str, config: ProjectConfig
    ) -> None:
        """Generate domain architecture: domain/<feature>/{Entity, DTO, Repository, Mapper, Service, Controller}."""
        domain_root = base_dir / "domain"
        domain_root.mkdir(parents=True, exist_ok=True)

        for entity in config.entities:
            feature_key = entity.name.lower()
            feature_dir = domain_root / feature_key
            feature_dir.mkdir(parents=True, exist_ok=True)
            feature_pkg = f"{base_pkg}.domain.{feature_key}"

            # 1. Entity
            self._render_file(
                "Entity.java.jinja",
                feature_dir / f"{entity.name}.java",
                package_name=feature_pkg,
                entity=entity,
                relationship_imports=[
                    f"{base_pkg}.domain.{rel.target_entity.lower()}.{rel.target_entity}"
                    for rel in entity.relationships
                    if rel.target_entity.lower() != feature_key
                ],
            )

            # 2. DTOs (Records)
            dto_imports = []
            dtos_for_mapper = []
            req_schema = type(
                "ReqSchema",
                (),
                {
                    "name": f"{entity.name}RequestDTO",
                    "fields": [f for f in entity.fields if not f.is_pk],
                },
            )()
            res_schema = type(
                "ResSchema",
                (),
                {"name": f"{entity.name}ResponseDTO", "fields": entity.fields},
            )()

            all_dtos = [req_schema, res_schema]
            all_dtos.extend(entity.schemas)

            for d_item in all_dtos:
                self._render_file(
                    "RecordDTO.java.jinja",
                    feature_dir / f"{d_item.name}.java",
                    package_name=feature_pkg,
                    schema=d_item,
                )
                dtos_for_mapper.append(d_item)

            # 3. Repository
            self._render_file(
                "Repository.java.jinja",
                feature_dir / f"{entity.name}Repository.java",
                package_name=feature_pkg,
                entity=entity,
                entity_import=f"{feature_pkg}.{entity.name}",
            )

            # 4. Mapper
            self._render_file(
                "Mapper.java.jinja",
                feature_dir / f"{entity.name}Mapper.java",
                package_name=feature_pkg,
                entity=entity,
                entity_import=f"{feature_pkg}.{entity.name}",
                dto_imports=dto_imports,
                dtos=dtos_for_mapper,
            )

            # 5. Service
            self._render_file(
                "Service.java.jinja",
                feature_dir / f"{entity.name}Service.java",
                package_name=feature_pkg,
                entity=entity,
                entity_import=f"{feature_pkg}.{entity.name}",
                repository_import=f"{feature_pkg}.{entity.name}Repository",
                mapper_import=f"{feature_pkg}.{entity.name}Mapper",
            )

            # 6. Controller
            self._render_file(
                "Controller.java.jinja",
                feature_dir / f"{entity.name}Controller.java",
                package_name=feature_pkg,
                entity=entity,
                entity_import=f"{feature_pkg}.{entity.name}",
                service_import=f"{feature_pkg}.{entity.name}Service",
            )

    def _render_file(self, template_name: str, target_path: Path, **context) -> None:
        """Render a Jinja2 template and write to target path."""
        template = self.env.get_template(template_name)
        content = template.render(**context)
        target_path.write_text(content, encoding="utf-8")

    def _enrich_pom_xml(self, pom_path: Path) -> None:
        """Ensure MapStruct dependency and compiler annotation processors are present in pom.xml."""
        content = pom_path.read_text(encoding="utf-8")

        # 1. Check properties
        if "<org.mapstruct.version>" not in content:
            mapstruct_props = """\t\t<org.mapstruct.version>1.5.5.Final</org.mapstruct.version>
\t\t<lombok-mapstruct-binding.version>0.2.0</lombok-mapstruct-binding.version>
\t</properties>"""
            content = content.replace("</properties>", mapstruct_props, 1)

        # 2. Check dependencies
        if "org.mapstruct" not in content:
            mapstruct_dep = """\t\t<dependency>
\t\t\t<groupId>org.mapstruct</groupId>
\t\t\t<artifactId>mapstruct</artifactId>
\t\t\t<version>${org.mapstruct.version}</version>
\t\t</dependency>
\t</dependencies>"""
            content = content.replace("</dependencies>", mapstruct_dep, 1)

        # 3. Check maven-compiler-plugin
        if "maven-compiler-plugin" not in content and "</plugins>" in content:
            compiler_plugin = """\t\t\t<plugin>
\t\t\t\t<groupId>org.apache.maven.plugins</groupId>
\t\t\t\t<artifactId>maven-compiler-plugin</artifactId>
\t\t\t\t<configuration>
\t\t\t\t\t<annotationProcessorPaths>
\t\t\t\t\t\t<path>
\t\t\t\t\t\t\t<groupId>org.projectlombok</groupId>
\t\t\t\t\t\t\t<artifactId>lombok</artifactId>
\t\t\t\t\t\t</path>
\t\t\t\t\t\t<path>
\t\t\t\t\t\t\t<groupId>org.projectlombok</groupId>
\t\t\t\t\t\t\t<artifactId>lombok-mapstruct-binding</artifactId>
\t\t\t\t\t\t\t<version>${lombok-mapstruct-binding.version}</version>
\t\t\t\t\t\t</path>
\t\t\t\t\t\t<path>
\t\t\t\t\t\t\t<groupId>org.mapstruct</groupId>
\t\t\t\t\t\t\t<artifactId>mapstruct-processor</artifactId>
\t\t\t\t\t\t\t<version>${org.mapstruct.version}</version>
\t\t\t\t\t\t</path>
\t\t\t\t\t</annotationProcessorPaths>
\t\t\t\t</configuration>
\t\t\t</plugin>
\t\t</plugins>"""
            content = content.replace("</plugins>", compiler_plugin, 1)

        pom_path.write_text(content, encoding="utf-8")
