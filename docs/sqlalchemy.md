# 🗄️ Using SQLAlchemy with Supabase

This guide explains how to use SQLAlchemy with Supabase in Aiden.

## 📋 Prerequisites

- Supabase project and credentials
- PostgreSQL database URL from Supabase
- Python 3.12+

## 🔌 Connection Setup

1. **Environment Variables**

Add your Supabase credentials to `.env`:
```env
SUPABASE_DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres
SUPABASE_URL=https://[YOUR-PROJECT-REF].supabase.co
SUPABASE_KEY=[YOUR-SUPABASE-KEY]
```

2. **Database Connection**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

def get_db_engine():
    database_url = os.getenv("SUPABASE_DATABASE_URL")
    if not database_url:
        raise ValueError("SUPABASE_DATABASE_URL not set in environment")
    return create_engine(database_url)

def get_db_session():
    engine = get_db_engine()
    Session = sessionmaker(bind=engine)
    return Session()
```

## 📝 Model Example

```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String)
    owner_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    owner = relationship("User", back_populates="projects")
    tasks = relationship("Task", back_populates="project")

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"))
    status = Column(String, default="pending")
    
    # Relationships
    project = relationship("Project", back_populates="tasks")
```

## 🛠️ Usage Examples

1. **Create a New Project**
```python
def create_project(name: str, description: str, owner_id: int):
    session = get_db_session()
    try:
        project = Project(
            name=name,
            description=description,
            owner_id=owner_id
        )
        session.add(project)
        session.commit()
        return project
    finally:
        session.close()
```

2. **Query Projects**
```python
def get_user_projects(user_id: int):
    session = get_db_session()
    try:
        return session.query(Project)\
            .filter(Project.owner_id == user_id)\
            .all()
    finally:
        session.close()
```

3. **Update Task Status**
```python
def update_task_status(task_id: int, new_status: str):
    session = get_db_session()
    try:
        task = session.query(Task).get(task_id)
        if task:
            task.status = new_status
            session.commit()
            return True
        return False
    finally:
        session.close()
```

## 🔍 Best Practices

1. **Always Use Session Management**
   - Use context managers or try/finally blocks
   - Close sessions after use
   - Don't share sessions between requests

2. **Use Migrations**
   - Use Alembic for database migrations
   - Version control your schema changes
   - Test migrations before deployment

3. **Error Handling**
```python
from sqlalchemy.exc import SQLAlchemyError

def safe_db_operation():
    session = get_db_session()
    try:
        # Your database operations here
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        raise
    finally:
        session.close()
```

4. **Connection Pooling**
```python
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

## 🚨 Common Issues

1. **Connection Timeouts**
   - Implement retry logic
   - Use connection pooling
   - Check Supabase connection limits

2. **Performance**
   - Use eager loading with `joinedload()`
   - Index frequently queried columns
   - Optimize complex queries

3. **Security**
   - Never expose database credentials
   - Use parameterized queries
   - Implement proper access control