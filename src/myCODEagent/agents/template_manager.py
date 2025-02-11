from pathlib import Path
from typing import Dict, List, Optional, Union
import yaml
import typer
from dataclasses import dataclass

@dataclass
class TemplateField:
    name: str
    type: str
    required: bool
    description: str
    default: Optional[str] = None
    options: Optional[List[str]] = None

@dataclass
class Template:
    name: str
    type: str  # assistant, project, command, etc.
    description: str
    fields: List[TemplateField]
    template_file: str

class TemplateManager:
    def __init__(self, template_dir: str = "templates"):
        self.template_dir = Path(template_dir)
        self.templates: Dict[str, Template] = {}
        self.load_templates()

    def load_templates(self):
        """Load all templates from the templates directory"""
        for yaml_file in self.template_dir.glob("*.yml"):
            with yaml_file.open() as f:
                try:
                    data = yaml.safe_load(f)
                    if not data:
                        continue
                        
                    # Handle different template types
                    if "assistant_config" in data:
                        self._process_assistant_template(yaml_file, data)
                    elif "project" in data:
                        self._process_project_template(yaml_file, data)
                    elif "commands" in data:
                        self._process_command_template(yaml_file, data)
                except yaml.YAMLError:
                    continue

    def _process_template(self, file: Path, data: dict, type_key: str) -> Template:
        """Process a template file and extract fields"""
        fields = []
        for field_name, field_data in data[type_key].items():
            if isinstance(field_data, dict):
                field = TemplateField(
                    name=field_name,
                    type=field_data.get("type", "str"),
                    required=field_data.get("required", True),
                    description=field_data.get("description", ""),
                    default=field_data.get("default"),
                    options=field_data.get("options", [])
                )
                fields.append(field)
        
        return Template(
            name=file.stem,
            type=type_key,
            description=data.get("description", ""),
            fields=fields,
            template_file=str(file)
        )

    def get_templates(self, type_filter: Optional[str] = None) -> List[Template]:
        """Get all templates, optionally filtered by type"""
        if type_filter:
            return [t for t in self.templates.values() if t.type == type_filter]
        return list(self.templates.values())

    def create_from_template(self, template_name: str, **kwargs) -> dict:
        """Create a new instance from a template with provided values"""
        if template_name not in self.templates:
            raise ValueError(f"Template {template_name} not found")
            
        template = self.templates[template_name]
        result = {}
        
        # Collect missing required fields
        for field in template.fields:
            if field.name not in kwargs and field.required:
                if field.options:
                    value = typer.prompt(
                        f"{field.description} ({'/'.join(field.options)})",
                        type=click.Choice(field.options)
                    )
                else:
                    value = typer.prompt(
                        field.description or f"Enter {field.name}",
                        default=field.default
                    )
                kwargs[field.name] = value
            
            result[field.name] = kwargs.get(field.name, field.default)
            
        return result

    def list_templates(self, type_filter: Optional[str] = None):
        """List available templates in a formatted way"""
        templates = self.get_templates(type_filter)
        for template in templates:
            typer.echo(f"\n{template.name} ({template.type})")
            typer.echo(f"Description: {template.description}")
            typer.echo("Fields:")
            for field in template.fields:
                required = "(required)" if field.required else "(optional)"
                default = f" [default: {field.default}]" if field.default else ""
                options = f" [options: {', '.join(field.options)}]" if field.options else ""
                typer.echo(f"  - {field.name}: {field.type} {required}{default}{options}")
                if field.description:
                    typer.echo(f"    {field.description}")
