import sqlite3
from pathlib import Path

class RepoMetaDB:
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        db_dir = repo_path / ".repometa"
        db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_dir / "repometa.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def setup(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filepath TEXT UNIQUE NOT NULL
            )
        ''')
        # Dropped start_line and end_line for token optimization
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS symbols (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER,
                name TEXT,
                qualname TEXT,
                symbol_type TEXT,
                docstring TEXT,
                FOREIGN KEY(file_id) REFERENCES files(id)
            )
        ''')
        self.conn.commit()

    def clear_all(self):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM files')
        cursor.execute('DELETE FROM symbols')
        self.conn.commit()

    def insert_file(self, filepath: str) -> int:
        cursor = self.conn.cursor()
        cursor.execute('INSERT INTO files (filepath) VALUES (?)', (filepath,))
        self.conn.commit()
        return cursor.lastrowid

    def insert_symbols(self, file_id: int, symbols: list[dict]):
        cursor = self.conn.cursor()
        query = '''
            INSERT INTO symbols 
            (file_id, name, qualname, symbol_type, docstring)
            VALUES (?, ?, ?, ?, ?)
        '''
        for sym in symbols:
            cursor.execute(query, (
                file_id,
                sym['name'],
                sym['qualname'],
                sym['symbol_type'],
                sym.get('docstring')
            ))
        self.conn.commit()

    def get_symbols_by_file(self, filepath: str) -> list[dict]:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT s.name, s.qualname, s.symbol_type, s.docstring
            FROM symbols s
            JOIN files f ON s.file_id = f.id
            WHERE f.filepath = ? OR f.filepath LIKE ?
        ''', (filepath, '%/' + filepath))
        return [dict(row) for row in cursor.fetchall()]
