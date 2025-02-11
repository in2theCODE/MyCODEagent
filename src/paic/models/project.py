from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from models.models import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    owner_id = Column(Integer, ForeignKey("users.id"))
    repository_url = Column(String)
    language = Column(String)
    framework = Column(String)
    start_date = Column(DateTime)
    due_date = Column(DateTime)
    status = Column(String, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="projects")
    tasks = relationship("Task", back_populates="project")

    @classmethod
    def create(cls, db, **kwargs):
        """Create a new project."""
        project = cls(**kwargs)
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    @classmethod
    def get_all(cls, db):
        """Get all projects."""
        return db.query(cls).all()

    @classmethod
    def get_by_id(cls, db, project_id: int):
        """Get project by ID."""
        return db.query(cls).filter(cls.id == project_id).first()

    @classmethod
    def get_user_projects(cls, db, user_id: int):
        """Get all projects for a user."""
        return db.query(cls).filter(cls.owner_id == user_id).all()
