import sqlite3
import json

def verify():
    conn = sqlite3.connect('repometa.db')
    cursor = conn.cursor()

    print("--- Database Statistics ---")
    cursor.execute("SELECT COUNT(*) FROM files")
    print(f"Files parsed: {cursor.fetchone()[0]}")

    cursor.execute("SELECT COUNT(*) FROM symbols")
    print(f"Symbols extracted: {cursor.fetchone()[0]}")

    cursor.execute("SELECT COUNT(*) FROM edges")
    print(f"Edges extracted: {cursor.fetchone()[0]}")

    cursor.execute("SELECT COUNT(*) FROM dependencies")
    print(f"Dependencies tracked: {cursor.fetchone()[0]}")

    print("\\n--- Sample Symbols ---")
    cursor.execute("SELECT symbol_type, name, qualname, metadata FROM symbols LIMIT 10")
    for row in cursor.fetchall():
        meta = json.loads(row[3]) if row[3] else {}
        print(f"[{row[0].upper()}] {row[2]}")
        if meta:
            print(f"  Metadata: {meta}")

    print("\\n--- Sample Edges ---")
    cursor.execute("SELECT edge_type, target_qualname FROM edges LIMIT 10")
    for row in cursor.fetchall():
        print(f"[{row[0].upper()}] -> {row[1]}")

    conn.close()

if __name__ == '__main__':
    verify()