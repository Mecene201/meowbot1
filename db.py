import sqlite3

def get_db():
    return sqlite3.connect("economy.db")

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            balance INTEGER DEFAULT 500
        )
    """)

    # Inventory table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            user_id TEXT,
            item TEXT,
            item_id INTEGER,
            emoji TEXT,
            amount INTEGER,
            UNIQUE(user_id, item_id)
        )
    """)

    # Upgrades table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS upgrades (
            user_id TEXT,
            upgrade_key TEXT,
            level INTEGER,
            PRIMARY KEY(user_id, upgrade_key)
        )
    """)

    # Cooldowns table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cooldowns (
            user_id TEXT,
            type TEXT,
            timestamp REAL,
            PRIMARY KEY(user_id, type)
        )
    """)

    # Leveling table for storing level and XP
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leveling (
            user_id TEXT PRIMARY KEY,
            level INTEGER DEFAULT 1,
            xp INTEGER DEFAULT 0
        )
    """)

    # About Me table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS about_me (
            user_id TEXT PRIMARY KEY,
            about TEXT DEFAULT ''
        )
    """)

    # Hearts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hearts (
            user_id TEXT PRIMARY KEY,
            hearts INTEGER DEFAULT 0,
            last_given TEXT DEFAULT ''
        )
    """)

    # Profile Backgrounds table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profile_backgrounds (
            user_id TEXT PRIMARY KEY,
            backgrounds TEXT DEFAULT '["default"]',
            equipped_bg TEXT DEFAULT 'default'
        )
    """)

    # Confession Configuration table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS confession_config (
            guild_id TEXT PRIMARY KEY,
            channel_id TEXT NOT NULL
        )
    """)
    
    conn.commit()
    conn.close()
