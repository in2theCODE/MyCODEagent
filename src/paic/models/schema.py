import os

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Table, UniqueConstraint
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

# Association tables
project_tasks = Table(
    'project_tasks',
    Base.metadata,
    Column('project_id', Integer, ForeignKey('projects.id'), primary_key=True),
    Column('task_id', Integer, ForeignKey('tasks.id'), primary_key=True)
)


# Models
class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True)
    role = Column(String(50), default='user')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    projects = relationship("Project", back_populates="owner")
    tasks = relationship("Task", back_populates="assigned_user")


class Project(Base):
    __tablename__ = 'projects'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    owner_id = Column(Integer, ForeignKey('users.id'))
    status = Column(String(50), default='active')
    priority = Column(Integer, default=3)
    start_date = Column(DateTime(timezone=True))
    due_date = Column(DateTime(timezone=True))
    completed_date = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="projects")
    tasks = relationship("Task", secondary=project_tasks, back_populates="projects")
    goals = relationship("Goal", back_populates="project")
    events = relationship("CalendarEvent", back_populates="project")

    @classmethod
    def get_by_project_name(cls, name: str):
        """Get a project by name"""
        from sqlalchemy.orm import Session
        from sqlalchemy import create_engine

        engine = create_engine(os.getenv("SUPABASE_DATABASE_URL"))
        session = Session(engine)
        return session.query(cls).filter(cls.name == name).first()

    @classmethod
    def get_all(cls):
        """Get all projects"""
        from sqlalchemy.orm import Session
        from sqlalchemy import create_engine

        engine = create_engine(os.getenv("SUPABASE_DATABASE_URL"))
        session = Session(engine)
        return session.query(cls).all()

    @classmethod
    def get_by_project_id(cls, user_id: int):
        from sqlalchemy.orm import Session
        from sqlalchemy import create_engine

        engine = create_engine(os.getenv("SUPABASE_DATABASE_URL"))
        session = Session(engine)
        return session.query(cls).filter(cls.owner_id == user_id).all()

    @classmethod
    def get_by_status(cls, status: str):
        from sqlalchemy.orm import Session
        from sqlalchemy import create_engine

        engine = create_engine(os.getenv("SUPABASE_DATABASE_URL"))
        session = Session(engine)
        return session.query(cls).filter(cls.status == status).all()

    @classmethod
    def get_by_priority(cls, priority: int):
        from sqlalchemy.orm import Session
        from sqlalchemy import create_engine

        engine = create_engine(os.getenv("SUPABASE_DATABASE_URL"))
        session = Session(engine)
        return session.query(cls).filter(cls.priority == priority).all()


class Task(Base):
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    priority = Column(Integer, default=3)
    status = Column(String(50), default='pending')
    user_id = Column(Integer, ForeignKey('users.id'))
    due_date = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    assigned_user = relationship("User", back_populates="tasks")
    projects = relationship("Project", secondary=project_tasks, back_populates="tasks")
    dependencies = relationship(
        "Task",
        secondary="task_dependencies",
        primaryjoin="Task.id==task_dependencies.c.task_id",
        secondaryjoin="Task.id==task_dependencies.c.dependent_on_id",
        backref="dependent_tasks"
    )

    __table_args__ = (
        UniqueConstraint('title', 'user_id', name='unique_title_per_user'),
    )

    @classmethod
    def get_by_name(cls, name: str):
        """Get a task by name"""
        from sqlalchemy.orm import Session
        from sqlalchemy import create_engine

        engine = create_engine(os.getenv("SUPABASE_DATABASE_URL"))
        session = Session(engine)
        return session.query(cls).filter(cls.title == name).first()

    @classmethod
    def get_all(cls):
        """Get all tasks"""
        from sqlalchemy.orm import Session
        from sqlalchemy import create_engine

        engine = create_engine(os.getenv("SUPABASE_DATABASE_URL"))
        session = Session(engine)
        return session.query(cls).all()

    @classmethod
    def get_by_task_id(cls, user_id: int):
        from sqlalchemy.orm import Session
        from sqlalchemy import create_engine

        engine = create_engine(os.getenv("SUPABASE_DATABASE_URL"))
        session = Session(engine)
        return session.query(cls).filter(cls.user_id == user_id).all()

    @classmethod
    def get_all_tasks_attached_to_project_id(cls, project_id: int, task_id: int):
        from sqlalchemy.orm import Session
        from sqlalchemy import create_engine

        engine = create_engine(os.getenv("SUPABASE_DATABASE_URL"))
        session = Session(engine)
        return session.query(cls).filter(cls.projects.any(id=project_id)).all()

    @classmethod
    def get_tasks_for_project_by_status(cls, status: str):
        from sqlalchemy.orm import Session
        from sqlalchemy import create_engine

        engine = create_engine(os.getenv("SUPABASE_DATABASE_URL"))
        session = Session(engine)
        return session.query(cls).filter(cls.status == status).all()

    @classmethod
    def get_by_priority(cls, priority: int):
        from sqlalchemy.orm import Session
        from sqlalchemy import create_engine

        engine = create_engine(os.getenv("SUPABASE_DATABASE_URL"))
        session = Session(engine)
        return session.query(cls).filter(cls.priority == priority).all()

    @classmethod
    def get_by_due_date(cls, due_date: str):
        from sqlalchemy.orm import Session
        from sqlalchemy import create_engine

        engine = create_engine(os.getenv("SUPABASE_DATABASE_URL"))
        session = Session(engine)
        return session.query(cls).filter(cls.due_date == due_date).all()


class TaskDependency(Base):
    __tablename__ = 'task_dependencies'

    task_id = Column(Integer, ForeignKey('tasks.id'), primary_key=True)
    dependent_on_id = Column(Integer, ForeignKey('tasks.id'), primary_key=True)
    dependency_type = Column(String(50), default='blocks')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('task_id', 'dependent_on_id', name='unique_dependency'),
    )

    @classmethod
    def get_all(cls):
        """Get all task dependencies"""
        from sqlalchemy.orm import Session
        from sqlalchemy import create_engine

        engine = create_engine(os.getenv("SUPABASE_DATABASE_URL"))
        session = Session(engine)
        return session.query(cls).all()

    @classmethod
    def get_by_task_id(cls, task_id: int):
        from sqlalchemy.orm import Session
        from sqlalchemy import create_engine

        engine = create_engine(os.getenv("SUPABASE_DATABASE_URL"))
        session = Session(engine)
        return session.query(cls).filter(cls.task_id == task_id).all()

    @classmethod
    def get_by_dependent_on_id(cls, dependent_on_id: int):
        from sqlalchemy.orm import Session
        from sqlalchemy import create_engine

        engine = create_engine(os.getenv("SUPABASE_DATABASE_URL"))
        session = Session(engine)
        return session.query(cls).filter(cls.dependent_on_id == dependent_on_id).all()


class CalendarEvent(Base):
    __tablename__ = 'calendar_events'

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    location = Column(String(255))
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True))
    event_type = Column(String(50), default='meeting')
    project_id = Column(Integer, ForeignKey('projects.id'))
    recurring = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    project = relationship("Project", back_populates="events")


class Goal(Base):
    __tablename__ = 'goals'

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100))
    target_date = Column(DateTime(timezone=True))
    project_id = Column(Integer, ForeignKey('projects.id'))
    status = Column(String(50), default='active')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    project = relationship("Project", back_populates="goals")


class Tag(Base):
    __tablename__ = 'tags'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    color = Column(String(7))  # Hex color code
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class TagAssociation(Base):
    __tablename__ = 'tag_associations'

    id = Column(Integer, primary_key=True)
    tag_id = Column(Integer, ForeignKey('tags.id'))
    item_id = Column(Integer, nullable=False)
    item_type = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('tag_id', 'item_id', 'item_type', name='unique_tag_item'),
    )


# Helper methods for models
@classmethod
def get_by_name(cls, name: str):
    """Get a record by name"""
    from sqlalchemy.orm import Session
    from sqlalchemy import create_engine

    engine = create_engine(os.getenv("SUPABASE_DATABASE_URL"))
    session = Session(engine)
    return session.query(cls).filter(cls.name == name).first()


@classmethod
def get_all(cls):
    """Get all records"""
    from sqlalchemy.orm import Session
    from sqlalchemy import create_engine

    engine = create_engine(os.getenv("SUPABASE_DATABASE_URL"))
    session = Session(engine)
    return session.query(cls).all()


# Add helper methods to relevant classes
for cls in [Project, Task, User]:
    cls.get_by_name = get_by_name
    cls.get_all = get_all