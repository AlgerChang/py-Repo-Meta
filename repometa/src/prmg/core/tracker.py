import sqlite3
from pathlib import Path
from typing import Set

class DependencyTracker:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS dependencies (
                    from_path TEXT NOT NULL,
                    to_module TEXT NOT NULL,
                    PRIMARY KEY (from_path, to_module)
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_to_module ON dependencies(to_module)')

    def update_relations(self, file_path: str, imports: Set[str], conn: sqlite3.Connection = None):
        managed_conn = False
        if conn is None:
            conn = sqlite3.connect(self.db_path)
            managed_conn = True
            
        try:
            conn.execute('DELETE FROM dependencies WHERE from_path = ?', (file_path,))
            if imports:
                conn.executemany(
                    'INSERT OR IGNORE INTO dependencies (from_path, to_module) VALUES (?, ?)',
                    [(file_path, imp) for imp in imports]
                )
            if managed_conn:
                conn.commit()
        finally:
            if managed_conn:
                conn.close()

    def get_dependents(self, file_path: str, project_root: str) -> Set[str]:
        module_fqn = self._get_module_fqn(project_root, file_path)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT from_path FROM dependencies 
                WHERE to_module = ? OR to_module LIKE ?
            ''', (module_fqn, f"{module_fqn}.%"))
            return {row[0] for row in cursor.fetchall()}

    def remove_file(self, file_path: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM dependencies WHERE from_path = ?', (file_path,))

    @staticmethod
    def _get_module_fqn(project_root: str, filepath: str) -> str:
        root_path = Path(project_root).resolve()
        file_path = Path(filepath).resolve()
        try:
            rel_path = file_path.relative_to(root_path)
        except ValueError:
            rel_path = Path(filepath)
            
        parts = list(rel_path.parts)
        # Strip common 'src' prefix for correct FQN matching
        if parts and parts[0] == 'src':
            parts = parts[1:]
            
        if parts and parts[-1].endswith('.py'):
            if parts[-1] == '__init__.py':
                parts = parts[:-1]
            else:
                parts[-1] = parts[-1][:-3]
                
        return ".".join(parts)
