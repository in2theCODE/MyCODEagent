from typing import Any, Dict, List
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

from .base_agent import AgentConfig, AgentResponse, BaseAgent


class LocalModelAgentConfig(AgentConfig):
    """Configuration for local model agent"""
    model_path: str  # Path to the model files
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    max_new_tokens: int = 1000
    temperature: float = 0.7
    top_p: float = 0.95


class LocalModelAgent(BaseAgent):
    """Agent for running local models like R1"""

    def _validate_config(self) -> None:
        if not hasattr(self.config, "model_path"):
            raise ValueError("model_path must be specified in config")

    def _setup_client(self) -> None:
        self.tokenizer = AutoTokenizer.from_pretrained(self.config.model_path)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.config.model_path,
            torch_dtype=torch.float16 if self.config.device == "cuda" else torch.float32,
            device_map=self.config.device
        )
        self.model.eval()

    async def generate_response(self, messages: List[Dict[str, str]]) -> AgentResponse:
        try:
            # Format messages into a prompt
            formatted_prompt = self._format_messages(messages)
            
            # Tokenize
            inputs = self.tokenizer(formatted_prompt, return_tensors="pt").to(self.config.device)
            
            # Generate
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=self.config.max_new_tokens,
                    temperature=self.config.temperature,
                    top_p=self.config.top_p,
                    do_sample=True
                )
            
            # Decode response
            response_text = self.tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
            
            return AgentResponse(
                success=True,
                message=response_text,
                data={"raw_response": response_text}
            )
            
        except Exception as e:
            return AgentResponse(
                success=False,
                message="Failed to generate response",
                error=str(e)
            )

    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """Format conversation messages into a prompt string"""
        formatted = []
        
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            
            if role == "system":
                formatted.append(f"System: {content}\n")
            elif role == "user":
                formatted.append(f"User: {content}\n")
            elif role == "assistant":
                formatted.append(f"Assistant: {content}\n")
                
        return "".join(formatted)
