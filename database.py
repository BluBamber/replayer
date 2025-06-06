#!/usr/bin/env python3
"""
ROBLOX Game Replay System - Database Module
"""

import os
import json
import sqlite3
import time

# Database configuration
DATABASE = 'roblox_replays.db'

def init_db():
    """Initialize the SQLite database"""
    print("Initializing database...")
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS servers (
            server_id TEXT PRIMARY KEY,
            place_id INTEGER,
            creator_id INTEGER,
            game_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_frame INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS frames (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            server_id TEXT,
            frame_number INTEGER,
            timestamp REAL,
            parts_data TEXT,
            players_data TEXT,
            game_info TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (server_id) REFERENCES servers (server_id)
        )
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_server_frame ON frames (server_id, frame_number)
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_db_exists():
    """Ensure database exists and is initialized"""
    if not os.path.exists(DATABASE):
        print("Database file doesn't exist, creating...")
        init_db()
    else:
        # Check if tables exist
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='frames'")
            if not cursor.fetchone():
                print("Tables don't exist, initializing...")
                conn.close()
                init_db()
            else:
                conn.close()
                print("Database already exists and is properly initialized")
        except Exception as e:
            print(f"Error checking database: {e}")
            print("Reinitializing database...")
            init_db() 