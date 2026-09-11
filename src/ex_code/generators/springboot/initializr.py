"""Client and fallback generator for Spring Initializr (start.spring.io)."""

import io
import os
import shutil
import subprocess
import tarfile
import urllib.parse
import urllib.request
from pathlib import Path

from ex_code.core.models import ProjectConfig
from ex_code.core.types import DatabaseType, to_snake_case


class SpringInitializrClient:
    """Handles downloading starter archives from start.spring.io with offline fallback."""

    INITIALIZR_URL = "https://start.spring.io/starter.tgz"

    @classmethod
    def download_and_extract(
        cls, config: ProjectConfig, target_dir: Path, offline: bool = False
    ) -> bool:
        """
        Download starter.tgz from start.spring.io using curl or urllib and extract into target_dir.
        Returns True if successful, False if offline/failed.
        """
        target_dir.mkdir(parents=True, exist_ok=True)
        artifact_id = to_snake_case(config.name).replace("_", "-")
        pkg_suffix = to_snake_case(config.name).replace("-", "").replace("_", "")
        package_name = f"com.excode.{pkg_suffix}"

        # If offline requested or environment variable set, generate locally and instantly
        if offline or os.environ.get("EX_CODE_OFFLINE") == "1":
            cls._create_offline_skeleton(config, target_dir, package_name, artifact_id)
            return True

        # Map dependencies
        deps = ["web", "data-jpa", "lombok", "validation"]
        if config.database == DatabaseType.POSTGRESQL:
            deps.append("postgresql")
        elif config.database == DatabaseType.MYSQL:
            deps.append("mysql")
        elif config.database == DatabaseType.SQLITE:
            deps.append("h2")

        for extra in config.dependencies:
            clean_dep = extra.strip().lower()
            if clean_dep and clean_dep not in deps:
                deps.append(clean_dep)

        data = {
            "type": "maven-project",
            "language": "java",
            "javaVersion": "21",
            "groupId": "com.excode",
            "artifactId": artifact_id,
            "name": config.name,
            "packageName": package_name,
            "dependencies": ",".join(deps),
            "baseDir": "",
        }

        # Try curl with strict timeouts and safe in-memory extraction
        curl_bin = shutil.which("curl")
        if curl_bin:
            try:
                curl_args = [
                    curl_bin,
                    "-s",
                    "-f",
                    "--connect-timeout",
                    "3",
                    "--max-time",
                    "8",
                    cls.INITIALIZR_URL,
                ]
                for k, v in data.items():
                    curl_args.extend(["-d", f"{k}={v}"])

                res = subprocess.run(
                    curl_args,
                    capture_output=True,
                    timeout=10,
                    check=False,
                )
                if res.returncode == 0 and res.stdout:
                    with tarfile.open(
                        fileobj=io.BytesIO(res.stdout), mode="r:gz"
                    ) as tar:
                        tar.extractall(path=target_dir)
                    if (target_dir / "pom.xml").is_file():
                        return True
            except (
                subprocess.SubprocessError,
                tarfile.TarError,
                OSError,
                TimeoutError,
            ):
                pass

        # Try urllib fallback with fast timeout
        try:
            encoded_data = urllib.parse.urlencode(data).encode("utf-8")
            req = urllib.request.Request(
                cls.INITIALIZR_URL,
                data=encoded_data,
                headers={"User-Agent": "ex-code/0.1.0"},
            )
            with urllib.request.urlopen(req, timeout=4) as response:
                content = response.read()
                with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as tar:
                    tar.extractall(path=target_dir)
                if (target_dir / "pom.xml").is_file():
                    return True
        except (urllib.error.URLError, tarfile.TarError, OSError, TimeoutError):
            pass

        # Fallback offline generator (instant, 100% offline, lightweight)
        cls._create_offline_skeleton(config, target_dir, package_name, artifact_id)
        return False

    @classmethod
    def _create_offline_skeleton(
        cls,
        config: ProjectConfig,
        target_dir: Path,
        package_name: str,
        artifact_id: str,
    ) -> None:
        """Create a valid baseline Maven Spring Boot project locally when offline."""
        app_name = "".join(
            x.capitalize()
            for x in config.name.replace("-", " ").replace("_", " ").split()
        )
        if not app_name.endswith("Application"):
            app_name += "Application"

        pkg_path = target_dir / "src" / "main" / "java" / Path(*package_name.split("."))
        pkg_path.mkdir(parents=True, exist_ok=True)
        res_path = target_dir / "src" / "main" / "resources"
        res_path.mkdir(parents=True, exist_ok=True)

        app_java = f"""package {package_name};

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class {app_name} {{
    public static void main(String[] args) {{
        SpringApplication.run({app_name}.class, args);
    }}
}}
"""
        (pkg_path / f"{app_name}.java").write_text(app_java, encoding="utf-8")
        (res_path / "application.properties").write_text("", encoding="utf-8")

        pom_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.4.1</version>
        <relativePath/>
    </parent>
    <groupId>com.excode</groupId>
    <artifactId>{artifact_id}</artifactId>
    <version>0.0.1-SNAPSHOT</version>
    <name>{config.name}</name>
    <description>{config.description or "Spring Boot project generated by ex-code"}</description>
    <properties>
        <java.version>21</java.version>
        <org.mapstruct.version>1.5.5.Final</org.mapstruct.version>
        <lombok-mapstruct-binding.version>0.2.0</lombok-mapstruct-binding.version>
    </properties>
    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <optional>true</optional>
        </dependency>
        <dependency>
            <groupId>org.mapstruct</groupId>
            <artifactId>mapstruct</artifactId>
            <version>${{org.mapstruct.version}}</version>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
"""
        (target_dir / "pom.xml").write_text(pom_content, encoding="utf-8")
