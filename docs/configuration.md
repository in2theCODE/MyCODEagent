# ⚙️ Configuration Guide

Learn how to configure and customize Aiden for your needs.

## 📑 Table of Contents

- [Environment Setup](#environment-setup)
- [Assistant Configuration](#assistant-configuration)
- [AI Models](#ai-models)
- [Database Configuration](#database-configuration)
- [Command Settings](#command-settings)

## 🌍 Environment Setup

### Required Variables

```env
# Supabase Configuration
SUPABASE_DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres
SUPABASE_URL=https://[YOUR-PROJECT-REF].supabase.co
SUPABASE_KEY=[YOUR-SUPABASE-KEY]

# OpenAI Configuration (for GPT-4 based assistants)
OPENAI_API_KEY=your_openai_api_key

# Anthropic Configuration (for Claude based assistants)
ANTHROPIC_API_KEY=your_anthropic_key

# Optional: Voice Synthesis
ELEVEN_LABS_API_KEY=your_eleven_labs_key
```

## 🤖 Assistant Configuration

### Creating an Assistant

Use the provided scripts to create and configure your assistant:

```bash
# Create a new assistant with interactive setup
./scripts/create_assistant.sh

# Use pre-configured assistants
./scripts/deepseek-architect.sh    # Deepseek-based assistant
./scripts/sonnet-architect.sh      # Claude-based assistant
./scripts/o1-architect-deepseek-editor.sh  # O1 Deepseek editor
```

### Assistant Settings

```yaml
# config/config.yml
assistant:
  name: "your_assistant_name"
  description: "Assistant description"
  
  # Choose your AI model
  model:
    name: "gpt-4"  # or "claude-3-opus", "claude-3-sonnet", "ollama:phi4"
    settings:
      temperature: 0.7
      max_tokens: 2000
  
  # Voice settings (if using voice features)
  voice:
    type: "local"  # or "elevenlabs", "realtime-tts"
    settings:
      rate: 1.0
      volume: 1.0

  # Command settings
  commands:
    prefix: ""  # Command prefix if desired
    auto_confirm: false  # Whether to auto-confirm safe commands
```

## 🧠 AI Models

### Available Models

1. **OpenAI Models**
   - GPT-4 (Recommended for complex tasks)
   - GPT-3.5-turbo (Faster, suitable for simpler tasks)

2. **Anthropic Models**
   - Claude-3-opus (Most capable Claude model)
   - Claude-3-sonnet (Balanced performance and speed)

3. **Local Models**
   - Ollama:phi4 (Local execution)
   - Custom models (Configurable)

### Model Configuration

```yaml
# Model-specific settings
models:
  gpt-4:
    temperature: 0.7
    max_tokens: 2000
    top_p: 1.0
    
  claude-3-opus:
    temperature: 0.5
    max_tokens: 4000
    
  ollama:phi4:
    temperature: 0.8
    max_tokens: 1000
```

## 🗄️ Database Configuration

### Supabase Setup

```yaml
# Database settings
database:
  # Connection settings
  pool_size: 5
  max_overflow: 10
  pool_timeout: 30
  
  # Query settings
  statement_timeout: 30000  # milliseconds
  query_timeout: 30000     # milliseconds
  
  # Retry configuration
  max_retries: 3
  retry_interval: 1000     # milliseconds
```

### Connection Management

```python
# Example connection configuration
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    os.getenv("SUPABASE_DATABASE_URL"),
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30
)
```

## ⚡ Command Settings

### Available Commands

The following command groups are available:

1. **Project Management**
   ```bash
   aiden create-project
   aiden list-projects
   aiden assign-project
   ```

2. **Task Management**
   ```bash
   aiden create-task
   aiden list-tasks
   aiden add-task-dependency
   ```

3. **User Management**
   ```bash
   aiden create-user
   aiden list-users
   aiden delete-user
   ```

4. **Data Management**
   ```bash
   aiden generate-report
   aiden filter-records
   aiden backup-data
   ```

### Command Configuration

```yaml
# Command-specific settings
commands:
  # Project settings
  create_project:
    require_confirmation: true
    max_retries: 3
    
  # Task settings
  create_task:
    default_priority: 1
    require_project: false
    
  # User settings
  create_user:
    default_role: "user"
    require_email: true
```

## 📝 Logging

```yaml
# Logging configuration
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  handlers:
    console:
      enabled: true
      level: "INFO"
    file:
      enabled: true
      level: "DEBUG"
      filename: "logs/aiden.log"
      max_bytes: 10485760  # 10MB
      backup_count: 5
```

For more information about specific features, refer to:
- [Database Guide](database-guide.md)
- [SQLAlchemy Guide](sqlalchemy.md)
- [Assistant Guide](assistants.md)

```

python assistant.py stop

python assistant.py run-tool "ls -l"

python assistant.py focus

python assistant.py start --mode cli

python assistant.py start --mode gui

```