"""Detector for framework and architecture of existing projects."""

from pathlib import Path

from ex_code.core.types import ArchitectureType, FrameworkType


class ProjectDetector:
    """Detects whether an existing project uses FastAPI or Spring Boot, and its architecture pattern."""

    @classmethod
    def find_project_root(cls, start_path: Path | str) -> Path:
        """Find the root directory of a project by traversing upwards from start_path."""
        current = Path(start_path).resolve()
        if current.is_file():
            current = current.parent

        # 1. Primary project root markers
        for candidate in [current, *current.parents]:
            if (
                (candidate / ".excode.json").is_file()
                or (candidate / "ex-code.json").is_file()
                or (candidate / "pom.xml").is_file()
                or (candidate / "build.gradle").is_file()
                or (candidate / "build.gradle.kts").is_file()
                or (candidate / "pyproject.toml").is_file()
                or (candidate / "requirements.txt").is_file()
                or (candidate / "app" / "main.py").is_file()
            ):
                return candidate

        # 2. Secondary fallback (standalone root with main.py)
        for candidate in [current, *current.parents]:
            if (candidate / "main.py").is_file():
                return candidate
        return current

    @classmethod
    def detect_framework(cls, project_path: Path | str) -> FrameworkType | None:
        """Detect the framework used in the given directory."""
        path = Path(project_path).resolve()
        if not path.is_dir():
            return None

        # 0. Check for .excode.json or ex-code.json
        for meta_name in (".excode.json", "ex-code.json"):
            meta = path / meta_name
            if meta.is_file():
                try:
                    import json

                    data = json.loads(meta.read_text(encoding="utf-8"))
                    fw = data.get("framework")
                    if fw:
                        return FrameworkType(str(fw).lower())
                except (json.JSONDecodeError, OSError, ValueError):
                    continue

        # Check for Spring Boot indicators
        pom_xml = path / "pom.xml"
        if pom_xml.is_file():
            content = pom_xml.read_text(encoding="utf-8", errors="ignore")
            if "org.springframework.boot" in content or "spring-boot" in content:
                return FrameworkType.SPRINGBOOT

        gradle_file = path / "build.gradle"
        gradle_kts = path / "build.gradle.kts"
        if gradle_file.is_file() or gradle_kts.is_file():
            content = (gradle_file if gradle_file.is_file() else gradle_kts).read_text(
                encoding="utf-8", errors="ignore"
            )
            if "org.springframework.boot" in content or "spring" in content:
                return FrameworkType.SPRINGBOOT

        # Check for FastAPI indicators
        pyproject = path / "pyproject.toml"
        if pyproject.is_file():
            content = pyproject.read_text(encoding="utf-8", errors="ignore")
            if "fastapi" in content.lower():
                return FrameworkType.FASTAPI

        reqs = path / "requirements.txt"
        if reqs.is_file():
            content = reqs.read_text(encoding="utf-8", errors="ignore")
            if "fastapi" in content.lower():
                return FrameworkType.FASTAPI

        # Check for app/main.py or main.py
        for candidate in (path / "app" / "main.py", path / "main.py"):
            if candidate.is_file():
                content = candidate.read_text(encoding="utf-8", errors="ignore")
                if "fastapi" in content.lower():
                    return FrameworkType.FASTAPI

        return None

    @classmethod
    def detect_architecture(
        cls, project_path: Path | str, framework: FrameworkType
    ) -> ArchitectureType:
        """Detect whether the project adopts a layered or domain-based architecture."""
        path = Path(project_path).resolve()

        if framework == FrameworkType.FASTAPI:
            if (path / "app" / "modules").is_dir() or (path / "modules").is_dir():
                return ArchitectureType.DOMAIN
            return ArchitectureType.LAYERED
        elif framework == FrameworkType.SPRINGBOOT:
            java_root = path / "src" / "main" / "java"
            if java_root.is_dir():
                for d in java_root.rglob("domain"):
                    if d.is_dir():
                        return ArchitectureType.DOMAIN
            return ArchitectureType.LAYERED

        return ArchitectureType.LAYERED
