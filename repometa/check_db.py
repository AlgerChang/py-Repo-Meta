import sqlite3
import json

conn = sqlite3.connect('repometa/repometa.db')
cursor = conn.cursor()
cursor.execute("SELECT name, metadata FROM symbols WHERE name='read_user'")
row = cursor.fetchone()
print(f"Name: {row[0]}")
print(f"Metadata: {row[1]}")
