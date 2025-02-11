import enum
from logging import getLogger
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from . import Base

logger = getLogger(__name__)


class UserRole(enum.Enum):
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True)
    full_name = Column(String)
    role = Column(Enum(UserRole), default=UserRole.USER)
    preferences = Column(JSON)  # Store user preferences (theme, settings, etc.)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    projects = relationship("Project", back_populates="owner")
    code_snippets = relationship("CodeSnippet", back_populates="owner")
    tasks = relationship("Task", back_populates="owner")
    notes = relationship("Note", back_populates="owner")
    reminders = relationship("Reminder", back_populates="owner")
    assigned_tasks = relationship("Task", back_populates="assignee")

    @classmethod
    def get_all(cls, db):
        """Get all records"""
        return db.query(cls).all()

    @classmethod
    def get_by_id(cls, db, id: int):
        """Get record by ID"""
        return db.query(cls).filter(cls.id == id).first()

    @classmethod
    def create(cls, db, **kwargs):
        """Create a new user"""
        logger.info(f"👤 Creating new user: {kwargs.get('username')}")
        user = cls(**kwargs)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @classmethod
    def get_by_username(cls, db, username: str):
        """Get user by username"""
        return db.query(cls).filter(cls.username == username).first()


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    owner_id = Column(Integer, ForeignKey("users.id"))
    repository_url = Column(String)  # Git repository URL
    language = Column(String)  # Primary programming language
    framework = Column(String)  # Primary framework used
    start_date = Column(DateTime)
    due_date = Column(DateTime)
    status = Column(String, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="projects")
    code_snippets = relationship("CodeSnippet", back_populates="project")
    tasks = relationship("Task", secondary="project_tasks", back_populates="projects")

    @classmethod
    def create(cls, db, **kwargs):
        """Create a new project"""
        logger.info(f"📝 Creating new project: {kwargs.get('name')}")
        project = cls(**kwargs)
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    @classmethod
    def get_all(cls, db):
        """Get all projects"""
        return db.query(cls).all()

    @classmethod
    def get_by_id(cls, db, project_id: int):
        """Get project by ID"""
        return db.query(cls).filter(cls.id == project_id).first()

    @classmethod
    def get_user_projects(cls, db, user_id: int):
        """Get all projects for a user"""
        return db.query(cls).filter(cls.owner_id == user_id).all()


class CodeSnippet(Base):
    __tablename__ = "code_snippets"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    code = Column(Text, nullable=False)
    language = Column(String)  # Programming language
    description = Column(Text)
    tags = Column(JSON)  # Store tags as JSON array
    owner_id = Column(Integer, ForeignKey("users.id"))
    project_id = Column(Integer, ForeignKey("projects.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="code_snippets")
    project = relationship("Project", back_populates="code_snippets")

    @classmethod
    def create(cls, db, **kwargs):
        """Create a new record"""
        logger.info(
            f"Creating new {cls.__name__}: {kwargs.get('title', kwargs.get('name', ''))}"
        )
        obj = cls(**kwargs)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    @classmethod
    def get_all(cls, db):
        """Get all records"""
        return db.query(cls).all()

    @classmethod
    def get_by_id(cls, db, id: int):
        """Get record by ID"""
        return db.query(cls).filter(cls.id == id).first()


project_tasks = Table(
    'project_tasks',
    Base.metadata,
    Column('project_id', Integer, ForeignKey('projects.id'), primary_key=True),
    Column('task_id', Integer, ForeignKey('tasks.id'), primary_key=True)
)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_name = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(50), default="pending")
    priority = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    due_date = Column(DateTime)
    assigned_to = Column(Integer, ForeignKey("users.id"))
    
    # Relationships
    projects = relationship("Project", secondary=project_tasks, back_populates="tasks")
    assignee = relationship("User", back_populates="assigned_tasks")
    owner = relationship("User", back_populates="tasks")
    subtasks = relationship("Task", back_populates="parent_task")
    parent_task = relationship("Task", back_populates="subtasks")
    dependencies = relationship(
        "Task",
        secondary="task_dependencies",
        primaryjoin="Task.id==task_dependencies.c.task_id",
        secondaryjoin="Task.id==task_dependencies.c.dependent_on_id",
        backref="dependent_tasks"
    )

    @classmethod
    def create(cls, db, **kwargs):
        """Create a new record"""
        logger.info(
            f"Creating new {cls.__name__}: {kwargs.get('title', kwargs.get('name', ''))}"
        )
        obj = cls(**kwargs)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    @classmethod
    def get_all(cls, db):
        """Get all records"""
        return db.query(cls).all()

    @classmethod
    def get_by_id(cls, db, taskid: int):
        """Get record by ID"""
        return db.query(cls).filter(cls.id == taskid).first()


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text)
    tags = Column(JSON)  # Store tags as JSON array
    owner_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="notes")

    @classmethod
    def create(cls, db, **kwargs):
        """Create a new record"""
        logger.info(
            f"Creating new {cls.__name__}: {kwargs.get('title', kwargs.get('name', ''))}"
        )
        obj = cls(**kwargs)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    @classmethod
    def get_all(cls, db):
        """Get all records"""
        return db.query(cls).all()

    @classmethod
    def get_by_id(cls, db, id: int):
        """Get record by ID"""
        return db.query(cls).filter(cls.id == id).first()


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    due_date = Column(DateTime, nullable=False)
    repeat_interval = Column(String)  # daily, weekly, monthly, etc.
    is_completed = Column(Boolean, default=False)
    owner_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="reminders")

    @classmethod
    def create(cls, db, **kwargs):
        """Create a new record"""
        logger.info(
            f"Creating new {cls.__name__}: {kwargs.get('title', kwargs.get('name', ''))}"
        )
        obj = cls(**kwargs)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    @classmethod
    def get_all(cls, db):
        """Get all records"""
        return db.query(cls).all()

    @classmethod
    def get_by_id(cls, db, id: int):
        """Get record by ID"""
        return db.query(cls).filter(cls.id == id).first()
