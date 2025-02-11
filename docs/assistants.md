# Managing Assistants

This guide explains how to create and manage different assistants in the aiden system.

## Creating a New Assistant

Use the create assistant script:
```bash
./scripts/create_assistant.sh
```

This interactive script will guide you through:
1. Choosing a name for your assistant
2. Setting your name (optional)
3. Selecting a template (base or typer)
4. Choosing a voice type (local, elevenlabs, realtime-tts)
5. Selecting an AI model (GPT-4, Claude, etc.)

## Running an Assistant

### Basic Usage
```bash
# Run the default assistant (aiden)
./aiden.sh start

# Run a specific assistant
./aiden.sh start --assistant <assistant_name>

# Run in CLI mode
./aiden.sh start --assistant <assistant_name> --mode cli

# Run in voice mode
./aiden.sh start --assistant <assistant_name> --mode voice
```

### Quick Commands
```bash
# Quick listen mode with default assistant
./aiden.sh listen

# Quick listen with specific assistant
./aiden.sh listen --assistant <assistant_name>

# Toggle voice recognition
./aiden.sh toggle

# Stop the assistant
./aiden.sh stop
```

## Assistant Templates

### Base Assistant Template
The basic template with essential features:
- Voice interaction
- Text-to-speech
- Basic file operations
- Conversation memory

Example config:
```yaml
base_assistant:
  name: aiden
  voice:
    type: local
  agents:
    conversation:
      model_name: gpt-4
    task:
      type: task
      model_name: local
```

### Typer Assistant Template
Enhanced template with CLI capabilities:
- All base features
- Command-line interface
- Argument parsing
- Shell command integration

Example config:
```yaml
typer_assistant:
  name: aiden
  voice:
    type: elevenlabs
  agents:
    conversation:
      model_name: claude-3-opus
    task:
      type: task
      model_name: local
```

## Configuration

Assistants are configured in `config/config.yml`. Each assistant can have:

1. **Voice Settings**
   - `local`: System text-to-speech
   - `elevenlabs`: ElevenLabs high-quality voices
   - `realtime-tts`: Real-time text-to-speech

2. **AI Models**
   - `gpt-4`: OpenAI's most capable model
   - `gpt-3.5-turbo`: Faster, cost-effective OpenAI model
   - `claude-3-opus`: Anthropic's most capable model
   - `claude-3-sonnet`: Balanced Anthropic model
   - `ollama:phi4`: Local Phi-4 model via Ollama

3. **Agent Types**
   - `conversation`: Handles natural language understanding
   - `task`: Manages file operations and simple tasks

## Examples

1. **Create a CLI-focused Assistant**
```bash
$ ./scripts/create_assistant.sh
What's your assistant's name? CommandPro
Choose a template: typer_assistant
Choose a voice type: local
Choose a brain model: gpt-4

# Run it
./aiden.sh start --assistant command_pro --mode cli
```

2. **Create a Voice Assistant**
```bash
$ ./scripts/create_assistant.sh
What's your assistant's name? Alice
Choose a template: base_assistant
Choose a voice type: elevenlabs
Choose a brain model: claude-3-opus

# Run it
./aiden.sh start --assistant alice --mode voice
```

## Troubleshooting

1. **Voice Not Working**
   - Check if required API keys are set in `.env`
   - Verify microphone permissions
   - Try switching to `local` voice type

2. **Model Errors**
   - Verify API keys in `.env`
   - Check internet connection
   - Try a different model

3. **Permission Errors**
   - Run `chmod +x scripts/*.sh` to make scripts executable
   - Ensure you're in the project root directory
