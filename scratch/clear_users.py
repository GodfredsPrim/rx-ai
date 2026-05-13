
import sqlite3
conn = sqlite3.connect('rxai.db')
cursor = conn.cursor()

# Get all table names
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall() if row[0] != 'sqlite_sequence']

print(f"Found tables: {tables}")

# Clear main user/pharmacist tables
to_clear = ['pharmacists', 'users', 'profiles', 'prescription_history', 'emergencies', 'chat_history']
for t in to_clear:
    try:
        cursor.execute(f"DELETE FROM {t}")
        print(f"Cleared {t}")
    except Exception as e:
        print(f"Could not clear {t}: {e}")

conn.commit()
conn.close()
print("Operation complete.")
