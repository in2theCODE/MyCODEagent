# utils/yaml_loader.py
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type, TypeVar
import yaml
from pathlib import Path

T = TypeVar('T')


@dataclass
class BaseSpec:
    """Base class for all specifications"""
    pass


@dataclass
class CommandSpec(BaseSpec):
    name: str
    description: str
    group: str
    parameters: List[Dict[str, Any]]
    database: Optional[Dict[str, Any]] = None
    permissions: Optional[List[str]] = None
    examples: Optional[List[Dict[str, Any]]] = None


@dataclass
class QuestionSpec(BaseSpec):
    id: str
    question: str
    type: str
    options: Optional[List[str]] = None


@dataclass
class AssistantConfigSpec(BaseSpec):
    assistant_name: str
    human_companion_name: Optional[str]
    ears: str
    brain: str
    voice: str
    elevenlabs_voice: Optional[str] = None


class TemplateLoader:
    """Generic YAML template loader"""

    def __init__(self, template_dir: str = "templates"):
        self.template_dir = Path(template_dir)
        self.spec_mappings = {
            "commands": CommandSpec,
            "questions": QuestionSpec,
            "assistant_config": AssistantConfigSpec
        }

    def load_template(self, template_name: str, spec_type: Type[T]) -> T:
        """Load a specific template and convert it to the specified spec type"""
        template_path = self.template_dir / f"{template_name}.yml"
        if not template_path.exists():
            raise FileNotFoundError(f"Template {template_name} not found")

        with template_path.open() as f:
            data = yaml.safe_load(f)
            return spec_type(**data)

    def load_all_templates(self, template_type: str) -> List[BaseSpec]:
        """Load all templates of a specific type"""
        if template_type not in self.spec_mappings:
            raise ValueError(f"Unknown template type: {template_type}")

        spec_class = self.spec_mappings[template_type]
        specs = []

        for yaml_file in self.template_dir.glob("*.yml"):
            with yaml_file.open() as f:
                try:
                    data = yaml.safe_load(f)
                    if template_type in data:  # Check if file contains relevant specs
                        specs.extend(spec_class(**item) for item in data[template_type])
                except (yaml.YAMLError, TypeError):
                    continue  # Skip files that don't match the expected format

        return specs

    def get_template_types(self) -> List[str]:
        """Get all available template types"""
        return list(self.spec_mappings.keys())