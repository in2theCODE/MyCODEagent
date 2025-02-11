import datetime
import json
import os
import subprocess
import uuid
from typing import Dict, List, Union

OUTPUT_DIR = "output"


def build_file_path(name: str):
    session_dir = f"{OUTPUT_DIR}"
    os.makedirs(session_dir, exist_ok=True)
    return os.path.join(session_dir, f"{name}")


def build_file_name_session(name: str, session_id: str):
    session_dir = f"{OUTPUT_DIR}/{session_id}"
    os.makedirs(session_dir, exist_ok=True)
    return os.path.join(session_dir, f"{name}")


def to_json_file_pretty(name: str, content: Union[Dict, List]):
    def default_serializer(obj):
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        raise TypeError(
            f"Object of type {obj.__class__.__name__} is not JSON serializable"
        )

    with open(f"{name}.json", "w") as outfile:
        json.dump(content, outfile, indent=2, default=default_serializer)


def current_date_time_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def current_date_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d")


def dict_item_diff_by_set(
    previous_list: List[Dict], current_list: List[Dict], set_key: str
) -> List[str]:
    previous_set = {item[set_key] for item in previous_list}
    current_set = {item[set_key] for item in current_list}
    return list(current_set - previous_set)


def create_session_logger_id() -> str:
    return (
        datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    )


import logging
import sys


def setup_logging(session_id: str = None, debug: bool = False, name: str = "aiden"):
    """Configure logging with session-specific log file and stdout

    Args:
        session_id: Optional session ID for log file naming. If None, generates a new one
        debug: Whether to enable debug logging
        name: Name of the logger to create/get. Defaults to 'aiden'

    Returns:
        logging.Logger: Configured logger instance
    """
    # Generate session ID if not provided
    if session_id is None:
        session_id = create_session_logger_id()

    log_file = build_file_name_session("session.log", session_id)

    # Create or get the logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Clear any existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create formatter with emoji mapping
    class EmojiFormatter(logging.Formatter):
        EMOJI_MAP = {
            logging.INFO: "ℹ️",
            logging.WARNING: "⚠️",
            logging.ERROR: "❌",
            logging.CRITICAL: "🔥",
            logging.DEBUG: "🐛",
        }

        def format(self, record):
            emoji = self.EMOJI_MAP.get(record.levelno, "")
            record.emoji = emoji
            return super().format(record)

    # Create console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG if debug else logging.INFO)
    formatter = EmojiFormatter("%(emoji)s %(message)s")
    console.setFormatter(formatter)
    logger.addHandler(console)

    # Create file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)  # Always log everything to file
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    if debug:
        logger.debug(f"🔧 Debug logging enabled")
    logger.info(f"📝 Logging to {log_file}")

    return logger


def parse_markdown_backticks(str) -> str:
    if "```" not in str:
        return str.strip()
    # Remove opening backticks and language identifier
    str = str.split("```", 1)[-1].split("\n", 1)[-1]
    # Remove closing backticks
    str = str.rsplit("```", 1)[0]
    # Remove any leading or trailing whitespace
    return str.strip()


def setup_github_repo(repo_name: str, private: bool = False) -> tuple[bool, str]:
    """
    Create a new GitHub repository and set it up as a remote.

    Args:
        repo_name: Name of the repository
        private: Whether the repository should be private

    Returns:
        tuple[bool, str]: (success, message/error)
    """
    try:
        # Check for GitHub CLI
        try:
            subprocess.run(["gh", "--version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return (
                False,
                "GitHub CLI (gh) not found. Please install it first: https://cli.github.com/",
            )

        # Check if already logged in
        try:
            subprocess.run(["gh", "auth", "status"], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            return False, "Please login to GitHub CLI first using: gh auth login"

        # Create repository
        visibility = "--private" if private else "--public"
        result = subprocess.run(
            [
                "gh",
                "repo",
                "create",
                repo_name,
                visibility,
                "--source=.",
                "--remote=origin",
                "--push",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            return True, f"Repository created and pushed to GitHub: {repo_name}"
        else:
            return False, f"Failed to create repository: {result.stderr}"

    except Exception as e:
        return False, f"Error setting up GitHub repository: {str(e)}"


def run_mode(mode: str) -> None:
    """Run the application in specified mode."""
    if mode not in ["cli", "server", "daemon"]:
        raise ValueError(f"Invalid mode: {mode}")
    # Implementation details here
    pass


def write_pid(pid_file: str) -> None:
    """Write process ID to file."""
    with open(pid_file, 'w') as f:
        f.write(str(os.getpid()))


def play(audio_file: str) -> None:
    """Play an audio file."""
    # Implementation using system audio player
    pass


def seed_database() -> None:
    """Initialize the database with seed data."""
    # Implementation for seeding database
    pass


def caesar_cipher_encrypt(text: str, shift: int = 3) -> str:
    """Simple Caesar cipher encryption."""
    result = ""
    for char in text:
        if char.isalpha():
            ascii_offset = ord('A') if char.isupper() else ord('a')
            result += chr((ord(char) - ascii_offset + shift) % 26 + ascii_offset)
        else:
            result += char
    return result


def caesar_cipher_decrypt(text: str, shift: int = 3) -> str:
    """Simple Caesar cipher decryption."""
    return caesar_cipher_encrypt(text, -shift)
