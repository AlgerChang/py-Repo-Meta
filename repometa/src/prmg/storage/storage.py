import json
import sqlite3
from typing import List, Sequence

from .models import ConsumerReference, Edge, File, Symbol

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

            # dependencies table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dependencies (
                    from_path TEXT NOT NULL,
                    to_module TEXT NOT NULL,
                    PRIMARY KEY (from_path, to_module)
                )
            """)

            # Occurrence-level reverse edges used by `query consumers`.
            # This is intentionally separate from `edges`: the latter is a
            # deduplicated structural graph and cannot retain source locations.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS consumer_edges (
                    id INTEGER PRIMARY KEY,
                    source_path TEXT NOT NULL,
                    source_symbol_qualname TEXT NOT NULL,
                    target_qualname TEXT NOT NULL,
                    target_symbol_id INTEGER,
                    base_edge_kind TEXT NOT NULL,
                    line_start INTEGER NOT NULL,
                    col_start INTEGER NOT NULL,
                    raw_reference TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    resolution TEXT NOT NULL DEFAULT 'unresolved',
                    UNIQUE (
                        source_path,
                        source_symbol_qualname,
                        target_qualname,
                        base_edge_kind,
                        line_start,
                        col_start,
                        origin
                    )
                )
            """)
            
            # Create indexes for better query performance on FK columns
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbols_file_id ON symbols(file_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbols_parent_id ON symbols(parent_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_to_module ON dependencies(to_module);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_consumer_target ON consumer_edges(target_qualname);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_consumer_target_symbol ON consumer_edges(target_symbol_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_consumer_source_path ON consumer_edges(source_path);")

            # Track semantic index settings that are not represented by a source
            # file hash. Changing symbol visibility must trigger a full rebuild.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS index_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            
            conn.commit()

    def get_index_setting(self, key: str) -> str | None:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM index_metadata WHERE key = ?",
                (key,),
            ).fetchone()
            return row[0] if row else None

    def set_index_setting(self, key: str, value: str) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO index_metadata (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def clear_index(self) -> None:
        """Remove all derived records so the next scan reindexes every file."""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM consumer_edges")
            conn.execute("DELETE FROM dependencies")
            conn.execute("DELETE FROM files")

    def delete_consumer_references(
        self,
        source_path: str,
        *,
        origin: str | None = None,
        conn: sqlite3.Connection = None,
    ) -> None:
        managed_conn = False
        if conn is None:
            conn = self.get_connection()
            managed_conn = True

        try:
            if origin is None:
                conn.execute(
                    "DELETE FROM consumer_edges WHERE source_path = ?",
                    (source_path,),
                )
            else:
                conn.execute(
                    "DELETE FROM consumer_edges WHERE source_path = ? AND origin = ?",
                    (source_path, origin),
                )
            if managed_conn:
                conn.commit()
        finally:
            if managed_conn:
                conn.close()

    def replace_consumer_references(
        self,
        source_path: str,
        references: Sequence[ConsumerReference],
        *,
        origin: str,
        conn: sqlite3.Connection = None,
    ) -> None:
        managed_conn = False
        if conn is None:
            conn = self.get_connection()
            managed_conn = True

        try:
            conn.execute(
                "DELETE FROM consumer_edges WHERE source_path = ? AND origin = ?",
                (source_path, origin),
            )
            if references:
                conn.executemany(
                    """
                    INSERT OR IGNORE INTO consumer_edges (
                        source_path,
                        source_symbol_qualname,
                        target_qualname,
                        base_edge_kind,
                        line_start,
                        col_start,
                        raw_reference,
                        origin,
                        resolution
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'unresolved')
                    """,
                    [
                        (
                            reference.source_path,
                            reference.source_symbol_qualname,
                            reference.target_qualname,
                            reference.base_edge_kind,
                            reference.line_start,
                            reference.col_start,
                            reference.raw_reference,
                            origin,
                        )
                        for reference in references
                    ],
                )
            if managed_conn:
                conn.commit()
        finally:
            if managed_conn:
                conn.close()

    def replace_origin_consumer_references(
        self,
        references: Sequence[ConsumerReference],
        *,
        origin: str,
    ) -> None:
        """Replace every reference produced by a full-repository origin scan."""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM consumer_edges WHERE origin = ?", (origin,))
            if references:
                conn.executemany(
                    """
                    INSERT OR IGNORE INTO consumer_edges (
                        source_path,
                        source_symbol_qualname,
                        target_qualname,
                        base_edge_kind,
                        line_start,
                        col_start,
                        raw_reference,
                        origin,
                        resolution
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'unresolved')
                    """,
                    [
                        (
                            reference.source_path,
                            reference.source_symbol_qualname,
                            reference.target_qualname,
                            reference.base_edge_kind,
                            reference.line_start,
                            reference.col_start,
                            reference.raw_reference,
                            origin,
                        )
                        for reference in references
                    ],
                )

    def resolve_consumer_references(self) -> None:
        """Resolve raw qualnames strictly against symbols in the current index."""
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE consumer_edges
                SET target_symbol_id = NULL,
                    resolution = 'unresolved'
                """
            )
            conn.execute(
                """
                UPDATE consumer_edges
                SET target_symbol_id = (
                        SELECT symbols.id
                        FROM symbols
                        WHERE symbols.qualname = consumer_edges.target_qualname
                    ),
                    resolution = 'resolved'
                WHERE EXISTS (
                    SELECT 1
                    FROM symbols
                    WHERE symbols.qualname = consumer_edges.target_qualname
                )
                """
            )
            # Preserve compatibility with repositories that explicitly import
            # through a `src.` package prefix while indexing strips that prefix.
            conn.execute(
                """
                UPDATE consumer_edges
                SET target_qualname = substr(target_qualname, 5),
                    target_symbol_id = (
                        SELECT symbols.id
                        FROM symbols
                        WHERE symbols.qualname = substr(consumer_edges.target_qualname, 5)
                    ),
                    resolution = 'resolved'
                WHERE resolution = 'unresolved'
                  AND target_qualname LIKE 'src.%'
                  AND EXISTS (
                      SELECT 1
                      FROM symbols
                      WHERE symbols.qualname = substr(consumer_edges.target_qualname, 5)
                  )
                """
            )

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
                    INSERT OR REPLACE INTO symbols (
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
