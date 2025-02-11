import logging
import os
import signal
import subprocess
import asyncio
from enum import Enum
from pathlib import Path
import typer
from core.voice import VoiceCommandSystem
from utils.shared_state import SharedState, FocusState
from core.cli import (

    project, handle_create_project, think_speak, tts, status,
    start as cli_start, ping, process_text, get_connection,
    list_projects, create_project, create_task, ping_server,
    show_config, list_files, list_users, create_user,
    delete_user, generate_report, backup_data, restore_data,
    summarize_logs, upload_file, download_file, filter_records,
    compare_files, encrypt_data, decrypt_data, migrate_database,
    queue_task, handle_list_tasks, remove_task, list_tasks,
    inspect_task, create_goal, create_event, add_task_dependency,
    list_project_tasks, assign_task, assign_project, initialize
)

logger = logging.getLogger(__name__)
app = typer.Typer()
PID_FILE = Path("/tmp/aiden.pid")

# Focus state management
ASSISTANT_FOCUSED = False

# Register all commands with the Typer app
app.command()(initialize)
app.command()(project)
app.command()(handle_create_project)
app.command()(think_speak)
app.command()(tts)
app.command()(status)
app.command(name="start")(cli_start)
app.command()(ping)
app.command()(process_text)
app.command()(get_connection)
app.command()(list_projects)
app.command()(create_project)
app.command()(ping_server)
app.command()(show_config)
app.command()(list_files)
app.command()(list_users)
app.command()(create_user)
app.command()(delete_user)
app.command()(generate_report)
app.command()(backup_data)
app.command()(restore_data)
app.command()(summarize_logs)
app.command()(upload_file)
app.command()(download_file)
app.command()(filter_records)
app.command()(compare_files)
app.command()(encrypt_data)
app.command()(decrypt_data)
app.command()(migrate_database)
app.command()(queue_task)
app.command()(handle_list_tasks)
app.command()(remove_task)
app.command()(list_tasks)
app.command()(inspect_task)
app.command()(create_goal)
app.command()(create_event)
app.command()(add_task_dependency)
app.command()(list_project_tasks)
app.command()(assign_task)
app.command()(assign_project)
app.command()(create_task)

# -----------------------------------------------------
# Entry point
# -----------------------------------------------------
def main():
    """Entry point for the CLI."""
    try:
        # Check if this is first run in this directory
        cwd = Path.cwd()
        config_file = cwd / ".aiden.conf.yml"


        if not config_file.exists():
            if typer.confirm(
                "👋 Welcome to Aiden! Would you like to set up your project now?"
            ):
                app.initialize()
                return

        app()
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)



def set_assistant_focus(focused: bool):
    """Set assistant focus state"""
    SharedState.set_focus_state(FocusState.FOCUSED if focused else FocusState.UNFOCUSED)
    logger.info(f"Assistant focus set to: {focused}")


def is_assistant_focused() -> bool:
    return SharedState.is_focused()


def set_assistant_focus(focused: bool):
    """Set assistant focus state"""
    global ASSISTANT_FOCUSED
    ASSISTANT_FOCUSED = focused
    logger.info(f"Assistant focus set to: {focused}")


def is_assistant_focused() -> bool:
    return ASSISTANT_FOCUSED


class Mode(str, Enum):
    CLI = "cli"
    VOICE = "voice"
    BOTH = "both"


class Daemonize:
    def __init__(self, app_name: str, pid_file: Path, action, chdir: str):
        self.app_name = app_name
        self.pid_file = pid_file
        self.action = action
        self.chdir = chdir

    def start(self):
        """Start the assistant as a background process"""
        if self.pid_file.exists():
            typer.echo("🚫 Assistant is already running")
            return

        pid = os.fork()
        if pid > 0:
            typer.echo(f"✅ Assistant started with PID {pid}")
            self.pid_file.write_text(str(pid))
            return

        os.chdir(self.chdir)
        os.setsid()
        os.umask(0)

        with open(self.pid_file, "w") as f:
            f.write(str(os.getpid()))

        self.action()

    def stop(self):
        """Stop the assistant"""
        if not self.pid_file.exists():
            typer.echo("❌ Assistant is not running")
            return

        with open(self.pid_file, "r") as f:
            pid = int(f.read().strip())

        try:
            os.kill(pid, signal.SIGTERM)
            self.pid_file.unlink()
            typer.echo("✅ Assistant stopped")
        except ProcessLookupError:
            typer.echo("❌ Process not found, cleaning up PID file")
            self.pid_file.unlink()


# -----------------------------------------------------
# CLI Commands
# -----------------------------------------------------

@app.command()
def focus():
    """Focus the assistant for commands"""
    set_assistant_focus(True)
    typer.echo("🎯 Assistant focused and ready")


@app.command()
def unfocus():
    """Unfocus the assistant"""
    set_assistant_focus(False)
    typer.echo("💤 Assistant unfocused")


@app.command()
def focus():
    """Focus the assistant for commands"""
    set_assistant_focus(True)
    typer.echo("🎯 Assistant focused and ready")


@app.command()
def unfocus():
    """Unfocus the assistant"""
    set_assistant_focus(False)
    typer.echo("💤 Assistant unfocused")


@app.command()
def start(
    mode: Mode = typer.Option(Mode.CLI, "--mode", "-m"),
    daemon: bool = typer.Option(False, "--daemon", "-d"),
):
    """Start the assistant in specified mode"""
    if daemon:
        daemon = Daemonize("aiden", PID_FILE, lambda: run_mode(mode), os.getcwd())
        daemon.start()
    else:
        run_mode(mode)


def run_mode(mode: Mode):
    """Execute mode-specific behavior"""
    if mode == Mode.VOICE or mode == Mode.BOTH:
        voice_system = VoiceCommandSystem(logging.getLogger(__name__))
        asyncio.run(voice_system.start())
    if mode == Mode.CLI or mode == Mode.BOTH:
        app()  # Start the CLI interface using Typer app


@app.command()
def stop():
    """Stop the assistant"""
    daemon = Daemonize("aiden", PID_FILE, None, os.getcwd())
    daemon.stop()




# Update the execute_tool function
def execute_tool(command: str):
    """Run a system command"""
    if not SharedState.is_focused():
        typer.echo("Assistant is unfocused. Use 'focus' command first.")
        return
    try:
        output = subprocess.run(command, shell=True, capture_output=True, text=True)
        typer.echo(f"🛠️ Tool Output:\n{output.stdout}")
    except Exception as e:
        typer.echo(f"❌ Error running command: {str(e)}")

    # Update list_files function


@app.command()
def list_files(directory: str = "."):
    """List files in a directory"""
    if not SharedState.is_focused():
        typer.echo("Assistant is unfocused. Use 'focus' command first.")
        return

    try:
        files = os.listdir(directory)
        typer.echo(f"📂 Files in '{directory}': {files}")
    except Exception as e:
        typer.echo(f"❌ Error accessing directory: {str(e)}")

# -----------------------------------------------------
# TOOL & FILE ACCESS
# -----------------------------------------------------
def execute_tool(command: str):
    """Run a system command"""
    if not is_assistant_focused():
        typer.echo("Assistant is unfocused. Use 'focus' command first.")
        return
    try:
        output = subprocess.run(command, shell=True, capture_output=True, text=True)
        typer.echo(f"🛠️ Tool Output:\n{output.stdout}")
    except Exception as e:
        typer.echo(f"❌ Error running command: {str(e)}")


@app.command()
def run_tool(tool_name: str):
    """Execute a system tool"""
    execute_tool(tool_name)


@app.command()
def list_files(directory: str = "."):
    """List files in a directory"""
    if not is_assistant_focused():
        typer.echo("Assistant is unfocused. Use 'focus' command first.")
        return

    try:
        files = os.listdir(directory)
        typer.echo(f"📂 Files in '{directory}': {files}")
    except Exception as e:
        typer.echo(f"❌ Error accessing directory: {str(e)}")


if __name__ == "__main__":
    main()
