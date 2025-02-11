import logging
import os
from typing import Optional

import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT, connection
from supabase import Client, create_client

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


def get_supabase_client() -> Optional[Client]:
    """Get a Supabase client instance."""
    try:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")

        if not url or not key:
            logger.error("Missing Supabase credentials")
            return None

        return create_client(url, key)
    except Exception as e:
        logger.error(f"Failed to create Supabase client: {e}")
        return None


def get_db_connection() -> connection:
    """Create a connection to PostgreSQL using environment variables."""
    try:
        # Try Supabase connection first
        supabase_db = os.getenv("SUPABASE_DATABASE", "postgres")
        supabase_user = os.getenv("SUPABASE_USER")
        supabase_password = os.getenv("SUPABASE_PASSWORD")
        supabase_host = os.getenv("SUPABASE_HOST")

        if all([supabase_db, supabase_user, supabase_password, supabase_host]):
            conn = psycopg2.connect(
                dbname=supabase_db,
                user=supabase_user,
                password=supabase_password,
                host=supabase_host,
                port=os.getenv("POSTGRES_PORT", "5432"),
            )
        else:
            # Fallback to regular PostgreSQL connection
            conn = psycopg2.connect(
                dbname=os.getenv("POSTGRES_DB"),
                user=os.getenv("POSTGRES_USER"),
                password=os.getenv("POSTGRES_PASSWORD"),
                host=os.getenv("POSTGRES_HOST"),
                port=os.getenv("POSTGRES_PORT", "5432"),
            )

        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        return conn
    except psycopg2.Error as e:
        logger.error(f"Failed to connect to database: {e}")
        raise


def validate_db_config() -> bool:
    """Validate that all required database environment variables are set."""
    # Check Supabase credentials first
    supabase_vars = [
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "SUPABASE_DATABASE",
        "SUPABASE_USER",
        "SUPABASE_PASSWORD",
        "SUPABASE_HOST",
    ]

    if all(os.getenv(var) for var in supabase_vars):
        return True

    # Fallback to checking PostgreSQL credentials
    postgres_vars = [
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
    ]

    missing = [var for var in postgres_vars if not os.getenv(var)]

    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        return False

    return True


from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
