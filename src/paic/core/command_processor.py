from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from pathlib import Path
import time
import yaml
import re

@dataclass
class VoiceParameter:
    name: str
    type: str
    required: bool
    voice_prompt: str
    validation_regex: Optional[str] = None
    options: Optional[List[str]] = None

@dataclass
class VoiceCommand:
    name: str
    voice_triggers: List[str]
    description: str
    parameters: List[VoiceParameter]
    confirmation_required: bool
    success_message: str
    error_message: Optional[str] = None
    confirmation_prompt: Optional[str] = None

class VoiceCommandProcessor:
    def __init__(self, template_dir: str = "templates"):
        self.template_dir = Path(template_dir)
        self.commands: Dict[str, VoiceCommand] = {}
        self.command_history: List[Dict[str, Any]] = []
        self.load_commands()

    def load_commands(self):
        """Load voice commands from YAML template"""
        command_file = self.template_dir / "voice_commands.yml"
        if not command_file.exists():
            raise FileNotFoundError("Voice commands template not found")

        with command_file.open() as f:
            data = yaml.safe_load(f)
            for cmd in data.get("voice_commands", []):
                params = [VoiceParameter(**p) for p in cmd["parameters"]]
                command = VoiceCommand(
                    name=cmd["name"],
                    voice_triggers=cmd["voice_triggers"],
                    description=cmd["description"],
                    parameters=params,
                    confirmation_required=cmd["confirmation_required"],
                    success_message=cmd["success_message"],
                    error_message=cmd.get("error_message"),
                    confirmation_prompt=cmd.get("confirmation_prompt")
                )
                self.commands[cmd["name"]] = command
                # Also index by triggers for quick lookup
                for trigger in cmd["voice_triggers"]:
                    self.commands[trigger.lower()] = command

    def find_matching_command(self, text: str) -> Optional[VoiceCommand]:
        """Find a command that matches the voice input using fuzzy matching"""
        text = text.lower()
        
        # First check command history for recent successful matches
        for hist in reversed(self.command_history[-5:]):
            if hist["success"] and self._calculate_similarity(text, hist["input"]) > 0.9:
                return self.commands.get(hist["command"])
        
        # Try exact matches with triggers
        if text in self.commands:
            self._add_to_history(text, self.commands[text].name, True)
            return self.commands[text]

        # Then try partial matches with confidence scoring
        best_match = None
        best_score = 0.0
        
        for cmd in self.commands.values():
            for trigger in cmd.voice_triggers:
                # Calculate similarity score
                score = self._calculate_similarity(text, trigger.lower())
                if score > best_score and score > 0.7:  # Minimum confidence threshold
                    best_score = score
                    best_match = cmd
        
        if best_match:
            self._add_to_history(text, best_match.name, True)
        else:
            self._add_to_history(text, None, False)
            
        return best_match

    def _add_to_history(self, input_text: str, command: Optional[str], success: bool):
        """Add command attempt to history"""
        self.command_history.append({
            "input": input_text,
            "command": command,
            "success": success,
            "timestamp": time.time()
        })
        # Keep history manageable
        if len(self.command_history) > 100:
            self.command_history = self.command_history[-100:]
        
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity score between two strings"""
        # Simple Levenshtein distance-based similarity
        from difflib import SequenceMatcher
        return SequenceMatcher(None, text1, text2).ratio()

    def validate_parameter(self, param: VoiceParameter, value: str) -> bool:
        """Validate parameter value against constraints"""
        if param.validation_regex and not re.match(param.validation_regex, value):
            return False
        if param.options and value.lower() not in [opt.lower() for opt in param.options]:
            return False
        return True

    def format_message(self, message: str, params: Dict[str, Any]) -> str:
        """Format message with parameter values"""
        try:
            return message.format(**params)
        except KeyError:
            return message
