import json
import sqlite3
from typing import List

from .models import Edge, File, Symbol

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        """Establish a connection to SQLite with necessary PRAGMAs."""
        conn = sqlite3.connect(self.db_path)
        # Enable WAL mode for better write concurrency and performance
        conn.execute("PRAGMA journal_mode = WAL;")
        # Enable Foreign Key support
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def create_tables(self) -> None:
        """Initialize the v0.2 SQLite Schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # files table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY,
                    filepath TEXT UNIQUE NOT NULL,
                    file_hash TEXT NOT NULL,
                    last_modified REAL NOT NULL
                )
            """)
            
            # symbols table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS symbols (
                    id INTEGER PRIMARY KEY,
                    file_id INTEGER NOT NULL,
                    parent_id INTEGER,
                    symbol_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    qualname TEXT UNIQUE NOT NULL,
                    docstring TEXT,
                    metadata JSON,
                    line_start INTEGER NOT NULL,
                    line_end INTEGER NOT NULL,
                    FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE,
                    FOREIGN KEY(parent_id) REFERENCES symbols(id) ON DELETE CASCADE
                )
            """)
            
            # edges table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS edges (
                    source_symbol_id INTEGER NOT NULL,
                    target_qualname TEXT NOT NULL,
                    edge_type TEXT NOT NULL,
                    PRIMARY KEY (source_symbol_id, target_qualname, edge_type),
                    FOREIGN KEY(source_symbol_id) REFERENCES symbols(id) ON DELETE CASCADE
                )
            """)
            
            # Create indexes for better query performance on FK columns
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbols_file_id ON symbols(file_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbols_parent_id ON symbols(parent_id);")
            
            conn.commit()

    def upsert_file(self, file: File, conn: sqlite3.Connection = None) -> int:
        """
        Insert a new file or update an existing one based on filepath.
        If the file exists but hash changed, delete it first to trigger
        ON DELETE CASCADE for old symbols and edges, preventing duplication.
        Returns the file ID.
        """
        managed_conn = False
        if conn is None:
            conn = self.get_connection()
            managed_conn = True
            
        try:
            cursor = conn.cursor()
            
            # Check for existing file
            cursor.execute("SELECT id, file_hash FROM files WHERE filepath = ?", (file.filepath,))
            row = cursor.fetchone()
            
            if row:
                existing_id, existing_hash = row
                if existing_hash == file.file_hash:
                    # Content unchanged, just update timestamp
                    cursor.execute(
                        "UPDATE files SET last_modified = ? WHERE id = ?",
                        (file.last_modified, existing_id)
                    )
                    file.id = existing_id
                    if managed_conn:
                        conn.commit()
                    return existing_id
                else:
                    # Content changed, DELETE to trigger CASCADE for symbols and edges
                    cursor.execute("DELETE FROM files WHERE id = ?", (existing_id,))
            
            # Insert new file (or re-insert after delete)
            cursor.execute("""
                INSERT INTO files (filepath, file_hash, last_modified)
                VALUES (?, ?, ?)
                RETURNING id
            """, (file.filepath, file.file_hash, file.last_modified))
            
            result = cursor.fetchone()
            if result:
                file.id = result[0]
                if managed_conn:
                    conn.commit()
                return result[0]
            raise RuntimeError(f"Failed to upsert file: {file.filepath}")
        finally:
            if managed_conn:
                conn.close()

    def insert_symbols(self, symbols: List[Symbol], conn: sqlite3.Connection = None) -> List[int]:
        """
        Insert a list of symbols hierarchically to satisfy FK constraints.
        It resolves `parent_id` dynamically using `parent_qualname`.
        """
        inserted_ids = []
        
        # Sort symbols by qualname depth (dots count) to ensure Top-Down insertion
        # This guarantees parents are always inserted before their children.
        sorted_symbols = sorted(symbols, key=lambda s: s.qualname.count('.'))
        
        # In-memory mapping to keep track of generated IDs for children to reference
        qualname_to_id = {}
        
        managed_conn = False
        if conn is None:
            conn = self.get_connection()
            managed_conn = True
            
        try:
            cursor = conn.cursor()
            for symbol in sorted_symbols:
                # Dynamically resolve parent_id if a parent_qualname is provided
                if symbol.parent_qualname and symbol.parent_qualname in qualname_to_id:
                    symbol.parent_id = qualname_to_id[symbol.parent_qualname]
                    
                # Handle JSON serialization for metadata
                metadata_json = json.dumps(symbol.metadata) if symbol.metadata is not None else None
                
                cursor.execute("""
                    INSERT INTO symbols (
                        file_id, parent_id, symbol_type, name, qualname,
                        docstring, metadata, line_start, line_end
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    RETURNING id
                """, (
                    symbol.file_id, symbol.parent_id, symbol.symbol_type,
                    symbol.name, symbol.qualname, symbol.docstring,
                    metadata_json, symbol.line_start, symbol.line_end
                ))
                result = cursor.fetchone()
                if result:
                    symbol.id = result[0]
                    inserted_ids.append(result[0])
                    # Update mapping for subsequent children
                    qualname_to_id[symbol.qualname] = symbol.id
            if managed_conn:
                conn.commit()
            return inserted_ids
        finally:
            if managed_conn:
                conn.close()

    def insert_edges(self, edges: List[Edge], conn: sqlite3.Connection = None) -> None:
        """Insert a list of dependency/relationship edges."""
        managed_conn = False
        if conn is None:
            conn = self.get_connection()
            managed_conn = True
            
        try:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT OR IGNORE INTO edges (source_symbol_id, target_qualname, edge_type)
                VALUES (?, ?, ?)
            """, [(e.source_symbol_id, e.target_qualname, e.edge_type) for e in edges])
            if managed_conn:
                conn.commit()
        finally:
            if managed_conn:
                conn.close()
