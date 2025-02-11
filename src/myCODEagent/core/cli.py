import asyncio
import difflib
import json
import logging
import os
import random
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import psycopg2
import typer
import yaml
from RealtimeSTT_server.stt_server import recorder
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from agents.conversation_agent import (
    ConversationAgent,
    ConversationAgentConfig,
)
from core.project_generator import SpecPromptGenerator
from commands.create_directory import setup_project_dir
from models import (
    Base,
)
from elevenlabs import ElevenLabs
from core.assistant_config import get_config
from core.base_assistant import PlainAssistant
from core.r1 import prefix_prompt
from agents.template_manager import TemplateManager
from core.voice import VoiceCommandSystem
from main import PID_FILE, Daemonize
from models import (
    Project,
    Task,
)
from utils.utils import (
    create_session_logger_id,
    setup_github_repo,
    setup_logging,
    build_file_name_session,
    run_mode,
    write_pid,
    play,
    seed_database,
    caesar_cipher_encrypt,
    caesar_cipher_decrypt,
)


# Create the Typer app
app = typer.Typer()

def get_voice_system(logger=None):
    """Get or create VoiceCommandSystem instance"""
    if not hasattr(get_voice_system, '_instance'):
        if logger is None:
            logger = setup_logging(create_session_logger_id())
        get_voice_system._instance = VoiceCommandSystem(logger)
    return get_voice_system._instance

# Initialize template manager
template_manager = TemplateManager(...)


# List of commands that require additional authorization
RESTRICTED_COMMANDS = ["delete-user", "migrate-database", "restore-data"]

def log_command_history(command: str, result: dict, user_input: str) -> None:
    """Log command execution history for auditing.
    :param command: The executed command.
    :param result: The  output of the command
    :param user_input: exec_command
    """
    with open("command_history.log", "a") as f:
        timestamp = datetime.now().isoformat()
        f.write(f"{timestamp}: {command} - Success: {result['success']}\n")


def check_voice_authorization(command_name: str) -> str:
    """Check if current user is authorized to use this command."""
    if command_name in RESTRICTED_COMMANDS:
        raise PermissionError(f"Command '{command_name}' requires additional authorization")
    return command_name


def exec_command(command_name: str, *args, **kwargs) -> dict:
    """
    Execute a command by name with optional arguments.
    Returns a dict with success status and any output/error messages.
    """
    try:
        # Get the command function from the app
        if not hasattr(app, command_name):
            return {
                "success": False,
                "error": f"Command '{command_name}' not found",
            }

        command_func = getattr(app, command_name)

        # Execute the command with any provided arguments
        result = command_func(*args, **kwargs)

        return {"success": True, "output": result}

    except Exception as e:
        return {"success": False, "error": str(e)}


def parse_voice_command(text: str) -> tuple:
    """
    Parse voice command into command name and arguments.
    Returns tuple of (command_name, args, kwargs)
    """
    # Remove filler words
    text = text.lower().replace("please", "").replace("could you", "").strip()

    # Basic command mappings
    command_mappings = {
        "show all tasks": ("list-tasks", ["--all"]),
        "list my tasks": ("list-tasks", []),
        "show config": ("show-config", []),
        "show full config": ("show-config", ["--verbose"]),
        "backup everything": ("backup-data", ["./backups", "--full"]),
        "create backup": ("backup-data", ["./backups"]),
        "list users": ("list-users", []),
        "show admins": ("list-users", ["--role", "admin"]),
        "ping server": ("ping-server", []),
    }

    # Check for exact matches first
    if text in command_mappings:
        return command_mappings[text][0], command_mappings[text][1], {}

    # Handle dynamic commands
    if "create user" in text:
        parts = text.split("with role")
        username = parts[0].replace("create user", "").strip()
        role = parts[1].strip() if len(parts) > 1 else "guest"
        return "create-user", [username], {"role": role}

    if "create task" in text:
        parts = text.split("with priority")
        task_name = parts[0].replace("create task", "").strip()
        priority = int(parts[1].strip()) if len(parts) > 1 else 1
        return "queue-task", [task_name], {"priority": priority}

    if "remove task" in text:
        task_id = text.split("remove task")[-1].strip()
        return "remove-task", [task_id], {"force": True}

    return None, [], {}


def get_available_commands() -> list:
    """Get list of all available commands for voice control."""
    commands = []
    for command in app.commands:
        commands.append(
            {
                "name": command.name,
                "help": command.help,
                "args": [param.name for param in command.params],
            }
        )
    return commands


def suggest_similar_command(text: str) -> str:
    """Suggest similar commands when voice command isn't recognized."""
    available_commands = get_available_commands()
    command_names = [cmd["name"] for cmd in available_commands]

    # Use difflib to find close matches
    from difflib import get_close_matches

    matches = get_close_matches(text.lower(), command_names, n=1)

    if matches:
        return f"Did you mean '{matches[0]}'? You can say 'yes' to execute that command."
    return "Command not recognized. Say 'help' to see available commands."


class TyperAgent:
    def __init__(
        self,
        logger: logging.Logger,
        session_id: str,
        recorder: ElevenLabs,
        user_role: str = "user",
    ):
        # Define valid roles as a class constant
        self.template_manager = template_manager.load_templates()
        self.command_patterns = []
        self.voice_shortcuts = None
        self.recorder = recorder
        self.logger = logger
        self.session_id = session_id
        self.log_file = build_file_name_session("session.log", session_id)
        self.elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVEN_API_KEY"))
        self.previous_successful_requests = []
        self.previous_responses = []
        self.pending_command = None
        self.command_history = []
        self.user_role = user_role
        self.logger.info(f"👤 User role: {self.user_role}")
        log_command_history("init", {"success": True})

    def learn_user_patterns(self, item: str, matched_command: str) -> None:
        """Learn and adapt to user's voice command patterns."""
        self.command_patterns[difflib.SequenceMatcher(None, item,
        matched_command).ratio()] = matched_command

    def register_voice_shortcut(self, phrase: str, command: str) -> None:
        """Register custom voice shortcuts for frequently used commands."""
        self.voice_shortcuts[phrase] = command

    def handle_voice_command(self, text: str) -> str:
        """Main handler for voice commands with natural language processing."""
        command_name, args, kwargs = parse_voice_command(text)

        if command_name:
            result = exec_command(command_name, *args, **kwargs)
            if result["success"]:
                self.speak(f"Command {command_name} executed successfully")
                return result["output"]
            else:
                self.speak(f"Error executing command: {result['error']}")
                return result["error"]
        else:
            suggestion = suggest_similar_command(text)
            self.speak(suggestion)
            return suggestion

    def handle_confirmation(self, text: str, pending_command: dict) -> None:
        """Handle yes/no confirmation for commands."""
        if any(word in text.lower() for word in ["yes", "yeah", "correct", "right"]):
            if pending_command:
                exec_command(
                    pending_command["command"],
                    *pending_command["args"],
                    **pending_command["kwargs"],
                )
                self.pending_command = None
        else:
            self.speak("Command cancelled")
            self.pending_command = None

    def _validate_markdown(self, file_path: str) -> bool:
        """Validate that file is markdown and has expected structure"""
        if not file_path.endswith((".md", ".markdown")):
            self.logger.error(f"📄 Scratchpad file {file_path} must be a markdown file")
            return False

        try:
            with open(file_path, "r") as f:
                content = f.read()
                # Basic validation - could be expanded based on needs
                if not content.strip():
                    self.logger.warning("📄 Markdown file is empty")
                return True
        except Exception as e:
            self.logger.error(f"📄 Error reading markdown file: {str(e)}")
            return False

    @classmethod
    def build_agent(cls, typer_file: str, scratchpad: List[str]):
        """Create and configure a new TyperAssistant instance"""
        session_id = create_session_logger_id()
        logger = setup_logging(session_id)
        logger.info(f"🚀 Starting STT session {session_id}")

        if not os.path.exists(typer_file):
            logger.error(f"📂 Typer file {typer_file} does not exist")
            raise FileNotFoundError(f"Typer file {typer_file} does not exist")

        # Validate markdown scratchpad
        agent = cls(logger, session_id = session_id)
        if scratchpad and not agent._validate_markdown(scratchpad[0]):
            raise ValueError(f"Invalid markdown scratchpad file: {scratchpad[0]}")

        return agent, typer_file, scratchpad[0]

    def build_prompt(
        self,
        typer_file: str,
        scratchpad: str,
        context_files: List[str],
        prompt_text: str,
    ) -> str:
        """Build and format the prompt template with current state"""
        try:
            # Load typer file
            self.logger.info("📂 Loading typer file...")
            with open(typer_file, "r") as f:
                typer_content = f.read()

            # Load scratchpad file
            self.logger.info("📝 Loading scratchpad file...")
            if not os.path.exists(scratchpad):
                self.logger.error(f"📄 Scratchpad file {scratchpad} does not exist")
                raise FileNotFoundError(f"Scratchpad file {scratchpad} does not exist")

            with open(scratchpad, "r") as f:
                scratchpad_content = f.read()

            # Load context files
            context_content = ""
            for file_path in context_files:
                if not os.path.exists(file_path):
                    self.logger.error(f"📄 Context file {file_path} does not exist")
                    raise FileNotFoundError(f"Context file {file_path} does not exist")

                with open(file_path, "r") as f:
                    file_content = f.read()
                    file_name = os.path.basename(file_path)
                    context_content += f'\t<context name="{file_name}">\n{file_content}\n</context>\n\n'

            # Load and format prompt template
            self.logger.info("📝 Loading prompt template...")
            with open("prompts/typer-commands.xml", "r") as f:
                prompt_template = f.read()

            # Replace template placeholders
            formatted_prompt = (
                prompt_template.replace("{{typer-commands}}", typer_content)
                .replace("{{scratch_pad}}", scratchpad_content)
                .replace("{{context_files}}", context_content)
                .replace("{{natural_language_request}}", prompt_text)
            )

            # Log the filled prompt template to file only (not stdout)
            with open(self.log_file, "a") as log:
                log.write("\n📝 Filled prompt template:\n")
                log.write(formatted_prompt)
                log.write("\n\n")

            return formatted_prompt

        except Exception as e:
            self.logger.error(f"❌ Error building prompt: {str(e)}")
            raise


    async def process_text(self, text: str) -> bool | None:
        """
        Process user speech input and map it to command functions with enhanced voice interaction.
        """
        try:
            assistant_name = get_config("typer_assistant.assistant_name")
            if assistant_name.lower() not in text.lower():
                self.speak(f"I'm {assistant_name}, but you weren't talking to me.")
                return True

            # Try processing as a command first
            voice_system = get_voice_system(self.logger)
            command_response = await voice_system.process_command(text)
            if command_response:
                self.speak(command_response)
                return True

            # Convert speech to lowercase for easier processing
            text = text.lower()

            # Exit commands
            if any(word in text for word in ["exit", "quit", "goodbye", "bye"]):
                self.speak("Goodbye! Have a great day!")
                return False

            # Handle pending confirmations first
            if self.pending_command:
                self.handle_confirmation(text, self.pending_command)
                return True

            # Stop recording while processing
            self.recorder.stop()
            try:
                # Template-based command handling for "add" commands
                if "add" in text:
                    return self.template_manager.handle_voice_add(text, self.speak, self.get_voice_input)

                # Run existing command
                elif "run" in text and "command" in text:
                    command_name = (
                        text.replace("run", "")
                        .replace("command", "")
                        .strip()
                        .replace(" ", "_")
                    )

                    if self.command_exists(command_name):
                        self.speak(f"Running {command_name} command.")
                        result = exec_command(command_name)

                        if result["success"]:
                            self.speak(f"Command {command_name} completed successfully.")
                        else:
                            self.speak(
                                f"There was an issue running the command: {result.get('error', 'Unknown error')}"
                            )
                    else:
                        self.speak(f"I couldn't find a command named {command_name}.")

                elif "help" in text or "what can you do" in text:
                    self.speak(
                        """
                        I can help you manage and run commands. Try saying:
                        - Add a new assistant, project, or command
                        - Run a specific command
                        - Or ask for help anytime
                    """
                    )

                else:
                    # Try to parse and execute as a natural language command
                    result = self.handle_voice_command(text)
                    self.logger.info(f"Command result: {result}")
                    if not result:
                        self.speak(
                            "I didn't recognize that command. Try asking for help to see what I can do."
                        )

                return True

            finally:
                # Always restart recording when done
                self.recorder.start()

        except Exception as e:
            self.logger.error(f"Error processing voice command: {str(e)}")
            self.speak(
                "I encountered an error processing your request. Please try again."
            )
            self.recorder.start()
            return True

    def get_voice_confirmation(self) -> bool:
        """Get yes/no confirmation from voice input."""
        response = self.get_voice_input().lower()
        return any(
            word in response for word in ["yes", "yeah", "sure", "okay", "confirm"]
        )

    def get_voice_input(self) -> str:
        """Get voice input from user with timeout."""
        self.recorder.start()
        response = None

        # Wait for up to 5 seconds for response
        for _ in range(50):  # 5 seconds with 0.1s sleep
            if response:
                break
            time.sleep(0.1)

        self.recorder.stop()
        return response if response else ""

    def command_exists(command_name: str, COMMANDS_FILE=None) -> bool:
        """Check if a command exists in the commands file."""
        try:
            with open(COMMANDS_FILE, "r") as f:
                content = f.read()
                return f"def {command_name}(" in content
        except Exception:
            return False

    def speak(self, param):
        pass


@app.command()
def initialize():
    """Initialize the application"""
    # Create the configuration directory if it doesn't exist
    config_dir = Path.home() / ".aiden"
    config_dir.mkdir(parents=True, exist_ok=True)

    # Create the configuration file if it doesn't exist
    config_file = config_dir / "config.yml"
    if not config_file.exists():
        with open(config_file, "w") as f:
            # Write default configuration to the file
            yaml.dump({"project_name": "My Project", "project_description": "My project description"}, f)

    # Create the project directory if it doesn't exist
    project_dir = Path.cwd() / "project"
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create the project files if they don't exist
    project_files = ["main.py", "requirements.txt", "README.md"]
    for file in project_files:
        file_path = project_dir / file
        if not file_path.exists():
            with open(file_path, "w") as f:
                # Write default content to the file
                if file == "main.py":
                    f.write("# Your Python code here")
                elif file == "requirements.txt":
                    f.write("# Your dependencies here")
                elif file == "README.md":
                    f.write("# Your project description here")

    # Initialize the project with Git
    try:
        import git
        repo = git.Repo.init(project_dir)
        repo.index.add(["*"])
        repo.index.commit("Initial commit")
    except ImportError:
        typer.echo("Git is not installed. Skipping Git initialization.")

    typer.echo("Application initialized successfully!")



# Define your Typer commands
@app.command("project")
def project(action: str):
    if action == "create":
        print("Creating project...")
        return {"status": "created"}


@app.command("create project", help="Create a new project")
def handle_create_project():
    typer.run(project)


@app.command()
def think_speak(self, text: str):
    response_prompt_base = ""
    with open("prompts/concise-assistant-response.xml", "r") as f:
        response_prompt_base = f.read()

    assistant_name = get_config("typer_assistant.assistant_name")
    human_companion_name = get_config("typer_assistant.human_companion_name")

    response_prompt = response_prompt_base.replace("{{latest_action}}", text)
    response_prompt = response_prompt.replace(
        "{{human_companion_name}}", human_companion_name
    )
    response_prompt = response_prompt.replace(
        "{{personal_ai_assistant_name}}", assistant_name
    )
    prompt_prefix = f"Your Conversational Response: "
    response = prefix_prompt(
        prompt=response_prompt, prefix=prompt_prefix, no_prefix=True
    )
    self.logger.info(f"🤖 Response: '{response}'")
    self.speak(response)


@app.command()
def tts(self, text: str):

    start_time = time.time()
    model = "eleven_flash_v2_5"
    # model="eleven_flash_v2"
    # model = "eleven_turbo_v2"
    # model = "eleven_turbo_v2_5"
    # model="eleven_multilingual_v2"
    voice = get_config("typer_assistant.elevenlabs_voice")

    audio_generator = self.elevenlabs_client.generate(
        text=text,
        voice=voice,
        model=model,
        stream=False,
    )
    audio_bytes: bytes = b"".join(list(audio_generator))
    duration = time.time() - start_time
    self.logger.info(f"Model {model} completed tts in {duration:.2f} seconds")
    start(audio_bytes)


@app.command()
def status():
    if PID_FILE.exists():
        pid = PID_FILE.read_text().strip()
        typer.echo(f"✅ aiden running (PID: {pid})")
    else:
        typer.echo("❌ aiden not running")


@app.command()
def start(
    mode: str = typer.Option("cli", "--mode", "-m"),
    daemon: bool = typer.Option(False, "--daemon", "-d"),
):
    if PID_FILE.exists():
        typer.echo("🚫 aiden is already running")
        raise typer.Exit(code=1)

    if daemon:
        daemon = Daemonize(
            app="aiden",
            pid=PID_FILE,
            action=lambda: run_mode(mode),
            chdir=str(Path.cwd()),
        )
        try:
            # First fork (detaches from parent)
            try:
                pid = os.fork()
                if pid > 0:
                    sys.exit(0)  # Parent exits
            except OSError as err:
                daemon.logger.error(f'First fork failed: {err}')
                sys.exit(1)

            # Decouple from parent environment
            os.chdir(daemon.chdir)
            os.umask(0)
            os.setsid()

            # Second fork (relinquish session leadership)
            try:
                pid = os.fork()
                if pid > 0:
                    sys.exit(0)  # Parent exits
            except OSError as err:
                daemon.logger.error(f'Second fork failed: {err}')
                sys.exit(1)

            # Flush I/O buffers and write PID file
            sys.stdout.flush()
            sys.stderr.flush()

            # Write PID file
            with open(daemon.pid_file, 'w') as f:
                f.write(str(os.getpid()))

            # Signal handlers
            signal.signal(signal.SIGTERM, daemon._cleanup)
            signal.signal(signal.SIGHUP, daemon._cleanup)

            # Execute the daemon action
            daemon.action()

        except Exception as e:
            daemon.logger.error(f'Error starting daemon: {e}')
            if daemon.pid_file.exists():
                os.unlink(daemon.pid_file)
            sys.exit(1)
    else:
        run_mode(mode)
        write_pid()


@app.command()
def ping():
    print("pong")


@app.command(help="Start a chat session with the plain assistant using speech input")
def process_text(text: str):
    """Process user speech input using ElevenLabs"""
    if not text:
        return

    if text.lower() in ["quit", "exit", "stop"]:
        return

    try:
        # Initialize ElevenLabs client
        elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVEN_API_KEY"))

        # Process the text with the assistant
        assistant = PlainAssistant()
        response = assistant.process_input(text)

        # Convert response to speech using ElevenLabs
        voice = get_config("typer_assistant.elevenlabs_voice")
        audio = elevenlabs_client.generate(
            text=response, voice=voice, model="eleven_turbo_v2"
        )

        # Play the response
        play(audio)

    except Exception as e:
        typer.echo(f"❌ Error processing text: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command()
def get_connection():
    """Connect to PostgreSQL (Supabase/Neon)"""
    try:
        conn = psycopg2.connect(os.getenv("SUPABASE_DATABASE_URL"))
        typer.echo("✅ Successfully connected to database")
        return conn
    except Exception as e:
        typer.echo(f"❌ Database connection error: {str(e)}", err=True)
        raise typer.Exit(1)


# Ensure the database is seeded before doing anything
seed_database()


# -----------------------------------------------------
# Database helpers
# -----------------------------------------------------


def get_supabase_client():
    """Attempt to connect to Supabase. If credentials are missing, notify the user."""
    try:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")

        if not supabase_url or not supabase_key:
            raise ValueError("⚠️ Missing required credentials.")

        return create_client(supabase_url, supabase_key)

    except ValueError:
        typer.echo(
            "⚠️ Your database is not configured. Run `setup-database` to fix this."
        )
        return None
    except Exception as e:
        typer.echo(f"❌ Failed to connect to Supabase: {str(e)}")
        return None


@app.command()
def validate_db():
    """Validate the database connection without exposing credentials."""
    supabase = get_supabase_client()

    if not supabase:
        return

    try:
        response = supabase.table("users").select("*").limit(1).execute()

        if response.data:
            typer.echo("✅ Supabase database connection is valid!")
        else:
            typer.echo("⚠️ Connected, but no data found.")
    except Exception as e:
        typer.echo(f"❌ Database validation failed: {str(e)}")


def get_db_connection():
    """Get a PostgreSQL database connection."""
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("SUPABASE_DATABASE", "postgres"),
            user=os.getenv("SUPABASE_USER"),
            password=os.getenv("SUPABASE_PASSWORD"),
            host=os.getenv("SUPABASE_HOST"),
            port=os.getenv("POSTGRES_PORT", "5432"),
        )
        return conn
    except Exception as e:
        typer.echo(f"❌ Database connection error: {str(e)}")
        raise


# Database setup
def get_db_session():
    """Get SQLAlchemy session for database operations"""
    try:
        DATABASE_URL = os.getenv("SUPABASE_DATABASE_URL")
        if not DATABASE_URL:
            raise ValueError("Database URL not found in environment variables")

        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        return SessionLocal()
    except Exception as e:
        typer.echo(f"❌ Database connection error: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command()
def init_db() -> None:
    """Initialize the database schema"""
    try:
        DATABASE_URL = os.getenv("SUPABASE_DATABASE_URL")
        engine = create_engine(DATABASE_URL)
        Base.metadata.create_all(bind=engine)
        typer.echo("✅ Database schema initialized successfully")
    except Exception as e:
        typer.echo(f"❌ Database initialization error: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command()
def create_project(
    name: str = typer.Argument(..., help="Project name"),
    description: str = typer.Option("", help="Project description"),
    owner_id: int = typer.Option(..., help="Project owner ID"),
    start_date: Optional[str] = typer.Option(None, help="Start date (YYYY-MM-DD)"),
    due_date: Optional[str] = typer.Option(None, help="Due date (YYYY-MM-DD)"),
) -> None:
    """Creates a new project with the specified details"""
    try:
        db = get_db_session()
        
        # Convert string dates to datetime if provided
        start_date_dt = (
            datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
        )
        due_date_dt = datetime.strptime(due_date, "%Y-%m-%d") if due_date else None

        # Create new project using SQLAlchemy model
        project = Project(
            name=name,
            description=description,
            owner_id=owner_id,
            start_date=start_date_dt,
            due_date=due_date_dt,
        )

        db.add(project)
        db.commit()
        db.refresh(project)

        typer.echo(f"✅ Project '{name}' created with ID {project.id}")
        return project.id

    except Exception as e:
        db.rollback()
        typer.echo(f"❌ Error creating project: {str(e)}", err=True)
        raise typer.Exit(1)
    finally:
        db.close()


@app.command()
def list_projects() -> None:
    """List all projects"""
    try:
        db = get_db_session()
        projects = db.query(Project).all()

        if not projects:
            typer.echo("No projects found")
            return

        for project in projects:
            typer.echo(
                f"""
Project: {project.name} (ID: {project.id})
  Description: {project.description}
  Owner ID: {project.owner_id}
  Start Date: {project.start_date}
  Due Date: {project.due_date}
  Created At: {project.created_at}
"""
            )
    except Exception as e:
        typer.echo(f"❌ Error listing projects: {str(e)}", err=True)
        raise typer.Exit(1)
    finally:
        db.close()


@app.command()
def create_task(
    task_name: str = typer.Argument(..., help="Task name"),
    description: str = typer.Option("", help="Task description"),
    priority: int = typer.Option(1, help="Task priority (1-5)"),
    project_id: Optional[int] = typer.Option(None, help="Project ID to assign to"),
    assigned_to: Optional[int] = typer.Option(None, help="Assign task to user ID"),
    due_date: Optional[str] = typer.Option(None, help="Due date (YYYY-MM-DD)"),
):
    """Creates a new task with optional project and user assignment."""
    try:
        db = get_db_session()
        
        task_data = {
            "task_name": task_name,
            "description": description,
            "priority": priority,
            "assigned_to": assigned_to,
        }
        
        if due_date:
            task_data["due_date"] = datetime.strptime(due_date, "%Y-%m-%d")
            
        task = Task.create(db, **task_data)
        
        if project_id:
            project = Project.get_by_id(db, project_id)
            if not project:
                typer.echo(f"❌ Project with ID {project_id} not found")
                return
            project.tasks.append(task)
            db.commit()
        
        typer.echo(f"✅ Task '{task_name}' created successfully with ID {task.id}")
        
    except Exception as e:
        typer.echo(f"❌ Error creating task: {str(e)}")
        raise typer.Exit(1)


@app.command()
def list_tasks(
    status: Optional[str] = typer.Option(None, help="Filter by status (pending, in-progress, complete)"),
    project_id: Optional[int] = typer.Option(None, help="Filter by project ID"),
    assigned_to: Optional[int] = typer.Option(None, help="Filter by assigned user ID"),
    sort_by: str = typer.Option("priority", help="Sort by field (priority, due_date, created_at)"),
):
    """List tasks with optional filters and sorting."""
    try:
        db = get_db_session()
        query = db.query(Task)
        
        if status:
            query = query.filter(Task.status == status)
        if project_id:
            query = query.join(Task.projects).filter(Project.id == project_id)
        if assigned_to:
            query = query.filter(Task.assigned_to == assigned_to)
            
        if sort_by == "priority":
            query = query.order_by(Task.priority.desc())
        elif sort_by == "due_date":
            query = query.order_by(Task.due_date)
        elif sort_by == "created_at":
            query = query.order_by(Task.created_at)
            
        tasks = query.all()
        
        if not tasks:
            typer.echo("No tasks found matching the criteria")
            return
            
        for task in tasks:
            status_emoji = "🔄" if task.status == "in-progress" else "✅" if task.status == "complete" else "⏳"
            due_date = task.due_date.strftime("%Y-%m-%d") if task.due_date else "No due date"
            typer.echo(f"{status_emoji} [{task.id}] {task.task_name} (Priority: {task.priority}) - Due: {due_date}")
            if task.description:
                typer.echo(f"   Description: {task.description}")
            if task.assigned_to:
                typer.echo(f"   Assigned to: User {task.assigned_to}")
            typer.echo("---")
            
    except Exception as e:
        typer.echo(f"❌ Error listing tasks: {str(e)}")
        raise typer.Exit(1)


# -----------------------------------------------------
# 1) ping_server
# -----------------------------------------------------
@app.command()
def ping_server(
    wait: bool = typer.Option(False, "--wait", help="Wait for server response?")
):
    """
    Pings the server, optionally waiting for a response.
    """
    # Mock a server response time
    response_time_ms = random.randint(50, 300)
    result = f"Server pinged. Response time: {response_time_ms} ms."
    if wait:
        result += " (Waited for a response.)"
    typer.echo(result)
    return result


# -----------------------------------------------------
# 2) show_config
# -----------------------------------------------------
@app.command()
def show_config(
    verbose: bool = typer.Option(False, "--verbose", help="Show config in detail?")
):
    """
    Shows the current configuration from modules/assistant_config.py.
    """
    try:

        config = ""

        with open("../assistant_config.yml", "r") as f:
            config = f.read()

        if verbose:
            result = f"Verbose config:\n{json.dumps(yaml.safe_load(config), indent=2)}"
        else:
            result = f"Config: {config}"
        typer.echo(result)
        return result
    except ImportError:
        result = "Error: Could not load assistant_config module"
        typer.echo(result)
        return result


# -----------------------------------------------------
# 3) list_files
# -----------------------------------------------------
@app.command()
def list_files(
    path: str = typer.Argument(..., help="Path to list files from"),
    all_files: bool = typer.Option(False, "--all", help="Include hidden files"),
):
    """
    Lists files in a directory. Optionally show hidden files.
    """
    if not os.path.isdir(path):
        msg = f"Path '{path}' is not a valid directory."
        typer.echo(msg)
        return msg

    entries = os.listdir(path)
    if not all_files:
        entries = [e for e in entries if not e.startswith(".")]

    result = f"Files in '{path}': {entries}"
    typer.echo(result)
    return result


# -----------------------------------------------------
# 3.5) list_users
# -----------------------------------------------------
@app.command()
def list_users(
    role: str = typer.Option(None, "--role", help="Filter users by role"),
    sort: str = typer.Option(
        "username", "--sort", help="Sort by field (username, role, created_at)"
    ),
):
    """
    Lists all users, optionally filtered by role and sorted by specified field.
    """
    conn = get_connection()
    cur = conn.cursor()

    query = "SELECT username, role, created_at FROM users"
    params = []

    if role:
        query += " WHERE role = %s"
        params.append(role)

    query += f" ORDER BY {sort}"

    cur.execute(query, params)
    users = cur.fetchall()
    conn.close()

    if not users:
        result = "No users found."
        typer.echo(result)
        return result

    # Format output
    result = "Users:\n"
    for user in users:
        result += f"- {user[0]} (Role: {user[1]}, Created: {user[2]})\n"

    typer.echo(result)
    return result


# -----------------------------------------------------
# 4) create_user
# -----------------------------------------------------
@app.command()
def create_user(
    username: str = typer.Argument(..., help="Name of the new user"),
    role: str = typer.Option("guest", "--role", help="Role for the new user"),
):
    """
    Creates a new user with an optional role.
    """
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().isoformat()
    cur.execute(
        "INSERT INTO users (username, role, created_at) VALUES (%s, %s, %s)",
        (username, role, now),
    )
    conn.commit()
    conn.close()
    result = f"User '{username}' created with role '{role}'."
    typer.echo(result)
    return result


# -----------------------------------------------------
# 5) delete_user
# -----------------------------------------------------
@app.command()
def delete_user(
    user_id: str = typer.Argument(..., help="ID of user to delete"),
    confirm: bool = typer.Option(False, "--confirm", help="Skip confirmation prompt"),
):
    """
    Deletes a user by ID.
    """
    if not confirm:
        # In a real scenario, you'd prompt or handle differently
        typer.echo(f"Confirmation needed to delete user {user_id}. Use --confirm.")
        return f"Deletion of user {user_id} not confirmed."

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    changes = cur.rowcount
    conn.close()

    if changes > 0:
        msg = f"User with ID {user_id} deleted."
    else:
        msg = f"No user found with ID {user_id}."
    typer.echo(msg)
    return msg


# -----------------------------------------------------
# 6) generate_report
# -----------------------------------------------------
@app.command()
def generate_report(
    table_name: str = typer.Argument(..., help="Name of table to generate report from"),
    output_file: str = typer.Option("report.json", "--output", help="Output file name"),
):
    """
    Generates a report from an existing database table and saves it to a file.
    """
    conn = get_connection()
    cur = conn.cursor()

    # Get all data from the specified table
    cur.execute(f"SELECT * FROM {table_name}")
    rows = cur.fetchall()

    # Get column names from cursor description
    columns = [description[0] for description in cur.description]

    # Convert rows to list of dicts with column names
    data = []
    for row in rows:
        data.append(dict(zip(columns, row)))

    report_data = {
        "table": table_name,
        "timestamp": datetime.now().isoformat(),
        "columns": columns,
        "row_count": len(rows),
        "data": data,
    }

    with open(output_file, "w") as f:
        json.dump(report_data, f, indent=2)

    conn.close()

    result = f"Report for table '{table_name}' generated and saved to {output_file}."
    typer.echo(result)
    typer.echo(json.dumps(report_data, indent=2))
    return report_data


# -----------------------------------------------------
# 7) backup_data
# -----------------------------------------------------
@app.command()
def backup_data(
    directory: str = typer.Argument(..., help="Directory to store backups"),
    full: bool = typer.Option(False, "--full", help="Perform a full backup"),
    DB_NAME="database.db",
):
    """
    Back up data to a specified directory, optionally performing a full backup.
    """
    if not os.path.isdir(directory):
        os.makedirs(directory)

    backup_file = os.path.join(
        directory, f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )
    shutil.copy(DB_NAME, backup_file)

    result = (
        f"{'Full' if full else 'Partial'} backup completed. Saved to {backup_file}."
    )
    typer.echo(result)
    return result


# -----------------------------------------------------
# 8) restore_data
# -----------------------------------------------------
@app.command()
def restore_data(
    file_path: str = typer.Argument(..., help="File path of backup to restore"),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Overwrite existing data"
    ),
):
    """
    Restores data from a backup file.
    """
    if not os.path.isfile(file_path):
        msg = f"Backup file {file_path} does not exist."
        typer.echo(msg)
        return msg

    if not overwrite:
        msg = "Overwrite not confirmed. Use --overwrite to proceed."
        typer.echo(msg)
        return msg

    shutil.copy(file_path, "database.db")
    msg = f"Data restored from {file_path} to database.db."
    typer.echo(msg)
    return msg


# -----------------------------------------------------
# 9) summarize_logs
# -----------------------------------------------------
@app.command()
def summarize_logs(
    logs_path: str = typer.Argument(..., help="Path to log files"),
    lines: int = typer.Option(100, "--lines", help="Number of lines to summarize"),
):
    """
    Summarizes log data from a specified path, limiting lines.
    """
    if not os.path.isfile(logs_path):
        msg = f"Log file {logs_path} not found."
        typer.echo(msg)
        return msg

    with open(logs_path, "r") as f:
        all_lines = f.readlines()

    snippet = all_lines[:lines]
    result = f"Showing first {lines} lines from {logs_path}:\n" + "".join(snippet)
    typer.echo(result)
    return result


# -----------------------------------------------------
# 10) upload_file
# -----------------------------------------------------
@app.command()
def upload_file(
    file_path: str = typer.Argument(..., help="Path of file to upload"),
    destination: str = typer.Option(
        "remote", "--destination", help="Destination label"
    ),
    secure: bool = typer.Option(True, "--secure", help="Use secure upload"),
):
    """
    Uploads a file to a destination, optionally enforcing secure upload.
    """
    if not os.path.isfile(file_path):
        msg = f"File {file_path} not found."
        typer.echo(msg)
        return msg

    # Mock upload
    result = f"File '{file_path}' uploaded to '{destination}' using {'secure' if secure else 'insecure'} mode."
    typer.echo(result)
    return result


# -----------------------------------------------------
# 11) download_file
# -----------------------------------------------------
@app.command()
def download_file(
    url: str = typer.Argument(..., help="URL of file to download"),
    output_path: str = typer.Option(".", "--output", help="Local output path"),
    retry: int = typer.Option(3, "--retry", help="Number of times to retry"),
):
    """
    Downloads a file from a URL with a specified number of retries.
    """
    # In real scenario, you'd do requests, etc. We'll just mock it.
    filename = os.path.join(output_path, os.path.basename(url))
    with open(filename, "w") as f:
        f.write("Downloaded data from " + url)

    result = f"File downloaded from {url} to {filename} with {retry} retries allowed."
    typer.echo(result)
    return result


# -----------------------------------------------------
# 12) filter_records
# -----------------------------------------------------
@app.command()
def filter_records(
    source: str = typer.Argument(..., help="Data source to filter"),
    query: str = typer.Option("", "--query", help="Filtering query string"),
    limit: int = typer.Option(10, "--limit", help="Limit the number of results"),
):
    """
    Filters records from a data source using a query, limiting the number of results.
    Example usage: filter_records table_name --query "admin" --limit 5
    """
    conn = get_connection()
    cur = conn.cursor()

    # For demonstration, we'll assume the 'source' is a table name in the DB
    # and the 'query' is a substring to match against username or message, etc.
    # This is just a simple example.
    try:
        sql = f"SELECT * FROM {source} WHERE "
        if source == "users":
            sql += "username ILIKE %s"
        elif source == "logs":
            sql += "message ILIKE %s"
        elif source == "tasks":
            sql += "task_name ILIKE %s"
        else:
            typer.echo(f"Unknown table: {source}")
            return f"Table '{source}' not recognized."

        sql += f" LIMIT {limit}"

        wildcard_query = f"%{query}%"
        cur.execute(sql, (wildcard_query,))
        rows = cur.fetchall()

        result = (
            f"Found {len(rows)} records in '{source}' with query '{query}'.\n{rows}"
        )
        typer.echo(result)
        return result

    except psycopg2.Error as e:
        msg = f"Database error: {e}"
        typer.echo(msg)
        return msg
    finally:
        conn.close()


# -----------------------------------------------------
# 16) compare_files
# -----------------------------------------------------
@app.command()
def compare_files(
    file_a: str = typer.Argument(..., help="First file to compare"),
    file_b: str = typer.Argument(..., help="Second file to compare"),
    diff_only: bool = typer.Option(
        False, "--diff-only", help="Show only the differences"
    ),
):
    """
    Compares two files, optionally showing only differences.
    """
    if not os.path.isfile(file_a) or not os.path.isfile(file_b):
        msg = f"One or both files do not exist: {file_a}, {file_b}"
        typer.echo(msg)
        return msg

    with open(file_a, "r") as fa, open(file_b, "r") as fb:
        lines_a = fa.readlines()
        lines_b = fb.readlines()

    diff = difflib.unified_diff(lines_a, lines_b, fromfile=file_a, tofile=file_b)

    if diff_only:
        # Show only differences
        differences = []
        for line in diff:
            if line.startswith("+") or line.startswith("-"):
                differences.append(line)
        result = "\n".join(differences)
    else:
        # Show entire unified diff
        result = "".join(diff)

    typer.echo(result if result.strip() else "Files are identical.")
    return result


# -----------------------------------------------------
# 17) encrypt_data
# -----------------------------------------------------
@app.command()
def encrypt_data(
    input_path: str = typer.Argument(..., help="Path of the file to encrypt"),
    output_path: str = typer.Option("encrypted.bin", "--output", help="Output file"),
    algorithm: str = typer.Option("AES", "--algorithm", help="Encryption algorithm"),
):
    """
    Encrypts data using a specified algorithm (mocked by Caesar cipher here).
    """
    if not os.path.isfile(input_path):
        msg = f"File {input_path} not found."
        typer.echo(msg)
        return msg

    with open(input_path, "r") as f:
        data = f.read()

    # We'll just mock the encryption using Caesar cipher
    encrypted = caesar_cipher_encrypt(data, 3)

    with open(output_path, "w") as f:
        f.write(encrypted)

    result = f"Data from {input_path} encrypted with {algorithm} (mock) and saved to {output_path}."
    typer.echo(result)
    return result


# -----------------------------------------------------
# 18) decrypt_data
# -----------------------------------------------------
@app.command()
def decrypt_data(
    encrypted_file: str = typer.Argument(..., help="Path to encrypted file"),
    key: str = typer.Option(..., "--key", help="Decryption key"),
    output_path: str = typer.Option("decrypted.txt", "--output", help="Output file"),
):
    """
    Decrypts an encrypted file using a key (ignored in this mock Caesar cipher).
    """
    if not os.path.isfile(encrypted_file):
        msg = f"Encrypted file {encrypted_file} not found."
        typer.echo(msg)
        return msg

    with open(encrypted_file, "r") as f:
        encrypted_data = f.read()

    # Key is ignored in this Caesar cipher demo
    decrypted = caesar_cipher_decrypt(encrypted_data, 3)

    with open(output_path, "w") as f:
        f.write(decrypted)

    result = f"Data from {encrypted_file} decrypted and saved to {output_path}."
    typer.echo(result)
    return result


# -----------------------------------------------------
# 21) migrate_database
# -----------------------------------------------------
@app.command()
def migrate_database(
    old_db: str = typer.Argument(..., help="Path to old database"),
    new_db: str = typer.Option(..., "--new-db", help="Path to new database"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Perform a trial run without changing data"
    ),
):
    """
    Migrates data from an old database to a new one, optionally doing a dry run.
    """
    if not os.path.isfile(old_db):
        msg = f"Old database '{old_db}' not found."
        typer.echo(msg)
        return msg

    if dry_run:
        result = f"Dry run: would migrate {old_db} to {new_db}."
        typer.echo(result)
        return result

    shutil.copy(old_db, new_db)
    result = f"Database migrated from {old_db} to {new_db}."
    typer.echo(result)
    return result


# -----------------------------------------------------
# 27) queue_task
# -----------------------------------------------------
@app.command()
def queue_task(
    task_name: str = typer.Argument(..., help="Name of the task to queue"),
    priority: int = typer.Option(1, help="Priority of the task (1-5)"),
    delay: int = typer.Option(0, help="Delay in seconds before starting task"),
):
    """Queues a task with a specified priority and optional delay."""
    try:
        db = get_db_session()
        
        task = Task(
            task_name=task_name,
            priority=priority,
            status="pending"
        )
        
        db.add(task)
        db.commit()
        
        if delay > 0:
            typer.echo(f"⏰ Task will start in {delay} seconds")
            time.sleep(delay)
            
        typer.echo(f"✅ Task '{task_name}' queued successfully with ID {task.id}")
        return task.id
        
    except Exception as e:
        typer.echo(f"❌ Error queueing task: {str(e)}")
        raise typer.Exit(1)


@app.command("list tasks")
def handle_list_tasks():
    typer.invoke("task list")


# -----------------------------------------------------
# 28) remove_task
# -----------------------------------------------------
@app.command()
def remove_task(
    task_id: int = typer.Argument(..., help="ID of the task to remove"),
    force: bool = typer.Option(False, "--force", help="Remove without confirmation"),
):
    """Removes a queued task by ID."""
    if not force:
        typer.echo(f"Confirmation required to remove task {task_id}. Use --force.")
        return

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
    conn.commit()
    removed = cur.rowcount
    conn.close()

    if removed:
        typer.echo(f"✅ Task {task_id} removed.")
    else:
        typer.echo(f"⚠️ Task {task_id} not found.")


# -----------------------------------------------------
# 29) list_tasks
# -----------------------------------------------------
@app.command()
def list_tasks(
    show_all: bool = typer.Option(
        False, "--all", help="Show all tasks, including completed"
    ),
    sort_by: str = typer.Option(
        "priority", "--sort-by", help="Sort tasks by this field"
    ),
):
    """Lists tasks, optionally including completed tasks or sorting by a different field."""

    valid_sort_fields = ["priority", "status", "created_at"]
    if sort_by not in valid_sort_fields:
        typer.echo(f"⚠️ Invalid sort field. Must be one of {valid_sort_fields}.")
        return

    conn = get_connection()
    cur = conn.cursor()
    if show_all:
        sql = f"SELECT id, task_name, priority, status, created_at FROM tasks ORDER BY {sort_by} ASC"
    else:
        sql = f"SELECT id, task_name, priority, status, created_at FROM tasks WHERE status != 'complete' ORDER BY {sort_by} ASC"

    cur.execute(sql)
    tasks = cur.fetchall()
    conn.close()

    if not tasks:
        typer.echo("⚠️ No tasks found.")
        return

    result = "📌 Tasks:\n"
    for t in tasks:
        result += f"🆔 ID={t[0]}, 📌 Name={t[1]}, 🔥 Priority={t[2]}, ✅ Status={t[3]}, 🕒 Created={t[4]}\n"

    typer.echo(result.strip())
    return result


@app.command()
def inspect_task(
    task_id: int = typer.Argument(..., help="ID of the task to inspect"),
    json_output: bool = typer.Option(
        False, "--json", help="Show output in JSON format"
    ),
):
    """Inspects a specific task by ID, optionally in JSON format."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, task_name, priority, status, created_at FROM tasks WHERE id = %s",
        (task_id,),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        typer.echo(f"⚠️ No task found with ID {task_id}.")
        return

    task_dict = {
        "id": row[0],
        "task_name": row[1],
        "priority": row[2],
        "status": row[3],
        "created_at": row[4],
    }

    if json_output:
        result = json.dumps(task_dict, indent=2)
    else:
        result = f"🆔 Task ID={task_dict['id']}, 📌 Name={task_dict['task_name']}, 🔥 Priority={task_dict['priority']}, ✅ Status={task_dict['status']}, 🕒 Created={task_dict['created_at']}"
    typer.echo(result)
    return result


@app.command()
def create_goal(
    title: str = typer.Argument(..., help="Goal title"),
    description: str = typer.Option("", help="Goal description"),
    category: str = typer.Option("personal", help="Goal category"),
    target_date: str = typer.Option(None, help="Target date (YYYY-MM-DD)"),
    project_id: Optional[int] = typer.Option(None, help="Associated project ID"),
):
    """Creates a new goal with optional project association."""
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().isoformat()

    cur.execute(
        """
    INSERT INTO goals (title, description, category, target_date, project_id, created_at)
    VALUES (%s, %s, %s, %s, %s, %s)
    RETURNING id
    """,
        (title, description, category, target_date, project_id, now),
    )

    goal_id = cur.fetchone()[0]
    conn.commit()
    conn.close()

    result = f"🎯 Goal '{title}' created with ID {goal_id}."
    typer.echo(result)
    return result


@app.command()
def create_event(
    title: str = typer.Argument(..., help="Event title"),
    start_time: str = typer.Argument(..., help="Start time (YYYY-MM-DD HH:MM)"),
    end_time: Optional[str] = typer.Option(None, help="End time (YYYY-MM-DD HH:MM)"),
    description: str = typer.Option("", help="Event description"),
    location: str = typer.Option("", help="Event location"),
    event_type: str = typer.Option("meeting", help="Type of event"),
    project_id: Optional[int] = typer.Option(None, help="Associated project ID"),
    recurring: str = typer.Option(
        None, help="Recurring pattern (daily/weekly/monthly)"
    ),
):
    """Creates a new calendar event."""
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().isoformat()

    cur.execute(
        """
    INSERT INTO calendar_events (
        title, start_time, end_time, description, location, 
        event_type, project_id, recurring, created_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            title,
            start_time,
            end_time,
            description,
            location,
            event_type,
            project_id,
            recurring,
            now,
        ),
    )

    event_id = cur.lastrowid
    conn.commit()
    conn.close()
    return f"Event '{title}' created with ID {event_id}"


@app.command()
def add_task_dependency(
    task_id: int = typer.Argument(..., help="Task ID"),
    dependent_on_id: int = typer.Argument(..., help="ID of task this depends on"),
):
    """Adds a dependency relationship between two tasks."""
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().isoformat()

    # Verify both tasks exist
    cur.execute("SELECT id FROM tasks WHERE id IN (%s, %s)", (task_id, dependent_on_id))
    if len(cur.fetchall()) != 2:
        conn.close()
        return "One or both tasks not found"

    cur.execute(
        """
    INSERT INTO task_dependencies (task_id, dependent_on_id, created_at)
    VALUES (%s, %s, %s)
    """,
        (task_id, dependent_on_id, now),
    )

    conn.commit()
    conn.close()
    return f"Dependency added: Task {task_id} now depends on Task {dependent_on_id}"


@app.command()
def list_project_tasks(
    project_id: int = typer.Argument(..., help="Project ID"),
    status: Optional[str] = typer.Option(None, help="Filter by task status"),
):
    """Lists all tasks associated with a project."""
    try:
        db = get_db_session()
        
        project = Project.get_by_id(db, project_id)
        if not project:
            typer.echo(f"❌ Project with ID {project_id} not found")
            return
            
        tasks = project.tasks
        if status:
            tasks = [task for task in tasks if task.status == status]
            
        if not tasks:
            typer.echo(f"No tasks found for project '{project.name}'")
            return
            
        typer.echo(f"\n📋 Tasks for project '{project.name}':")
        for task in tasks:
            status_emoji = "🔄" if task.status == "in-progress" else "✅" if task.status == "complete" else "⏳"
            due_date = task.due_date.strftime("%Y-%m-%d") if task.due_date else "No due date"
            typer.echo(f"{status_emoji} [{task.id}] {task.task_name} (Priority: {task.priority}) - Due: {due_date}")
            if task.description:
                typer.echo(f"   Description: {task.description}")
            if task.assigned_to:
                typer.echo(f"   Assigned to: User {task.assigned_to}")
            typer.echo("---")
            
    except Exception as e:
        typer.echo(f"❌ Error listing project tasks: {str(e)}")
        raise typer.Exit(1)


# -----------------------------------------------------
# Task Management Commands
# -----------------------------------------------------


@app.command()
def create_task(
    name: str = typer.Argument(..., help="Task name"),
    description: str = typer.Option("", help="Task description"),
    priority: int = typer.Option(1, help="Task priority (1-5)"),
    user_id: Optional[int] = typer.Option(None, help="Assign task to user ID"),
):
    """Create a new task."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO tasks (task_name, description, priority, status, user_id)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """,
            (name, description, priority, "pending", user_id),
        )

        task_id = cur.fetchone()[0]
        conn.commit()
        typer.echo(f"✅ Task '{name}' created with ID {task_id}")
        return task_id
    except Exception as e:
        typer.echo(f"❌ Failed to create task: {str(e)}")
    finally:
        cur.close()
        conn.close()


@app.command()
def list_tasks(
    status: str = typer.Option(
        None, help="Filter by status (pending, in-progress, complete)"
    ),
    user_id: int = typer.Option(None, help="Filter by assigned user"),
):
    """List all tasks with optional filters."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        query = """
            SELECT t.id, t.task_name, t.description, t.priority, t.status, 
                   t.created_at, u.username as assigned_to
            FROM tasks t
            LEFT JOIN users u ON t.user_id = u.id
            WHERE 1=1
        """
        params = []

        if status:
            query += " AND t.status = %s"
            params.append(status)

        if user_id:
            query += " AND t.user_id = %s"
            params.append(user_id)

        cur.execute(query, params)
        tasks = cur.fetchall()

        if not tasks:
            typer.echo("No tasks found.")
            return

        for task in tasks:
            typer.echo(f"📋 Task #{task[0]}: {task[1]}")
            typer.echo(f"  Description: {task[2]}")
            typer.echo(f"  Priority: {task[3]}")
            typer.echo(f"  Status: {task[4]}")
            typer.echo(f"  Created: {task[5]}")
            typer.echo(f"  Assigned to: {task[6] or 'Unassigned'}")
            typer.echo("---")
    except Exception as e:
        typer.echo(f"❌ Failed to list tasks: {str(e)}")
    finally:
        cur.close()
        conn.close()


@app.command()
def assign_task(
    task_id: int = typer.Argument(..., help="Task ID to assign"),
    project_id: int = typer.Argument(..., help="Project ID to assign to"),
):
    """Assign a task to a project."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO project_tasks (project_id, task_id)
            VALUES (%s, %s)
        """,
            (project_id, task_id),
        )

        conn.commit()
        typer.echo(f"✅ Task {task_id} assigned to project {project_id}")
    except Exception as e:
        typer.echo(f"❌ Failed to assign task: {str(e)}")
    finally:
        cur.close()
        conn.close()


# -----------------------------------------------------
# Project Management Commands
# -----------------------------------------------------


@app.command()
def list_projects(
    status: str = typer.Option(None, help="Filter by status (active, completed, etc)"),
    owner_id: int = typer.Option(None, help="Filter by owner ID"),
):
    """List all projects with optional filters."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        query = """
            SELECT p.id, p.name, p.description, p.status, p.priority,
                   p.start_date, p.due_date, p.completed_date,
                   u.username as owner
            FROM projects p
            LEFT JOIN users u ON p.owner_id = u.id
            WHERE 1=1
        """
        params = []

        if status:
            query += " AND p.status = %s"
            params.append(status)

        if owner_id:
            query += " AND p.owner_id = %s"
            params.append(owner_id)

        cur.execute(query, params)
        projects = cur.fetchall()

        if not projects:
            typer.echo("No projects found.")
            return

        for project in projects:
            typer.echo(
                f"""
Project: {project[0]} - {project[1]}
  Description: {project[2]}
  Status: {project[3]}
  Priority: {project[4]}
  Start Date: {project[5]}
  Due Date: {project[6]}
  Completed Date: {project[7]}
  Owner: {project[8]}
"""
            )
    except Exception as e:
        typer.echo(f"❌ Failed to list projects: {str(e)}")
    finally:
        cur.close()
        conn.close()


@app.command()
def assign_project(
    project_id: int = typer.Argument(..., help="Project ID to assign"),
    user_id: int = typer.Argument(..., help="User ID to assign as owner"),
):
    """Assign a project to a new owner."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE projects
            SET owner_id = %s
            WHERE id = %s
        """,
            (user_id, project_id),
        )

        conn.commit()
        typer.echo(f"✅ Project {project_id} assigned to user {user_id}")
    except Exception as e:
        typer.echo(f"❌ Failed to assign project: {str(e)}")
    finally:
        cur.close()
        conn.close()


@app.command()
def add_tag(
    name: str = typer.Argument(..., help="Tag name"),
    item_id: int = typer.Argument(..., help="ID of item to tag"),
    item_type: str = typer.Argument(..., help="Type of item (project/goal/task/event)"),
):
    """Adds a tag to a project, goal, task, or event."""
    conn = get_db_connection()
    cur = conn.cursor()
    now = datetime.now().isoformat()

    # Create tag if it doesn't exist
    cur.execute(
        """
    INSERT INTO tags (name, created_at) ON CONFLICT DO NOTHING RETURNING id; INSERT
    VALUES (%s, %s)
    """,
        (name, now),
    )

    # Get tag ID
    cur.execute("SELECT id FROM tags WHERE name = %s", (name,))
    tag_id = cur.fetchone()[0]

    # Create association
    cur.execute(
        """
    INSERT INTO tag_associations (tag_id, item_id, item_type, created_at)
    VALUES (%s, %s, %s, %s)
    """,
        (tag_id, item_id, item_type, now),
    )

    conn.commit()
    conn.close()
    return f"Tag '{name}' added to {item_type} {item_id}"


@app.command()
def awaken(
    model: str = typer.Option(
        "gpt-4",
        "--model",
        "-m",
        help=(
            "Model to use: gpt-4, gpt-3.5-turbo, "
            "claude-3-opus, claude-3-sonnet"
        )
    ),
    voice_type: str = typer.Option(
        "elevenlabs",
        "--voice-type",
        "-v",
        help="Voice type to use: local, realtime-tts, or elevenlabs"
    ),
    elevenlabs_voice: str = typer.Option(
        None, "--elevenlabs-voice", help="ElevenLabs voice ID (only for elevenlabs voice type)"
    ),
    brain: str = typer.Option(
        "ollama:dolphin-mixtral",
        "--brain",
        "-b",
        help="Brain to use: ollama:<model> or deepseek"
    ),
    system_prompt: str = typer.Option(
        None, "--system-prompt", "-s", help="System prompt for the conversation agent"
    ),
    conversation_style: str = typer.Option(
        "casual",
        "--style",
        help="Conversation style: casual, professional, or technical"
    ),
    interruption_with_keyboard=None
):
    """Start an enhanced voice interface with advanced conversation capabilities"""
    try:
        # Initialize logging
        session_id = create_session_logger_id()
        logger = setup_logging(session_id)
        logger.info(f"🚀 Starting enhanced voice session {session_id}")

        # Set up voice configuration
        if voice_type == "elevenlabs" and elevenlabs_voice:
            os.environ["ELEVEN_VOICE"] = elevenlabs_voice

        # Initialize the base assistant
        assistant = PlainAssistant(logger, session_id)

        # Configure the conversation agent
        agent_config = ConversationAgentConfig(
            model_name=model,
            system_prompt=system_prompt or "You are a helpful AI assistant.",
            conversation_style=conversation_style,
            max_history=10,
        )
        conversation_agent = ConversationAgent(agent_config)
        
        typer.echo(f"🎤 Voice interface activated with:")
        typer.echo(f"   - Model: {model}")
        typer.echo(f"   - Voice: {voice_type}")
        typer.echo(f"   - Brain: {brain}")
        typer.echo("\nTry saying 'Hey Aiden, what can you do?' to get started")
        typer.echo("Press Ctrl+C to exit")

        def process_voice(text: str):
            try:
                # Process through both assistants
                base_response = assistant.process_text(text)
                agent_response = asyncio.run(
                    conversation_agent.process(
                        {"text": text, "history": assistant.conversation_history}
                    )
                )

                if agent_response.success:
                    return agent_response.data["response"]
                return base_response

            except Exception as e:
                logger.error(f"Error processing voice: {str(e)}")
                return f"I encountered an error: {str(e)}"

        while True:
            try:
                recorder.text(process_voice)
            except interruption_with_keyboard:
                typer.echo("\n👋 Shutting down voice interface...")
                assistant.save_conversation()
                break
            except Exception as e:
                typer.echo(f"Error in voice loop: {str(e)}")
                continue

    except Exception as e:
        typer.echo(f"❌ Error initializing voice interface: {str(e)}")
        raise typer.Exit(1)


# -----------------------------------------------------
# Code Generation Commands
# -----------------------------------------------------


@app.command()
def run_director(
    config_path: str = typer.Argument(
        ..., help="Path to the director config YAML file"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
):
    """Run the AI Coding Director with a specified config file."""
    try:
        from core.director import Director

        director = Director(config_path)

        if verbose:
            typer.echo(f"Loaded config from {config_path}")
            typer.echo("Starting code generation...")

        director.run()
        typer.echo("✅ Code generation completed successfully!")

    except Exception as e:
        typer.echo(f"❌ Failed to run director: {str(e)}")


@app.command()
def create_director_config(
    output_path: str = typer.Argument(
        ..., help="Path to save the config file"
    ),
    prompt: str = typer.Option(
        ..., help="Prompt or path to .md file with prompt"
    ),
    coder_model: str = typer.Option(
        "gpt-4", help="Model to use for coding"
    ),
    evaluator_model: str = typer.Option(
        "gpt-4o", help="Model to use for evaluation"
    ),
    max_iterations: int = typer.Option(
        10, help="Maximum number of iterations (default: 10, use -1 for unlimited)"
    ),
    min_iterations: int = typer.Option(
        3, help="Minimum number of iterations before accepting solution"
    ),
    execution_command: str = typer.Option(
        "python {file}", help="Command to execute generated code"
    ),
    editable_files: List[str] = typer.Option(
        [], help="List of files that can be edited"
    ),
    readonly_files: List[str] = typer.Option(
        [], help="List of files that are read-only context"
    ),
):
    """Create a new director configuration file."""
    try:
        config = {
            "prompt": prompt,
            "coder_model": coder_model,
            "evaluator_model": evaluator_model,
            "max_iterations": max_iterations,
            "min_iterations": min_iterations,
            "execution_command": execution_command,
            "context_editable": editable_files,
            "context_read_only": readonly_files,
            "evaluator": "default",
        }

        with open(output_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        typer.echo(f"✅ Created director config at {output_path}")

    except Exception as e:
        typer.echo(f"❌ Failed to create config: {str(e)}")


@app.command()
def generate_spec(
    name: str = typer.Argument(..., help="Name of the feature specification"),
    template: str = typer.Option("feature.yml", help="Template to use"),
    patterns: List[str] = typer.Option([], help="List of patterns to include"),
    output_dir: str = typer.Option("specs", help="Directory to save the spec file"),
):
    """Generate a new feature specification from a template."""
    try:
        from core.project_generator import SpecPromptGenerator

        generator = SpecPromptGenerator()

        # Create output directory if it doesn't exist
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        spec_path = generator.create_feature_spec(
            name=name, template=template, patterns=patterns
        )

        typer.echo(f"✅ Generated specification at {spec_path}")

    except Exception as e:
        typer.echo(f"❌ Failed to generate spec: {str(e)}")


@app.command()
def list_spec_templates():
    """List available specification templates."""
    try:
        generator = SpecPromptGenerator()

        template_dir = generator.template_dir / "spec_templates"
        templates = list(template_dir.glob("*.yml"))

        if not templates:
            typer.echo("No templates found")
            return

        typer.echo("📄 Available templates:")
        for template in templates:
            typer.echo(f"  - {template.name}")

            # Show template description if available
            try:
                with open(template) as f:
                    spec = yaml.safe_load(f)
                    if "description" in spec:
                        typer.echo(f"    {spec['description']}")
            except:
                pass

    except Exception as e:
        typer.echo(f"❌ Failed to list templates: {str(e)}")


# -----------------------------------------------------
# Project Initialization
# -----------------------------------------------------


@app.command()
def start(
    mode: str = typer.Option("cli", "--mode", "-m"),
    debug: bool = typer.Option(False, "--debug", "-d"),
):
    """Start aiden in either CLI or voice mode"""
    try:
        # Set up logging
        setup_logging(str | None)

        if mode == "voice":
            typer.echo("Starting voice mode...")
            # Voice mode initialization here
        else:
            typer.echo("Starting CLI mode...")
            # CLI mode initialization here

    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command()
def initialize(project_dir=setup_project_dir(Path.cwd())):
    """First-time setup for Aiden in a directory."""
    try:
        cwd = Path.cwd()

        # Check if we're in a git repo
        is_git_repo = False
        try:
            subprocess.run(
                ["git", "rev-parse", "--git-dir"], check=True, capture_output=True
            )
            is_git_repo = True
        except subprocess.CalledProcessError:
            pass

        if is_git_repo:
            # Existing project flow
            typer.echo("📂 Found existing git repository")

            # Check if repo has remote
            try:
                remote = subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                typer.echo(f"🔗 Repository is linked to: {remote.stdout.strip()}")
            except subprocess.CalledProcessError:
                if typer.confirm(
                    "❓ Repository isn't pushed to a remote. Would you like to set up GitHub?"
                ):
                    private = typer.confirm("❓ Should the repository be private?")
                    success, message = setup_github_repo(project_dir.name, private)
                    if success:
                        typer.echo(f"✅ {message}")
                    else:
                        typer.echo(f"❌ {message}")
        else:
            # New project flow
            if typer.confirm(
                "❓ Would you like to use the current directory for your project?"
            ):
                project_dir = cwd
            else:
                project_name = typer.prompt("📝 Enter project name")
                project_dir = cwd / project_name
                project_dir.mkdir(exist_ok=True)
                os.chdir(project_dir)

            if typer.confirm("❓ Would you like to initialize git?"):
                subprocess.run(["git", "init"], check=True)

                # Create .gitignore
                gitignore_content = """
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
.env
.venv
env/
venv/
ENV/

# Aiden
.aiden*
"""
                with open(".gitignore", "w") as f:
                    f.write(gitignore_content.strip())

                if typer.confirm("❓ Would you like to create a GitHub repository?"):
                    private = typer.confirm("❓ Should the repository be private?")
                    success, message = setup_github_repo(project_dir.name, private)
                    if success:
                        typer.echo(f"✅ {message}")
                    else:
                        typer.echo(f"❌ {message}")

        # Initialize Aiden configuration
        if not (cwd / ".aiden.conf.yml").exists():
            config = {
                "project": {
                    "name": project_dir.name,
                    "created_at": datetime.now().isoformat(),
                },
                "settings": {
                    "default_model": "gpt-4",
                    "auto_commits": True,
                    "auto_lint": True,
                },
            }
            with open(".aiden.conf.yml", "w") as f:
                yaml.dump(config, f, default_flow_style=False)
            typer.echo("✅ Created Aiden configuration")

        typer.echo(
            "\n🎉 Initialization complete! You can now use Aiden in this project."
        )
        typer.echo("Try 'aiden --help' to see available commands")

    except Exception as e:
        typer.echo(f"❌ Error during initialization: {str(e)}")
        raise typer.Exit(1)


# Project Management Commands
@app.command()
def set_project_description(
    project_name: str = typer.Argument(..., help="Name of the project"),
    description: str = typer.Argument(..., help="New project description"),
) -> None:
    """Set the description for a project"""
    try:
        project = Project.get_by_name(project_name)
        project.description = description
        project.save()
        typer.echo(f"✅ Updated description for project {project_name}")
    except Exception as e:
        typer.echo(f"❌ Error: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command()
def list_projects() -> None:
    """List all projects"""
    try:
        projects = Project.get_all()
        if not projects:
            typer.echo("No projects found")
            return

        for project in projects:
            typer.echo(f"📁 {project.name}: {project.description}")
    except Exception as e:
        typer.echo(f"❌ Error: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command()
def show_project(
    project_name: str = typer.Argument(
        ..., help="Name of the project to show details for"
    )
) -> None:
    """Show detailed information about a project"""
    try:
        project = Project.get_by_name(project_name)
        typer.echo(
            f"""
Project Details:
  Name: {project.name}
  Description: {project.description}
  Created: {project.created_at}
  Tasks: {len(project.tasks)}
"""
        )
    except Exception as e:
        typer.echo(f"❌ Error: {str(e)}", err=True)
        raise typer.Exit(1)


# Task Management Commands
@app.command()
def add_task(
    name: str = typer.Argument(..., help="Name of the task"),
    project_name: str = typer.Argument(..., help="Project to add task to"),
    priority: int = typer.Option(3, help="Task priority (1-5)", min=1, max=5),
) -> None:
    """Add a new task to a project"""
    try:
        project = Project.get_by_name(project_name)
        task = project.add_task(name=name, priority=priority)
        typer.echo(f"✅ Added task '{name}' to project {project_name}")
    except Exception as e:
        typer.echo(f"❌ Error: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command()
def set_task_priority(
    task_name: str = typer.Argument(..., help="Name of the task"),
    priority: int = typer.Argument(..., help="New priority (1-5)", min=1, max=5),
) -> None:
    """Update the priority of a task"""
    try:
        task = Task.get_by_name(task_name)
        task.priority = priority
        task.save()
        typer.echo(f"✅ Updated priority for task '{task_name}' to {priority}")
    except Exception as e:
        typer.echo(f"❌ Error: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command()
def complete_task(
    task_name: str = typer.Argument(..., help="Name of the task to mark as complete")
) -> None:
    """Mark a task as complete"""
    try:
        task = Task.get_by_name(task_name)
        task.complete()
        typer.echo(f"✅ Marked task '{task_name}' as complete")
    except Exception as e:
        typer.echo(f"❌ Error: {str(e)}", err=True)
        raise typer.Exit(1)


# Database Commands
@app.command()
def init_db() -> None:
    """Initialize the database"""
    try:
        from models.base import init_database

        init_database()
        typer.echo("✅ Database initialized successfully")
    except Exception as e:
        typer.echo(f"❌ Error: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command()
def backup_db(
    output_dir: str = typer.Option("./backups", help="Directory to store backup")
) -> None:
    """Create a backup of the database"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{output_dir}/db_backup_{timestamp}.sql"

        # Ensure backup directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Get database connection details from config
        config = get_config()
        db_name = config.get("database", "name")

        # Create backup using pg_dump
        result = subprocess.run(
            ["pg_dump", "-d", db_name, "-f", backup_file],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            typer.echo(f"✅ Database backup created at {backup_file}")
        else:
            raise Exception(f"Backup failed: {result.stderr}")
    except Exception as e:
        typer.echo(f"❌ Error: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command()
def validate_db() -> None:
    """Validate database connection and schema"""
    try:
        # Get database connection details from config
        config = get_config()
        db_params = config.get("database", {})

        # Test connection
        conn = psycopg2.connect(**db_params)
        cur = conn.cursor()

        # Check if required tables exist
        tables = ["projects", "tasks", "users"]
        for table in tables:
            cur.execute(
                f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table}')"
            )
            exists = cur.fetchone()[0]
            if not exists:
                raise Exception(f"Required table '{table}' not found")

        conn.close()
        typer.echo("✅ Database validation successful")
    except Exception as e:
        typer.echo(f"❌ Error: {str(e)}", err=True)
        raise typer.Exit(1)


# Core Entity Management Commands
@app.command()
def tasks(
    action: str = typer.Argument(
        ..., help="Action to perform: list, create, update, delete"
    ),
    task_id: Optional[int] = typer.Option(
        None, help="Task ID for update/delete operations"
    ),
    name: Optional[str] = typer.Option(None, help="Task name"),
    description: Optional[str] = typer.Option(None, help="Task description"),
    priority: Optional[int] = typer.Option(None, help="Task priority (1-5)"),
    due_date: Optional[str] = typer.Option(None, help="Due date (YYYY-MM-DD)"),
):
    """Manage tasks in the system"""
    pass


@app.command()
def users(
    action: str = typer.Argument(
        ..., help="Action to perform: list, create, update, delete"
    ),
    user_id: Optional[int] = typer.Option(
        None, help="User ID for update/delete operations"
    ),
    username: Optional[str] = typer.Option(None, help="Username"),
    email: Optional[str] = typer.Option(None, help="User email"),
    role: Optional[str] = typer.Option(None, help="User role"),
):
    """Manage users in the system"""
    pass


@app.command()
def projects(
    action: str = typer.Argument(
        ..., help="Action to perform: list, create, update, delete"
    ),
    project_id: Optional[int] = typer.Option(
        None, help="Project ID for update/delete operations"
    ),
    name: Optional[str] = typer.Option(None, help="Project name"),
    description: Optional[str] = typer.Option(None, help="Project description"),
    start_date: Optional[str] = typer.Option(None, help="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = typer.Option(None, help="End date (YYYY-MM-DD)"),
):
    """Manage projects in the system"""
    pass


@app.command()
def logs(
    action: str = typer.Argument(..., help="Action to perform: view, export, clear"),
    start_date: Optional[str] = typer.Option(None, help="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = typer.Option(None, help="End date (YYYY-MM-DD)"),
    log_type: Optional[str] = typer.Option(None, help="Log type (error, info, debug)"),
    export_format: Optional[str] = typer.Option(
        "csv", help="Export format (csv, json)"
    ),
):
    """Manage system logs"""
    pass


@app.command()
def create_client(
    name: str = typer.Argument(..., help="Client name"),
    email: Optional[str] = typer.Option(None, help="Client email"),
    company: Optional[str] = typer.Option(None, help="Client company"),
    phone: Optional[str] = typer.Option(None, help="Client phone number"),
    notes: Optional[str] = typer.Option(None, help="Additional notes"),
):
    """Create a new client in the system"""
    pass


@app.command()
def calendar_events(
    action: str = typer.Argument(
        ..., help="Action to perform: list, create, update, delete"
    ),
    event_id: Optional[int] = typer.Option(
        None, help="Event ID for update/delete operations"
    ),
    title: Optional[str] = typer.Option(None, help="Event title"),
    start_time: Optional[str] = typer.Option(
        None, help="Start time (YYYY-MM-DD HH:MM)"
    ),
    end_time: Optional[str] = typer.Option(None, help="End time (YYYY-MM-DD HH:MM)"),
    description: Optional[str] = typer.Option(None, help="Event description"),
    location: Optional[str] = typer.Option(None, help="Event location"),
    attendees: Optional[List[str]] = typer.Option(None, help="List of attendee emails"),
):
    """Manage calendar events"""
    pass


@app.command()
def task_dependencies(
    action: str = typer.Argument(..., help="Action to perform: list, add, remove"),
    task_id: int = typer.Option(..., help="Task ID"),
    dependent_task_id: Optional[int] = typer.Option(None, help="Dependent task ID"),
    dependency_type: Optional[str] = typer.Option(
        "blocks", help="Type of dependency (blocks, requires)"
    ),
):
    """Manage task dependencies"""
    pass


@app.command()
def tag_associations(
    action: str = typer.Argument(..., help="Action to perform: list, add, remove"),
    entity_type: str = typer.Option(..., help="Type of entity (task, project, user)"),
    entity_id: int = typer.Option(..., help="ID of the entity"),
    tag_id: Optional[int] = typer.Option(None, help="Tag ID to associate/dissociate"),
):
    """Manage tag associations for entities"""
    pass


@app.command()
def tags(
    action: str = typer.Argument(
        ..., help="Action to perform: list, create, update, delete"
    ),
    tag_id: Optional[int] = typer.Option(
        None, help="Tag ID for update/delete operations"
    ),
    name: Optional[str] = typer.Option
        (None, help="Tag name"),
    color: Optional[str] = typer.Option
        (None, help="Tag color (hex code)"),
    description: Optional[str] = typer.Option
        (None, help="Tag description"),
):
    """Manage tags in the system"""
    pass

@app.command()
def add(
    item_type: str = typer.Argument(
        ..., help="Type of item to add (assistant, project, command)"
    ),
    template_name: Optional[str] = typer.Option(
        None, "--template", "-t", help="Template to use"
    ),
    list_templates: bool = typer.Option(
        False, "--list", "-l", help="List available templates"
    ),
):
    """Add a new item using templates"""
    try:
        if list_templates:
            template_manager.list_templates(item_type)
            return

        if template_name:
            # Use specific template
            result = (template_manager.create_from_template
                      (template_name))
            typer.echo(f"Created {item_type} from template"
                       f" {template_name}")
            return result

        # Show available templates and let user choose
        templates = template_manager.get_templates(item_type)
        if not templates:
            typer.echo(f"No templates found for {item_type}")
            return

        typer.echo(f"\nAvailable {item_type} templates:")
        for i, template in enumerate(templates, 1):
            typer.echo(f"{i}. {template.name}"
            f" - {template.description}")

        choice = typer.prompt("Choose a template"
        " number", type=int, min=1, max=len(templates))
        chosen_template = templates[choice - 1]

        result = (template_manager.create_from_template
        (chosen_template.name))
        typer.echo(f"Created {item_type} from template "
        f"{chosen_template.name}")
        return result

    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)

@app.command()
def tags(
    action: str = typer.Argument(
        ..., help="Action to perform: list, create, update, delete"
    ),
    tag_id: Optional[int] = typer.Option(
        None, help="Tag ID for update/delete operations"
    ),
    name: Optional[str] = typer.Option(
        None, help="Tag name"
    ),
    color: Optional[str] = typer.Option(
        None, help="Tag color (hex code)"
    ),
    description: Optional[str] = typer.Option(
        None, help="Tag description"
    ),
):
    """Manage tags in the system"""
    pass

@app.command()
def awaken(
    model: str = typer.Option(
        "gpt-4",
        "--model",
        "-m",
        help=(
            "Model to use: gpt-4, gpt-3.5-turbo, "
            "claude-3-opus, claude-3-sonnet"
        )
    ),
    voice_type: str = typer.Option(
        "elevenlabs",
        "--voice-type",
        "-v",
        help="Voice type to use: local, realtime-tts, or elevenlabs"
    ),
    elevenlabs_voice: str = typer.Option(
        None, "--elevenlabs-voice", help="ElevenLabs voice ID (only for elevenlabs voice type)"
    ),
    brain: str = typer.Option(
        "ollama:dolphin-mixtral",
        "--brain",
        "-b",
        help="Brain to use: ollama:<model> or deepseek"
    ),
    system_prompt: str = typer.Option(
        None, "--system-prompt", "-s", help="System prompt for the conversation agent"
    ),
    conversation_style: str = typer.Option(
        "casual",
        "--style",
        help="Conversation style: casual, professional, or technical"
    ),
    interruption_with_keyboard=None
):
    """Start an enhanced voice interface with advanced conversation capabilities"""
    try:
        # Initialize logging
        session_id = create_session_logger_id()
        logger = setup_logging(session_id)
        logger.info(f"🚀 Starting enhanced voice session {session_id}")

        # Set up voice configuration
        if voice_type == "elevenlabs" and elevenlabs_voice:
            os.environ["ELEVEN_VOICE"] = elevenlabs_voice

        # Initialize the base assistant
        assistant = PlainAssistant(logger, session_id)

        # Configure the conversation agent
        agent_config = ConversationAgentConfig(
            model_name=model,
            system_prompt=system_prompt or "You are a helpful AI assistant.",
            conversation_style=conversation_style,
            max_history=10,
        )
        conversation_agent = ConversationAgent(agent_config)
        
        typer.echo(f"🎤 Voice interface activated with:")
        typer.echo(f"   - Model: {model}")
        typer.echo(f"   - Voice: {voice_type}")
        typer.echo(f"   - Brain: {brain}")
        typer.echo("\nTry saying 'Hey Aiden, what can you do?' to get started")
        typer.echo("Press Ctrl+C to exit")

        def process_voice(text: str):
            try:
                # Process through both assistants
                base_response = assistant.process_text(text)
                agent_response = asyncio.run(
                    conversation_agent.process(
                        {"text": text, "history": assistant.conversation_history}
                    )
                )

                if agent_response.success:
                    return agent_response.data["response"]
                return base_response

            except Exception as e:
                logger.error(f"Error processing voice: {str(e)}")
                return f"I encountered an error: {str(e)}"

        while True:
            try:
                recorder.text(process_voice)
            except interruption_with_keyboard:
                typer.echo("\n👋 Shutting down voice interface...")
                assistant.save_conversation()
                break
            except Exception as e:
                typer.echo(f"Error in voice loop: {str(e)}")
                continue

    except Exception as e:
        typer.echo(f"❌ Error initializing voice interface: {str(e)}")
        raise typer.Exit(1)


@app.command()
def create_director_config(
    output_path: str = typer.Argument(
        ..., help="Path to save the config file"
    ),
    prompt: str = typer.Option(
        ..., help="Prompt or path to .md file with prompt"
    ),
    coder_model: str = typer.Option(
        "gpt-4", help="Model to use for coding"
    ),
    evaluator_model: str = typer.Option(
        "gpt-4o", help="Model to use for evaluation"
    ),
    max_iterations: int = typer.Option(
        5, help="Maximum number of iterations"
    ),
    execution_command: str = typer.Option(
        "python {file}", help="Command to execute generated code"
    ),
    editable_files: List[str] = typer.Option(
        [], help="List of files that can be edited"
    ),
    readonly_files: List[str] = typer.Option(
        [], help="List of files that are read-only context"
    ),
):
    """Create a new director configuration file."""
    try:
        config = {
            "prompt": prompt,
            "coder_model": coder_model,
            "evaluator_model": evaluator_model,
            "max_iterations": max_iterations,
            "execution_command": execution_command,
            "context_editable": editable_files,
            "context_read_only": readonly_files,
            "evaluator": "default",
        }

        with open(output_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        typer.echo(f"✅ Created director config at {output_path}")

    except Exception as e:
        typer.echo(f"❌ Failed to create config: {str(e)}")

@app.command()
def list_spec_templates():
    """List available specification templates."""
    try:
        generator = SpecPromptGenerator()

        template_dir = generator.template_dir / "spec_templates"
        templates = list(template_dir.glob("*.yml"))

        if not templates:
            typer.echo("No templates found")
            return

        typer.echo("📄 Available templates:")
        for template in templates:
            typer.echo(f"  - {template.name}")

            # Show template description if available
            try:
                with open(template) as f:
                    spec = yaml.safe_load(f)
                    if "description" in spec:
                        typer.echo(f"    {spec['description']}")
            except:
                pass

    except Exception as e:
        typer.echo(f"❌ Failed to list templates: {str(e)}")

@app.command()
def list_spec_templates():
    """List available specification templates."""
    try:
        generator = SpecPromptGenerator()

        template_dir = generator.template_dir / "spec_templates"
        templates = list(template_dir.glob("*.yml"))

        if not templates:
            typer.echo("No templates found")
            return

        typer.echo("📄 Available templates:")
        for template in templates:
            typer.echo(f"  - {template.name}")

            # Show template description if available
            try:
                with open(template) as f:
                    spec = yaml.safe_load(f)
                    if "description" in spec:
                        typer.echo(f"    {spec['description']}")
            except:
                pass

    except FileNotFoundError as e:
        typer.echo(f"Template directory not found: {str(e)}")
    except PermissionError as e:
        typer.echo(f"Permission denied accessing templates: {str(e)}")
    except Exception as e:
        typer.echo(f"Unexpected error listing templates: {str(e)}")
        typer.echo(f"Error in list_spec_templates: {str(e)}")

@app.command()
def validate_db():
    """Validate database connection and schema"""
    try:
        # Validation code here
        pass
    except psycopg2.Error as e:
        typer.echo(f"Database error: {str(e)}")
    except Exception as e:
        typer.echo(f"Unexpected error during validation: {str(e)}")

@app.command()
def list_projects(
    status: str = typer.Option(
        None,
        help="Filter by status (active, completed, etc)"
    ),
    owner_id: int = typer.Option(
        None,
        help="Filter by owner ID"
    ),
):
    """List all projects with optional filters."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Build query based on filters
        query = """
            SELECT 
                p.id,
                p.name,
                p.description,
                p.status,
                p.priority,
                p.start_date,
                p.due_date,
                p.completed_date,
                u.username as owner
            FROM projects p
            LEFT JOIN users u ON p.owner_id = u.id
            WHERE 1=1
        """
        params = []

        if status:
            query += " AND p.status = ?"
            params.append(status)

        if owner_id:
            query += " AND p.owner_id = ?"
            params.append(owner_id)

        cur.execute(query, params)
        projects = cur.fetchall()

        if not projects:
            typer.echo("No projects found matching criteria")
            return

        for project in projects:
            typer.echo(
                f"""
Project: {project[0]} - {project[1]}
  Description: {project[2]}
  Status: {project[3]}
  Priority: {project[4]}
  Start Date: {project[5]}
  Due Date: {project[6]}
  Completed Date: {project[7]}
  Owner: {project[8]}
"""
            )
    except Exception as e:
        typer.echo(f"❌ Failed to list projects: {str(e)}")
    finally:
        conn.close()


def list_calendar_events():
    """List all calendar events"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM calendar_events ORDER BY start_time")
    return cur.fetchall()

def create_calendar_event(title: str, start_time: str, end_time: Optional[str] = None,
                         description: str = "", location: str = "", 
                         attendees: Optional[List[str]] = None):
    """Create a new calendar event"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO calendar_events (title, start_time, end_time, description, location)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """, (title, start_time, end_time, description, location))
    event_id = cur.fetchone()[0]
    conn.commit()
    return event_id

def update_calendar_event(event_id: int, title: str, start_time: str):
    """Update an existing calendar event"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE calendar_events 
        SET title = %s, start_time = %s
        WHERE id = %s
    """, (title, start_time, event_id))
    conn.commit()

def delete_calendar_event(event_id: int):
    """Delete a calendar event"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM calendar_events WHERE id = %s", (event_id,))
    conn.commit()


@app.command()
def calendar_events(
    action: str = typer.Argument(
        ..., help="Action to perform: list, create, update, delete"
    ),
    event_id: Optional[int] = typer.Option(
        None, help="Event ID for update/delete operations"
    ),
    title: Optional[str] = typer.Option(None, help="Event title"),
    start_time: Optional[str] = typer.Option(
        None, help="Start time (YYYY-MM-DD HH:MM)"
    ),
    end_time: Optional[str] = typer.Option(None, help="End time (YYYY-MM-DD HH:MM)"),
    description: Optional[str] = typer.Option(None, help="Event description"),
    location: Optional[str] = typer.Option(None, help="Event location"),
    attendees: Optional[List[str]] = typer.Option(None, help="List of attendee emails"),
):
    """Manage calendar events"""
    try:
        if action == "list":
            events = list_calendar_events()
            for event in events:
                typer.echo(
                    f"""
Event: {event.title}
  Start: {event.start_time}
  End: {event.end_time}
  Location: {event.location}
  Description: {event.description}
"""
                )
        elif action == "create":
            if not all([title, start_time]):
                typer.echo(
                    "Title and start time are required for creating events"
                )
                return
            create_calendar_event(
                title=title,
                start_time=start_time,
                end_time=end_time,
                description=description,
                location=location,
                attendees=attendees
            )
        elif action in ["update", "delete"]:
            if not event_id:
                typer.echo("Event ID is required for update/delete")
                return
            if action == "update":
                update_calendar_event(event_id, title, start_time)
            else:
                delete_calendar_event(event_id)
    except Exception as e:
        typer.echo(f"Error managing calendar events: {str(e)}")
