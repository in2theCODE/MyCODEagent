from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel


class AgentConfig(BaseModel):
    """Base configuration for all agents"""

    model_name: str
    temperature: float = 0.7
    max_tokens: int = 1000
    api_key: Optional[str] = None


class AgentResponse(BaseModel):
    """Standard response format for all agents"""

    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BaseAgent(ABC):
    """Base class for all agents"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self._validate_config()
        self._setup_client()

    @abstractmethod
    def _validate_config(self) -> None:
        """Validate agent-specific configuration"""
        pass

    @abstractmethod
    def _setup_client(self) -> None:
        """Set up any necessary API clients"""
        pass

    @abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Process input and return response"""
        pass

    def get_capabilities(self) -> Dict[str, str]:
        """Return agent capabilities and requirements"""
        return {
            "name": self.__class__.__name__,
            "description": self.__doc__ or "No description available",
            "supported_models": self._get_supported_models(),
            "required_permissions": self._get_required_permissions(),
        }

    @abstractmethod
    def _get_supported_models(self) -> Dict[str, str]:
        """Return dict of supported models and their descriptions"""
        pass

    @abstractmethod
    def _get_required_permissions(self) -> Dict[str, str]:
        """Return dict of required permissions and their purposes"""
        pass
