#!/usr/bin/env python3
import argparse
import os
import shutil
from typing import Any, Dict

import inquirer
import yaml
from colorama import Fore, Style, init

init()  # Initialize colorama


def load_yaml(file_path: str) -> Dict[str, Any]:
    """Load YAML file"""
    with open(file_path, "r") as f:
        return yaml.safe_load(f)


def save_yaml(file_path: str, data: Dict[str, Any]) -> None:
    """Save data to YAML file"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as f:
        yaml.dump(data, f, sort_keys=False, indent=2)


def get_template_path(template_name: str) -> str:
    """Get path to template file"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "aiden", "templates", f"{template_name}_config.yml")


def get_config_path() -> str:
    """Get path to main config file"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "config", "config.yml")


def prompt_assistant_details() -> Dict[str, Any]:
    """Prompt user for assistant details"""
    questions = [
        inquirer.Text(
            "name",
            message="What's your assistant's name?",
            validate=lambda _, x: len(x) >= 2,
        ),
        inquirer.Text("human_name", message="What's your name? (Press Enter to skip)"),
        inquirer.List(
            "template",
            message="Choose a template",
            choices=["base_assistant", "typer_assistant"],
        ),
        inquirer.List(
            "voice",
            message="Choose a voice type",
            choices=["local", "elevenlabs", "realtime-tts"],
        ),
        inquirer.List(
            "brain",
            message="Choose a brain model",
            choices=[
                "gpt-4",
                "gpt-3.5-turbo",
                "claude-3-opus",
                "claude-3-sonnet",
                "ollama:phi4",
            ],
        ),
    ]

    return inquirer.prompt(questions)


def customize_config(
    template_config: Dict[str, Any], details: Dict[str, Any]
) -> Dict[str, Any]:
    """Customize template config with user details"""
    config = template_config.copy()

    # Update basic settings
    config["name"] = details["name"]
    if details["human_name"]:
        config["human_companion_name"] = details["human_name"]

    # Update voice settings
    if "voice" not in config:
        config["voice"] = {}
    config["voice"]["type"] = details["voice"]

    # Update agent settings
    if "agents" not in config:
        config["agents"] = {}
    if "conversation" not in config["agents"]:
        config["agents"]["conversation"] = {}
    config["agents"]["conversation"]["model_name"] = details["brain"]

    return config


def main():
    print(f"{Fore.CYAN}🤖 Welcome to the aiden Assistant Creator!{Style.RESET_ALL}\n")

    # Get user input
    details = prompt_assistant_details()

    try:
        # Load template
        template_path = get_template_path(details["template"])
        template_config = load_yaml(template_path)

        # Load main config
        config_path = get_config_path()
        main_config = load_yaml(config_path)

        # Ensure assistants section exists
        if "assistants" not in main_config:
            main_config["assistants"] = {}

        # Check if assistant name already exists
        assistant_key = details["name"].lower().replace(" ", "_")
        if assistant_key in main_config["assistants"]:
            print(
                f"{Fore.RED}❌ An assistant with the name '{details['name']}' already exists!{Style.RESET_ALL}"
            )
            return

        # Customize config
        assistant_config = customize_config(template_config, details)

        # Add to main config
        main_config["assistants"][assistant_key] = assistant_config

        # Save config
        save_yaml(config_path, main_config)

        print(
            f"\n{Fore.GREEN}✅ Assistant '{details['name']}' created successfully!{Style.RESET_ALL}"
        )
        print(f"\nTo use your assistant, run:")
        print(
            f"{Fore.YELLOW}./aiden.sh start --assistant {assistant_key}{Style.RESET_ALL}"
        )

    except Exception as e:
        print(f"{Fore.RED}❌ Error creating assistant: {str(e)}{Style.RESET_ALL}")
        return


if __name__ == "__main__":
    main()
