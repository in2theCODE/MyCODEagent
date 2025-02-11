from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func

# Create a single Base class to be used throughout the application
class Base(DeclarativeBase):
    pass

# Import all models to make them available when importing from models
from .models import CodeSnippet, Note, Reminder, Task
from .project import Project

# Re-export everything
__all__ = ['Base', 'Project', 'CodeSnippet', 'Note', 'Reminder', 'Task']
