#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Ensure we're in the project root
cd "$PROJECT_ROOT"

# Check if Python virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run setup.sh first."
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Install required packages if not already installed
pip install -q inquirer colorama pyyaml

# Run the Python script
python "$SCRIPT_DIR/create_assistant_impl.py" "$@"

# Deactivate virtual environment
deactivate
