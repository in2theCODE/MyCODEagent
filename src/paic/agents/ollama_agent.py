from typing import Any, Dict, List
import ollama

from .base_agent import AgentConfig, AgentResponse, BaseAgent


class OllamaAgentConfig(AgentConfig):
    """Configuration for Ollama agent"""
    model_name: str  # Name of the Ollama model (e.g. 'r1')
    temperature: float = 0.7
    context_window: int = 4096


class OllamaAgent(BaseAgent):
    """Agent for running models through Ollama"""

    def _validate_config(self) -> None:
        if not self.config.model_name:
            raise ValueError("model_name must be specified in config")

    def _setup_client(self) -> None:
        # Ollama client is stateless, no setup needed
        pass

    async def generate_response(self, messages: List[Dict[str, str]]) -> AgentResponse:
        try:
            # Format messages into a prompt
            formatted_messages = []
            for msg in messages:
                formatted_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Generate response using Ollama
            response = ollama.chat(
                model=self.config.model_name,
                messages=formatted_messages,
                options={
                    "temperature": self.config.temperature,
                }
            )
            
            return AgentResponse(
                success=True,
                message=response.message.content,
                data={"raw_response": response.message.content}
            )
            
        except Exception as e:
            return AgentResponse(
                success=False,
                message="Failed to generate response",
                error=str(e)
            )
