import sqlite3
import os
from typing import Optional, List, Dict
from datetime import datetime

DB_PATH = "safemind.db"

def get_db_connection():
    """Get a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize database with required tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            location TEXT NOT NULL,
            gender TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Chats table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES chats(id)
        )
    """)
    
    conn.commit()
    conn.close()
    print("✓ Database initialized", flush=True)

# User operations
def create_user(email: str, name: str, age: int, location: str, gender: str, password_hash: str) -> Optional[int]:
    """Create a new user."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (email, name, age, location, gender, password_hash)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (email, name, age, location, gender, password_hash))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        return None

def get_user_by_email(email: str) -> Optional[Dict]:
    """Get user by email."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Get user by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# Chat operations
def create_chat(chat_id: str, user_id: int, title: str) -> bool:
    """Create a new chat."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO chats (id, user_id, title)
            VALUES (?, ?, ?)
        """, (chat_id, user_id, title))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def get_user_chats(user_id: int) -> List[Dict]:
    """Get all chats for a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM chats 
        WHERE user_id = ? 
        ORDER BY created_at DESC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_chat_by_id(chat_id: str) -> Optional[Dict]:
    """Get chat by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chats WHERE id = ?", (chat_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_chat_title(chat_id: str, title: str):
    """Update chat title."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE chats SET title = ? WHERE id = ?", (title, chat_id))
    conn.commit()
    conn.close()

# Message operations
def add_message(chat_id: str, role: str, content: str) -> bool:
    """Add a message to a chat."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO messages (chat_id, role, content)
            VALUES (?, ?, ?)
        """, (chat_id, role, content))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def get_chat_messages(chat_id: str) -> List[Dict]:
    """Get all messages for a chat."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM messages 
        WHERE chat_id = ? 
        ORDER BY created_at ASC
    """, (chat_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
