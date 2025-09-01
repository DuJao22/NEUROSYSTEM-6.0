"""Database utilities for SQLite compatibility"""
import sqlite3
import logging
from database import get_db_connection


def get_cursor():
    """Get a database connection with Row factory for dict-like access"""
    # Note: This function is deprecated, use get_db_connection() context manager instead
    conn = sqlite3.connect('neuropsychology.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    return conn, cursor


def execute_query(query, params=None):
    """Execute a query and return results with proper error handling"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            return cursor.fetchall()
    except sqlite3.Error as e:
        logging.error(f"Database query error: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error in execute_query: {e}")
        raise


def execute_single_query(query, params=None):
    """Execute a query and return single result"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            return cursor.fetchone()
    except sqlite3.Error as e:
        logging.error(f"Database query error: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error in execute_single_query: {e}")
        raise


def execute_update(query, params=None):
    """Execute an update/insert query"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            conn.commit()
            return cursor.rowcount
    except sqlite3.Error as e:
        logging.error(f"Database update error: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error in execute_update: {e}")
        raise