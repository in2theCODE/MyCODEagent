# 🗣️ Voice Commands Guide

This guide covers all available voice commands in aiden and how to use them effectively.

## 🎯 Command Categories

- [Project Management](#project-management)
- [Task Management](#task-management)
- [Code Generation](#code-generation)
- [Database Operations](#database-operations)
- [System Commands](#system-commands)

## 📋 Command Reference

### Project Management

| Command Pattern | Example | Description |
|----------------|---------|-------------|
| "Create a new project called [name]" | "Create a new project called Website Redesign" | Creates a new project |
| "Set project description to [description]" | "Set project description to Modernize company website" | Updates project description |
| "List all projects" | "List all projects" | Shows all projects |
| "Show project details for [name]" | "Show project details for Website Redesign" | Displays project information |
| "Assign project [name] to [user]" | "Assign project Website Redesign to John" | Changes project ownership |

### Task Management

| Command Pattern | Example | Description |
|----------------|---------|-------------|
| "Add task [name] to project [project]" | "Add task implement login to Website Redesign" | Creates a new task in project |
| "Set task priority to [1-5]" | "Set task priority to 3" | Updates task priority |
| "Mark task [name] as complete" | "Mark task implement login as complete" | Completes a task |
| "List all tasks" | "List all tasks" | Shows all tasks |
| "Show tasks for project [name]" | "Show tasks for Website Redesign" | Lists project tasks |

### Code Generation

| Command Pattern | Example | Description |
|----------------|---------|-------------|
| "Generate code for [description]" | "Generate code for user authentication" | Creates code based on description |
| "Create feature spec for [name]" | "Create feature spec for authentication" | Generates feature specification |
| "Explain code in [file]" | "Explain code in auth.py" | Provides code explanation |
| "Optimize code in [file]" | "Optimize code in database.py" | Suggests optimizations |
| "Add comments to [file]" | "Add comments to utils.py" | Adds documentation |

### Database Operations

| Command Pattern | Example | Description |
|----------------|---------|-------------|
| "Initialize database" | "Initialize database" | Sets up database |
| "Create new user [name]" | "Create new user john_doe" | Adds new user |
| "List all users" | "List all users" | Shows all users |
| "Backup database" | "Backup database" | Creates backup |
| "Validate database" | "Validate database" | Checks connection |

### System Commands

| Command Pattern | Example | Description |
|----------------|---------|-------------|
| "Exit" or "Quit" | "Exit" | Ends session |
| "Help" | "Help" | Shows help |
| "Show config" | "Show config" | Displays settings |
| "Clear screen" | "Clear screen" | Clears terminal |
| "Repeat last command" | "Repeat last command" | Repeats previous |

## 🎤 Voice Input Tips

### Best Practices

1. **Speak Clearly**
   - Use natural pace
   - Enunciate clearly
   - Maintain consistent volume

2. **Command Structure**
   - Start with action verb
   - Be specific
   - Use proper nouns for names

3. **Background Noise**
   - Minimize ambient noise
   - Use in quiet environment
   - Keep microphone close

### Command Variations

aiden understands multiple ways to express the same command:

```text
# Creating a project
"Create a new project called X"
"Start a project named X"
"Make a project X"

# Adding tasks
"Add task X to project Y"
"Create task X in Y"
"Make a new task X for project Y"
```

## ⚡ Quick Commands

Common commands you'll use frequently:

```text
"What's my next task?"
"Show my priorities"
"List active projects"
"Generate code"
"Help me with [topic]"
```

## 🔧 Customization

You can customize voice command behavior in `config.yml`:

```yaml
voice:
  command_prefix: ""  # Optional prefix for commands
  confirmation_required: true  # Ask before destructive actions
  response_style: "concise"  # verbose/concise/minimal
  language: "en-US"  # Voice recognition language
```

## 🚫 Limitations

- Complex code generation may require written input
- Some commands need specific formatting
- Background noise can affect recognition
- Some technical terms may need spelling

## 🆘 Troubleshooting

If aiden doesn't recognize a command:

1. Try rephrasing
2. Use simpler terms
3. Break into smaller commands
4. Check microphone settings
5. Verify command syntax
