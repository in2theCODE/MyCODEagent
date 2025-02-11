# 🚀 Getting Started with Aiden

This guide will help you set up and start using Aiden, your AI-powered coding assistant built on top of aiden.

## 📋 Prerequisites

- Python 3.12 or higher
- OpenAI API key (for GPT-4 based assistants)
- Supabase account and project (for database features)
- `uv` package manager (for dependency management)

## 🔧 Installation

1. **Install with pip**
   ```bash
   pip install aiden-assistant
   ```

2. **Environment Setup**
   ```bash
   # Create a new directory for your project
   mkdir my-aiden-project
   cd my-aiden-project
   
   # Create and activate virtual environment
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate

   # Create environment file
   touch .env
   ```
   
   Add your credentials to `.env`:
   ```env
   # Supabase Configuration
   SUPABASE_DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres
   SUPABASE_URL=https://[YOUR-PROJECT-REF].supabase.co
   SUPABASE_KEY=[YOUR-SUPABASE-KEY]

   # OpenAI Configuration (for GPT-4 based assistants)
   OPENAI_API_KEY=your_openai_api_key

   # Optional: Other AI Provider Keys
   ANTHROPIC_API_KEY=your_anthropic_key  # For Claude models
   ELEVEN_LABS_API_KEY=your_eleven_labs_key  # For voice synthesis
   ```

## 🚀 Starting Aiden

1. **Initialize the Database**
   ```bash
   aiden init-db
   ```

2. **Start the Assistant**
   ```bash
   # Start with default configuration
   aiden start

   # Or start with a specific configuration
   aiden start --config path/to/config.yml
   ```

## 🎯 Creating Your Assistant

Choose one of these methods to create and configure your AI assistant:

1. **Interactive Setup**
   ```bash
   aiden create-assistant
   ```
   This will guide you through:
   - Assistant name and description
   - AI model selection
   - Voice preferences (if using voice features)
   - Database configuration

2. **Use Pre-configured Templates**
   ```bash
   # For a GPT-4 based assistant
   aiden create-assistant --template gpt4

   # For a Claude-based assistant
   aiden create-assistant --template claude

   # For a local model assistant
   aiden create-assistant --template local
   ```

## 🛠️ Basic Commands

Here are some essential commands to get started:

```bash
# Create a new project
aiden create-project "My Project"

# List all projects
aiden list-projects

# Create a new task
aiden create-task "Task Description" --project "My Project"

# List all tasks
aiden list-tasks
```

## 🔍 Troubleshooting

1. **Database Connection Issues**
   - Verify your Supabase credentials in `.env`
   - Ensure your Supabase project is active
   - Check network connectivity to Supabase

2. **Assistant Creation Issues**
   - Confirm all required API keys are set
   - Verify Python version (3.12+)
   - Check for any error messages in the logs

3. **Command Execution Issues**
   - Ensure virtual environment is activated
   - Verify database is initialized
   - Check command syntax and arguments

## 📚 Next Steps

- [Database Guide](database-guide.md) - Learn about database operations
- [SQLAlchemy Guide](sqlalchemy.md) - Understand the ORM layer
- [Configuration Guide](configuration.md) - Customize your setup
- [Assistant Guide](assistants.md) - Advanced assistant features

## 🆘 Getting Help

- Visit our [GitHub Issues](https://github.com/aiden-AI/aiden/issues)
- Check the logs in `logs/aiden.log`
- Review the documentation in the `docs/` directory
