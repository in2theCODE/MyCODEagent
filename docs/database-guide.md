# 🗄️ Database Guide

Complete guide to Aiden's database system using Supabase and SQLAlchemy.

## 📑 Table of Contents

- [Setup and Configuration](#setup-and-configuration)
- [Database Architecture](#database-architecture)
- [Command Reference](#command-reference)
- [Data Models](#data-models)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## ⚙️ Setup and Configuration

### Environment Variables

```env
# Supabase Configuration
SUPABASE_DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres
SUPABASE_URL=https://[YOUR-PROJECT-REF].supabase.co
SUPABASE_KEY=[YOUR-SUPABASE-KEY]
```

### Database Connection

```python
def get_connection():
    """Connect to PostgreSQL (Supabase)"""
    return psycopg2.connect(os.getenv("SUPABASE_DATABASE_URL"))

def get_supabase_client():
    """Get Supabase client for additional features"""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if not all([supabase_url, supabase_key]):
        raise ValueError("Supabase credentials not configured")
    return create_client(supabase_url, supabase_key)
```

## 🏗️ Database Architecture

### System Overview

```mermaid
graph TD
    A[Aiden CLI] --> B[SQLAlchemy ORM]
    B --> C[Supabase PostgreSQL]
    A --> D[Supabase Client]
    D --> C
```

### Key Components

- **Supabase**: Cloud PostgreSQL database service
- **SQLAlchemy**: ORM for database operations
- **Connection Pool**: Managed by Supabase
- **psycopg2**: PostgreSQL adapter for Python

## 🛠️ Command Reference

### Project Management

```bash
# Create a new project
aiden create-project "My Project" --description "Project description" --owner-id 1

# List projects
aiden list-projects
aiden list-projects --status active
aiden list-projects --owner-id 1

# Assign project
aiden assign-project 1 2  # Assign project 1 to user 2
```

### Task Management

```bash
# Create a task
aiden create-task "Implement feature" --description "Details" --priority 2

# List tasks
aiden list-tasks
aiden list-tasks --status pending
aiden list-tasks --user-id 1

# Task dependencies
aiden add-task-dependency 2 1  # Task 2 depends on Task 1

# Project tasks
aiden list-project-tasks 1  # List tasks for project 1
```

### User Management

```bash
# Create a user
aiden create-user "username" --role developer

# List users
aiden list-users
aiden list-users --role admin
aiden list-users --sort created_at

# Delete user
aiden delete-user 1 --confirm
```

### Data Management

```bash
# Generate reports
aiden generate-report users --output users_report.json

# Filter records
aiden filter-records users --query "admin" --limit 5

# Backup data
aiden backup-data ./backups --full
```

## 📊 Data Models

### Core Tables

```sql
-- Projects
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    owner_id INTEGER REFERENCES users(id),
    start_date DATE,
    due_date DATE,
    priority INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tasks
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    project_id INTEGER REFERENCES projects(id),
    status VARCHAR(50) DEFAULT 'pending',
    priority INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Task Dependencies
CREATE TABLE task_dependencies (
    task_id INTEGER REFERENCES tasks(id),
    depends_on_id INTEGER REFERENCES tasks(id),
    PRIMARY KEY (task_id, depends_on_id)
);
```

## ✨ Best Practices

### 1. Connection Management

```python
def safe_db_operation():
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Your operations here
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
```

### 2. Error Handling

```python
from psycopg2 import Error as PostgresError

try:
    # Database operations
    conn.commit()
except PostgresError as e:
    print(f"Database error: {e}")
    conn.rollback()
```

### 3. Query Optimization

- Use prepared statements
- Create appropriate indexes
- Keep transactions short
- Use connection pooling

### 4. Security

- Never store credentials in code
- Use parameterized queries
- Implement proper access control
- Regular security audits

## 🔍 Troubleshooting

### Common Issues

1. **Connection Errors**
   - Check Supabase credentials
   - Verify network connectivity
   - Check connection limits

2. **Performance Issues**
   - Monitor query performance
   - Check index usage
   - Review connection pooling

3. **Data Consistency**
   - Use transactions properly
   - Implement proper error handling
   - Regular data validation

### Debugging Tips

1. **Enable Query Logging**
   ```python
   import logging
   logging.basicConfig()
   logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
   ```

2. **Connection Test**
   ```python
   def test_connection():
       try:
           conn = get_connection()
           cur = conn.cursor()
           cur.execute("SELECT 1")
           return True
       except Exception as e:
           print(f"Connection test failed: {e}")
           return False
       finally:
           cur.close()
           conn.close()
   ```

For more detailed SQLAlchemy usage, see [SQLAlchemy Guide](sqlalchemy.md)
