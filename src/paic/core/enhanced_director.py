from pathlib import Path
from typing import Dict, Any

import yaml

from core.director import Director


class EnhancedDirector(Director):
    def __init__(self, config_path: str):
        super().__init__(config_path)
        self.context = self._load_context()

    def _load_context(self) -> Dict[str, Any]:
        """Load and validate the context from aiden_context.yml"""
        context_path = Path("aiden_context.yml")
        if context_path.exists():
            with open(context_path) as f:
                return yaml.safe_load(f)
        return {}

    def create_new_ai_coding_prompt(self, *args, **kwargs):
        """Enhanced prompt creation with context"""
        base_prompt = super().create_new_ai_coding_prompt(*args, **kwargs)
        return f"""
     {base_prompt}
               """