# Aiden Command System Architecture

## Core Components

1. TyperAgent
   - Handles CLI command processing
   - Manages voice shortcuts
   - Integrates with ElevenLabs for voice responses

2. VoiceCommandSystem
   - Uses OpenWakeWord for wake word detection
   - Uses Whisper for speech recognition
   - Manages command callbacks

## Command Categories

### 1. Project Management
- Create project
- Set project description
- List projects
- Show project details
- Assign project

### 2. Task Management
- Add task
- Set task priority
- Mark task complete
- List tasks
- Show project tasks

### 3. Code Generation
- Generate code
- Create feature spec
- Explain code
- Optimize code
- Add comments

### 4. Database Operations
- Initialize database
- Create user
- List users
- Backup database
- Validate database

### 5. System Commands
- Exit/Quit
- Help
- Show config
- Clear screen
- Repeat last command

## Command Pattern

Each command should:
1. Support both CLI and voice interfaces
2. Handle errors gracefully
3. Provide feedback in both text and voice modes
4. Follow consistent naming patterns
5. Include help text and documentation

## Implementation Notes

1. CLI Commands:
   ```python
   @app.command()
   def command_name(
       param: str = typer.Argument(..., help="Parameter description"),
       option: str = typer.Option("default", help="Option description")
   ) -> None:
       """Command docstring"""
       pass
   ```

2. Voice Integration:
   ```python
   voice_system.register_command("command phrase", callback_function)
   ```

3. Error Handling:
   ```python
   try:
       # Command logic
   except Exception as e:
       typer.echo(f"Error: {str(e)}", err=True)
       raise typer.Exit(1)
   ```
