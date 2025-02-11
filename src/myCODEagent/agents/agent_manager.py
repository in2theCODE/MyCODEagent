import asyncio
import os
from logging import getLogger
from typing import Any, Dict, Optional, Type

import yaml

from .base_agent import AgentConfig, BaseAgent
from .conversation_agent import ConversationAgent, ConversationAgentConfig
from .task_agent import TaskAgent, TaskAgentConfig


class AgentManager:
    """Manages different agents and their configurations"""

    def __init__(
        self, config_path: str = "config/config.yml", assistant_name: str = "aiden"
    ):
        self.config_path = config_path
        self.assistant_name = assistant_name
        self.agents: Dict[str, BaseAgent] = {}
        self.config = self._load_config()

        # Register available agent types
        self.available_agents = {
            "conversation": (ConversationAgent, ConversationAgentConfig),
            "task": (TaskAgent, TaskAgentConfig),
        }

        # Initialize configured agents
        self._initialize_agents()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path, "r") as f:
            config = yaml.safe_load(f)

        if (
            "assistants" not in config
            or self.assistant_name not in config["assistants"]
        ):
            raise ValueError(f"Assistant '{self.assistant_name}' not found in config")

        return config["assistants"][self.assistant_name]

    def _initialize_agents(self) -> None:
        """Initialize all configured agents"""
        if "agents" not in self.config:
            raise ValueError("No agents configured in config file")

        for agent_type, agent_config in self.config["agents"].items():
            if agent_type in self.available_agents:
                self.configure_agent(agent_type, agent_config)

    def get_available_agents(self) -> Dict[str, Dict[str, Any]]:
        """Get information about available agent types"""
        info = {}
        for name, (agent_class, config_class) in self.available_agents.items():
            # Create temporary agent to get capabilities
            temp_config = config_class(
                model_name="gpt-4"
            )  # Default model for capability check
            temp_agent = agent_class(temp_config)

            info[name] = {
                "description": agent_class.__doc__,
                "capabilities": temp_agent.get_capabilities(),
                "config_schema": config_class.schema(),
            }

        return info

    def configure_agent(self, agent_type: str, config: Dict[str, Any]) -> None:
        """Configure an agent with specific settings"""
        if agent_type not in self.available_agents:
            raise ValueError(f"Unknown agent type: {agent_type}")

        agent_class, config_class = self.available_agents[agent_type]

        # Validate and create config
        agent_config = config_class(**config)

        # Create agent instance
        self.agents[agent_type] = agent_class(agent_config)

        # Update configuration
        if "agents" not in self.config:
            self.config["agents"] = {}
        self.config["agents"][agent_type] = config

    async def process_request(
        self, agent_type: str, input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process a request using the specified agent"""
        if agent_type not in self.agents:
            raise ValueError(f"Agent {agent_type} not configured")

        agent = self.agents[agent_type]
        response = await agent.process(input_data)

        return response.dict()

    def get_agent_config(self, agent_type: str) -> Optional[Dict[str, Any]]:
        """Get current configuration for an agent"""
        return self.config.get("agents", {}).get(agent_type)

    def list_configured_agents(self) -> Dict[str, Dict[str, Any]]:
        """List all configured agents and their current configurations"""
        return {
            agent_type: {
                "config": self.config["agents"][agent_type],
                "capabilities": agent.get_capabilities(),
            }
            for agent_type, agent in self.agents.items()
        }

    def get_assistant_config(self) -> Dict[str, Any]:
        """Get the full assistant configuration"""
        return self.config
