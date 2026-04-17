
import sqlite3
conn = sqlite3.connect('database.db')
cursor = conn.cursor()
cursor.execute("SELECT id, username, email, is_admin FROM users WHERE is_admin = 1")
rows = cursor.fetchall()
for row in rows:
    print(row)
conn.close()
