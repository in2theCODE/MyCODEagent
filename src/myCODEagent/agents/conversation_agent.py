from typing import Any, Dict

import anthropic
from openai import AsyncOpenAI
from pydantic import BaseModel

from .base_agent import AgentConfig, AgentResponse, BaseAgent


class ConversationAgentConfig(AgentConfig):
    """Configuration for conversation agent"""

    system_prompt: str = "You are a helpful assistant."
    conversation_style: str = "casual"
    max_history: int = 10


class ConversationAgent(BaseAgent):
    """Agent responsible for natural conversation and command understanding"""

    def _validate_config(self) -> None:
        valid_models = {
            "gpt-4",
            "gpt-3.5-turbo",  # OpenAI models
            "claude-3-opus",
            "claude-3-sonnet",  # Anthropic models
        }
        if self.config.model_name not in valid_models:
            raise ValueError(f"Model {self.config.model_name} not supported")

    def _setup_client(self) -> None:
        if self.config.model_name.startswith("gpt"):
            self.client = AsyncOpenAI(api_key=self.config.api_key)
            self.provider = "openai"
        else:
            self.client = anthropic.AsyncAnthropic(api_key=self.config.api_key)
            self.provider = "anthropic"

    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        try:
            if self.provider == "openai":
                response = await self._process_openai(input_data)
            else:
                response = await self._process_anthropic(input_data)

            return AgentResponse(
                success=True,
                message="Successfully processed conversation",
                data={"response": response},
            )
        except Exception as e:
            return AgentResponse(
                success=False, message="Failed to process conversation", error=str(e)
            )

    async def _process_openai(self, input_data: Dict[str, Any]) -> str:
        messages = [{"role": "system", "content": self.config.system_prompt}]

        # Add conversation history
        history = input_data.get("history", [])[-self.config.max_history :]
        messages.extend(history)

        # Add current message
        messages.append({"role": "user", "content": input_data["text"]})

        response = await self.client.chat.completions.create(
            model=self.config.model_name,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

        return response.choices[0].message.content

    async def _process_anthropic(self, input_data: Dict[str, Any]) -> str:
        # Format conversation history for Claude
        history = input_data.get("history", [])[-self.config.max_history :]
        formatted_history = ""
        for msg in history:
            role_prefix = "Human: " if msg["role"] == "user" else "Assistant: "
            formatted_history += f"{role_prefix}{msg['content']}\n\n"

        # Add current message
        message = f"{formatted_history}Human: {input_data['text']}\n\nAssistant:"

        response = await self.client.chat.completions.create(
            model=self.config.model_name,
            messages=[{"role": "user", "content": message}],
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        )

        return response.content[0].text

    def _get_supported_models(self) -> Dict[str, str]:
        return {
            "gpt-4": "Most capable OpenAI model, best for complex tasks",
            "gpt-3.5-turbo": "Fast and cost-effective OpenAI model",
            "claude-3-opus": "Most capable Anthropic model",
            "claude-3-sonnet": "Balanced Anthropic model",
        }

    def _get_required_permissions(self) -> Dict[str, str]:
        return {
            "openai_api": "Required for GPT models",
            "anthropic_api": "Required for Claude models",
            "conversation_history": "Access to conversation history",
        }
