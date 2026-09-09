"""Abstract base class for framework project generators."""

from abc import ABC, abstractmethod
from pathlib import Path

from ex_code.core.models import ProjectConfig


class FrameworkGenerator(ABC):
    """Base interface for all project scaffolding generators."""

    @abstractmethod
    def generate_project(self, config: ProjectConfig) -> Path:
        """
        Generate a complete functional project skeleton based on ProjectConfig.

        Returns:
            Path: The root directory of the generated project.
        """
        raise NotImplementedError
