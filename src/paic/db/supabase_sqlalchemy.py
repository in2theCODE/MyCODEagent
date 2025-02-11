import os
from logging import getLogger

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import declarative_base, sessionmaker

logger = getLogger(__name__)
load_dotenv()

# Get Supabase credentials from environment
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")
if not SUPABASE_DB_URL:
    raise ValueError("SUPABASE_DB_URL not found in environment variables")

# Create SQLAlchemy engine
engine = create_engine(SUPABASE_DB_URL)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for declarative models


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables"""
    logger.info("🗄️ Initializing database tables...")
    Base.metadata.create_all(bind=engine)


def get_db_engine():
    database_url = os.getenv("SUPABASE_DATABASE_URL")
    if not database_url:
        raise ValueError("SUPABASE_DATABASE_URL not set in environment")
    return create_engine(database_url)


def get_db_session():
    engine = get_db_engine()
    Session = sessionmaker(bind=engine)
    return Session()


from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()

# Association tables
task_dependencies = Table(
    "task_dependencies",
    Base.metadata,
    Column("task_id", Integer, ForeignKey("tasks.id"), primary_key=True),
    Column("dependent_on_id", Integer, ForeignKey("tasks.id"), primary_key=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)

project_tasks = Table(
    "project_tasks",
    Base.metadata,
    Column("project_id", Integer, ForeignKey("projects.id"), primary_key=True),
    Column("task_id", Integer, ForeignKey("tasks.id"), primary_key=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)

tag_associations = Table(
    "tag_associations",
    Base.metadata,
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
    Column("item_id", Integer, primary_key=True),
    Column("item_type", String(50), primary_key=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="user")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    tasks = relationship("Task", back_populates="user")
    owned_projects = relationship("Project", back_populates="owner")
    goals = relationship("Goal", back_populates="owner")
    calendar_events = relationship("CalendarEvent", back_populates="created_by_user")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    task_name = Column(String(255), nullable=False)
    priority = Column(Integer, nullable=False, default=1)
    status = Column(String(50), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(Integer, ForeignKey("users.id"))

    # Relationships
    user = relationship("User", back_populates="tasks")
    projects = relationship("Project", secondary=project_tasks, back_populates="tasks")
    dependencies = relationship(
        "Task",
        secondary=task_dependencies,
        primaryjoin=id == task_dependencies.c.task_id,
        secondaryjoin=id == task_dependencies.c.dependent_on_id,
        backref="dependent_tasks",
    )


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(50), default="active")
    priority = Column(Integer, default=1)
    owner_id = Column(Integer, ForeignKey("users.id"))
    start_date = Column(Date)
    due_date = Column(Date)
    completed_date = Column(Date)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    owner = relationship("User", back_populates="owned_projects")
    tasks = relationship("Task", secondary=project_tasks, back_populates="projects")
    goals = relationship("Goal", back_populates="project")
    calendar_events = relationship("CalendarEvent", back_populates="project")


class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100))
    status = Column(String(50), default="in_progress")
    target_date = Column(Date)
    completed_date = Column(Date)
    project_id = Column(Integer, ForeignKey("projects.id"))
    owner_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    project = relationship("Project", back_populates="goals")
    owner = relationship("User", back_populates="goals")


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True))
    location = Column(String(255))
    event_type = Column(String(100))
    recurring = Column(String(50))
    project_id = Column(Integer, ForeignKey("projects.id"))
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    project = relationship("Project", back_populates="calendar_events")
    created_by_user = relationship("User", back_populates="calendar_events")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True)
    message = Column(Text, nullable=False)
    level = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
