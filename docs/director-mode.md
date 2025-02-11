# Director Mode

Director Mode is a powerful feature in Aiden that enables self-directed AI coding. It allows you to specify a coding task in a YAML configuration file and let Aiden autonomously work on implementing, testing, and refining the solution.

## Getting Started

There are two main commands for using Director Mode:

```bash
# Create a new director configuration
aiden create-director-config my_task.yml \
    --prompt "Your coding task description" \
    --coder-model gpt-4 \
    --evaluator-model gpt-4o \
    --max-iterations 5

# Install dependencies using uv
uv pip install -r requirements.txt

# Run the director with your config
aiden run-director my_task.yml --verbose
```

## Configuration File

The director config file (`my_task.yml`) defines how the AI should approach your coding task:

```yaml
prompt: |
  # Your coding task description
  Create a function that:
  1. Does X
  2. Handles Y
  3. Returns Z

coder_model: gpt-4        # Model used for coding
evaluator_model: gpt-4o   # Model used for evaluation
max_iterations: 5         # Maximum attempts to improve the code
execution_command: python {file}  # How to run the generated code
context_editable: []      # Files that can be modified
context_read_only: []     # Files to use as reference
evaluator: default        # Evaluation strategy
```

### Configuration Options

- **prompt**: Your coding task description. Can be inline text or a path to a .md file
- **coder_model**: The AI model to use for code generation (e.g., gpt-4, claude-3)
- **evaluator_model**: The AI model to use for code evaluation
- **max_iterations**: Maximum number of attempts to improve the code
- **execution_command**: Command to run the generated code (e.g., "python {file}")
- **context_editable**: List of files that the AI can modify
- **context_read_only**: List of files the AI can read but not modify
- **evaluator**: The evaluation strategy to use (currently only "default" is supported)

## How It Works

1. **Code Generation**: The coder model generates an initial implementation based on your prompt
2. **Execution**: The code is executed using the specified command
3. **Evaluation**: The evaluator model assesses the output and suggests improvements
4. **Iteration**: Steps 1-3 repeat until either:
   - The code passes evaluation
   - Max iterations is reached
   - An unrecoverable error occurs

## Example Usage

Here's a simple example of using Director Mode to create a utility function:

1. Create the config file:
```bash
aiden create-director-config sum_evens.yml \
    --prompt "Create a function that sums even numbers in a list" \
    --coder-model gpt-4 \
    --execution-command "python {file}"
```

2. Run the director:
```bash
aiden run-director sum_evens.yml --verbose
```

The director will work autonomously to:
- Generate the initial implementation
- Test the function with various inputs
- Handle edge cases and errors
- Add proper documentation
- Refine the code until it meets the requirements

## Best Practices

1. **Clear Prompts**: Write detailed, specific prompts that clearly state:
   - Input/output requirements
   - Error handling expectations
   - Performance considerations
   - Documentation requirements

2. **Context Files**: Use context_read_only to provide:
   - Existing utility functions
   - Type definitions
   - Constants and configurations
   - Test cases

3. **Iterations**: Set max_iterations based on:
   - Task complexity
   - Code quality requirements
   - Time constraints

4. **Model Selection**: Choose appropriate models:
   - Use stronger models (gpt-4, claude-3) for complex tasks
   - Use faster models for simpler tasks or prototypes

## Limitations

- Currently supports Python code generation
- Evaluation is based on execution results and basic code quality metrics
- Complex multi-file projects may require manual coordination
- External dependencies must be installed separately
