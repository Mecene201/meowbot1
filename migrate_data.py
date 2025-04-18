import json
from db import get_db, init_db  # Import init_db so we can create tables beforehand

# Paths to your JSON files
LEVELING_FILE = 'leveling_data.json'
USER_DATA_FILE = 'user_data.json'

def migrate_leveling_data():
    try:
        with open(LEVELING_FILE, 'r') as f:
            leveling_data = json.load(f)
    except Exception as e:
        print(f"Error loading leveling JSON: {e}")
        return

    conn = get_db()
    cursor = conn.cursor()
    for user_id, stats in leveling_data.items():
        level = stats.get('level', 1)
        xp = stats.get('xp', 0)
        cursor.execute(
            "INSERT OR REPLACE INTO leveling (user_id, level, xp) VALUES (?, ?, ?)",
            (user_id, level, xp)
        )
        print(f"Migrated leveling for user {user_id}: level={level}, xp={xp}")
    conn.commit()
    conn.close()
    print("Leveling data migration completed.")

def migrate_user_data():
    try:
        with open(USER_DATA_FILE, 'r') as f:
            user_data = json.load(f)
    except Exception as e:
        print(f"Error loading user data JSON: {e}")
        return

    conn = get_db()
    cursor = conn.cursor()
    for user_id, data in user_data.items():
        balance = data.get("balance", 500)
        cursor.execute(
            "INSERT OR REPLACE INTO users (user_id, balance) VALUES (?, ?)",
            (user_id, balance)
        )
        # Migrate additional parts such as inventory if needed.
        if 'inventory' in data:
            for item in data['inventory']:
                cursor.execute("""
                    INSERT OR REPLACE INTO inventory (user_id, item, item_id, emoji, amount)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, item['item'], item['id'], item['emoji'], item.get('amount', 1)))
        print(f"Migrated user data for user {user_id}: balance={balance}")
    conn.commit()
    conn.close()
    print("User data migration completed.")

if __name__ == '__main__':
    print("Starting migration...")
    # Initialize all database tables so that the 'leveling' table is created.
    init_db()
    migrate_leveling_data()
    migrate_user_data()
    print("All migrations completed!")

