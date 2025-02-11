# Adding Custom Commands to Aiden

This guide explains how to add custom commands to your Aiden assistant using Python's Typer framework.

## Project Structure

Custom commands should be organized in the `aiden/cli/commands/` directory:

```
aiden/
├── cli/
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── user_commands.py    # Your custom user commands
│   │   └── task_commands.py    # Your custom task commands
│   └── main.py
```

## Creating Command Files

1. Create a new Python file in the `aiden/cli/commands/` directory:

```python
# aiden/cli/commands/user_commands.py
from typing import Optional
import typer
from aiden.cli.commands.base import BaseCommand

app = typer.Typer()

@app.command()
def add_user(

    name: str = typer.Argument(..., help="User's name"),
    role: str = typer.Option("user", help="User's role")
) -> None:
    """Add a new user to the system"""
    # Your implementation here
    typer.echo(f"Added user {name} with role {role}")

@app.command()
def list_users() -> None:
    """List all users in the system"""
    # Your implementation here
    typer.echo("Listing all users...")
```

## Registering Commands

1. Import your command file in `aiden/cli/commands/__init__.py`:

```python
from aiden.cli.commands.user_commands import app as user_commands
from aiden.cli.commands.task_commands import app as task_commands

# Add your commands to the __all__ list
__all__ = ['user_commands', 'task_commands']
```

2. Register commands in `aiden/cli/main.py`:

```python
from aiden.cli.commands import user_commands, task_commands

app = typer.Typer()
app.add_typer(user_commands, name="user")
app.add_typer(task_commands, name="task")
```

## Using Your Commands

After adding your commands, they will be available through the CLI:

```bash
# User commands
aiden user add-user "John Doe" --role admin
aiden user list-users

# Task commands
aiden task add-task "Complete documentation"
aiden task list-tasks
```

## Best Practices

1. **Use Type Hints**: Always include proper type hints for your command parameters
2. **Add Help Text**: Include descriptive help text for commands and parameters
3. **Error Handling**: Implement proper error handling and user feedback
4. **Base Classes**: Extend `BaseCommand` for shared functionality
5. **Documentation**: Add docstrings to all commands

## Example: Complete Command Implementation

Here's a complete example of a command with error handling and feedback:

```python
from typing import Optional
import typer
from aiden.cli.commands.base import BaseCommand
from aiden.core.exceptions import AidenError

app = typer.Typer()

class UserCommand(BaseCommand):
    def add_user(self, name: str, role: str) -> bool:
        # Implementation here
        return True

@app.command()
def add_user(
    name: str = typer.Argument(..., help="User's name"),
    role: str = typer.Option("user", help="User's role"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress output")
) -> None:
    """
    Add a new user to the system.
    
    Args:
        name: The name of the user to add
        role: The role to assign to the user
        quiet: If True, suppress command output
    """
    try:
        cmd = UserCommand()
        success = cmd.add_user(name, role)
        
        if success and not quiet:
            typer.echo(f"✅ Successfully added user {name} with role {role}")
            
    except AidenError as e:
        typer.echo(f"❌ Error: {str(e)}", err=True)
        raise typer.Exit(1)
```

## Testing Commands

Create tests for your commands in the `tests/cli/commands/` directory:

```python
# tests/cli/commands/test_user_commands.py
from typer.testing import CliRunner
from aiden.cli.main import app

runner = CliRunner()

def test_add_user():
    result = runner.invoke(app, ["user", "add-user", "Test User"])
    assert result.exit_code == 0
    assert "Successfully added user Test User" in result.stdout
```

For more examples and advanced usage, check the [Typer documentation](https://typer.tiangolo.com/).



    def process_text(self, text: str) -> bool:
        """
        Process user speech input and map it to command functions with enhanced voice interaction.
        """
        try:
            assistant_name = get_config("typer_assistant.assistant_name")
            if assistant_name.lower() not in text.lower():
                self.speak(f"I'm {assistant_name}, but you weren't talking to me.")
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
                # Command Management
                if "add" in text and "command" in text:
                    # Extract command name and description
                    parts = text.split("with description", 1)
                    command_name = (
                        parts[0]
                        .replace("add", "")
                        .replace("command", "")
                        .strip()
                        .replace(" ", "_")
                    )
                    description = (
                        parts[1].strip()
                        if len(parts) > 1
                        else "Voice-generated command"
                    )

                    add_command(command_name, description)
                    self.speak(f"I've added the {command_name} command for you.")

                elif "remove" in text and "command" in text:
                    command_name = (
                        text.replace("remove", "")
                        .replace("command", "")
                        .strip()
                        .replace(" ", "_")
                    )

                    # Ask for confirmation
                    self.speak(
                        f"Are you sure you want to remove the {command_name} command?"
                    )
                    confirmation = self.get_voice_confirmation()

                    if confirmation:
                        remove_command(command_name)
                        self.speak(f"I've removed the {command_name} command.")
                    else:
                        self.speak("Command removal cancelled.")

                elif any(
                    phrase in text
                    for phrase in ["list commands", "show commands", "what commands"]
                ):
                    self.speak("Here are the available commands:")
                    list_commands()

                elif "run" in text and "command" in text:
                    command_name = (
                        text.replace("run", "")
                        .replace("command", "")
                        .strip()
                        .replace(" ", "_")
                    )

                    # Verify command exists
                    if self.command_exists(command_name):
                        self.speak(f"Running {command_name} command.")
                        result = self.exec_command(command_name)

                        # Provide verbal feedback on execution
                        if result["success"]:
                            self.speak(
                                f"Command {command_name} completed successfully."
                            )
                        else:
                            self.speak(
                                f"There was an issue running the command: {result.get('error', 'Unknown error')}"
                            )
                    else:
                        self.speak(
                            f"I couldn't find a command named {command_name}. Would you like me to create it?"
                        )
                        if self.get_voice_confirmation():
                            self.speak(
                                "What should this command do? Please provide a description."
                            )
                            description = self.get_voice_input()
                            add_command(command_name, description)
                            self.speak(
                                f"I've created the {command_name} command for you."
                            )

                elif "help" in text or "what can you do" in text:
                    self.speak(
                        """
                        I can help you manage and run commands. Try saying:
                        - Add a command with a name and description
                        - Remove a command
                        - List all available commands
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
