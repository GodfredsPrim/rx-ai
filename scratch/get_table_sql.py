
import sqlite3
conn = sqlite3.connect('rxai.db')
cursor = conn.cursor()
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='pharmacists'")
print(cursor.fetchone()[0])
conn.close()
