from pathlib import Path
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_project_dir(base_path: str | Path = None) -> Path:
    """
    Set up a project directory structure and return the project root path.

    Args:
        base_path: Optional base directory path. If None, uses the parent
                  directory of the calling script.

    Returns:
        Path: Project root directory path
    """
    # If no base path provided, get the parent directory of the calling script
    if base_path is None:
        project_dir = Path(__file__).resolve().parent.parent
    else:
        project_dir = Path(base_path).resolve()

    # Create standard project directories
    directories = [
        "data",
        "data/raw",
        "data/processed",
        "models",
        "models/checkpoints",
        "configs",
        "src",
        "src/utils",
        "src/preprocessing",
        "src/training",
        "notebooks",
        "logs",
        "tests"
    ]

    for dir_path in directories:
        full_path = project_dir / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created directory: {full_path}")

    # Create basic gitignore if it doesn't exist
    gitignore_path = project_dir / ".gitignore"
    if not gitignore_path.exists():
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

# Environments
.env
.venv
env/
venv/
ENV/

# Data and models
data/raw/*
data/processed/*
models/checkpoints/*

# Logs
logs/*
*.log

# Notebooks
.ipynb_checkpoints
"""
        gitignore_path.write_text(gitignore_content.strip())
        logger.info(f"Created .gitignore at: {gitignore_path}")

    return project_dir


if __name__ == "__main__":
    # Example usage
    project_path = setup_project_dir()
    print(f"Project directory set up at: {project_path}")