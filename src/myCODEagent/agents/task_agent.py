import json
import os
from typing import Any, Dict, List

from .base_agent import AgentConfig, AgentResponse, BaseAgent


class TaskAgentConfig(AgentConfig):
    """Configuration for task agent that handles file operations and simple tasks"""

    allowed_operations: List[str] = ["read_file", "write_file", "list_directory"]
    workspace_path: str = "."


class TaskAgent(BaseAgent):
    """Agent responsible for handling simple file operations and tasks"""

    def _validate_config(self) -> None:
        if not os.path.exists(self.config.workspace_path):
            raise ValueError(
                f"Workspace path {self.config.workspace_path} does not exist"
            )

        for op in self.config.allowed_operations:
            if op not in self._get_supported_operations():
                raise ValueError(f"Operation {op} not supported")

    def _setup_client(self) -> None:
        # No external API needed for basic file operations
        pass

    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        try:
            operation = input_data.get("operation")
            if operation not in self.config.allowed_operations:
                return AgentResponse(
                    success=False,
                    message=f"Operation {operation} not allowed",
                    error="Operation not permitted",
                )

            result = self._execute_operation(operation, input_data.get("params", {}))
            return AgentResponse(
                success=True,
                message=f"Successfully executed {operation}",
                data=result,
            )
        except Exception as e:
            return AgentResponse(
                success=False, message=f"Failed to execute {operation}", error=str(e)
            )

    def _execute_operation(
        self, operation: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute the requested operation"""
        if operation == "read_file":
            return self._read_file(params["path"])
        elif operation == "write_file":
            return self._write_file(params["path"], params["content"])
        elif operation == "list_directory":
            return self._list_directory(params.get("path", "."))
        else:
            raise ValueError(f"Unknown operation: {operation}")

    def _read_file(self, path: str) -> Dict[str, Any]:
        """Read file contents"""
        full_path = os.path.join(self.config.workspace_path, path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File {path} not found")

        with open(full_path, "r") as f:
            content = f.read()

        return {"path": path, "content": content, "size": os.path.getsize(full_path)}

    def _write_file(self, path: str, content: str) -> Dict[str, Any]:
        """Write content to file"""
        full_path = os.path.join(self.config.workspace_path, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, "w") as f:
            f.write(content)

        return {"path": path, "size": os.path.getsize(full_path)}

    def _list_directory(self, path: str) -> Dict[str, Any]:
        """List directory contents"""
        full_path = os.path.join(self.config.workspace_path, path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Directory {path} not found")

        entries = []
        for entry in os.scandir(full_path):
            entries.append(
                {
                    "name": entry.name,
                    "type": "file" if entry.is_file() else "directory",
                    "size": entry.stat().st_size if entry.is_file() else None,
                }
            )

        return {"path": path, "entries": entries}

    def _get_supported_models(self) -> Dict[str, str]:
        return {"local": "Local file system operations, no AI model required"}

    def _get_required_permissions(self) -> Dict[str, str]:
        return {
            "file_read": "Permission to read files",
            "file_write": "Permission to write files",
            "directory_list": "Permission to list directory contents",
        }

    def _get_supported_operations(self) -> List[str]:
        """Get list of supported operations"""
        return ["read_file", "write_file", "list_directory"]
