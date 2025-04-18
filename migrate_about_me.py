import json
from db import get_db, init_db

# File paths for your JSON data.
ABOUT_FILE = "about_me.json"
HEARTS_FILE = "hearts_data.json"

def migrate_about_me_data():
    try:
        with open(ABOUT_FILE, "r") as f:
            about_data = json.load(f)
    except Exception as e:
        print(f"Error loading about_me JSON: {e}")
        return

    # Ensure tables are created before migration.
    init_db()
    
    conn = get_db()
    cursor = conn.cursor()

    for user_id, about_text in about_data.items():
        cursor.execute(
            "INSERT OR REPLACE INTO about_me (user_id, about) VALUES (?, ?)",
            (user_id, about_text)
        )
        print(f"Migrated About Me for user {user_id}: '{about_text}'")
    
    conn.commit()
    conn.close()
    print("About Me data migration completed!")


def migrate_hearts_data():
    try:
        with open(HEARTS_FILE, "r") as f:
            hearts_data = json.load(f)
    except Exception as e:
        print(f"Error loading hearts JSON: {e}")
        return

    # Ensure tables are created before migration.
    init_db()
    
    conn = get_db()
    cursor = conn.cursor()

    for user_id, data in hearts_data.items():
        hearts = data.get("hearts", 0)
        last_given = data.get("last_given", "")
        cursor.execute(
            "INSERT OR REPLACE INTO hearts (user_id, hearts, last_given) VALUES (?, ?, ?)",
            (user_id, hearts, last_given)
        )
        print(f"Migrated Hearts for user {user_id}: hearts={hearts}, last_given='{last_given}'")
    
    conn.commit()
    conn.close()
    print("Hearts data migration completed!")


if __name__ == '__main__':
    print("Starting migration...")
    migrate_about_me_data()
    migrate_hearts_data()
    print("All migrations completed!")

