import shutil
from pathlib import Path
from typing import List

import yaml


class SpecPromptGenerator:
    def __init__(self):
        self.template_dir = Path(__file__).parent.parent / "templates"

    def create_project(
        self,
        name: str,
        template: str = "basic",
        patterns: List[str] = [],
        include_docs: bool = True,
    ):
        """Create a new project from template"""
        # Create project directory
        project_dir = Path(name)
        project_dir.mkdir(exist_ok=True)

        # Copy template files
        template_path = self.template_dir / "project_templates" / template
        self._copy_template(template_path, project_dir)

        # Add selected patterns
        if patterns:
            self._add_patterns(project_dir, patterns)

        # Add documentation
        if include_docs:
            self._add_documentation(project_dir)

        # Generate project files
        self._generate_project(str(project_dir), name, template, patterns)

    def _generate_project(
        self, project_dir: str, name: str, template: str, patterns: List[str]
    ) -> None:
        """Generate project files"""
        # Create project directory
        import os

        os.makedirs(project_dir, exist_ok=True)

        # Initialize aiden context
        self._init_aiden_context(project_dir, name, template, patterns),

    def create_feature_spec(
        self, name: str, template: str = "feature.yml", patterns: List[str] = []
    ) -> Path:
        """Create a new feature specification"""
        template_path = self.template_dir / "spec_templates" / template
        spec_path = Path(f"specs/{name}.yml")
        spec_path.parent.mkdir(exist_ok=True)

        # Load and customize template
        with open(template_path) as f:
            spec = yaml.safe_load(f)

        # Add patterns if specified
        if patterns:
            spec["patterns"] = patterns

    def _add_documentation(self, project_dir):
        pass

    def _init_aiden_context(self, project_dir, name, template, patterns):
        pass

    def _add_patterns(self, project_dir, patterns):
        pass

    def _copy_template(self, template_path, project_dir):
        pass
