import os
import hashlib
import fnmatch
import concurrent.futures
from pathlib import Path
from typing import Optional, Set, List, Tuple

from prmg.storage.models import File, Symbol, Edge
from prmg.storage.storage import DatabaseManager
from prmg.parser.base import BaseParser
from prmg.core.tracker import DependencyTracker

def _parse_task(filepath: str, parser_class, project_root: str, plugin_config: dict = None) -> tuple[str, list[Symbol], list[Edge]]:
    """
    Top-level function for multiprocessing to avoid pickle issues with inner functions or lambdas.
    """
    parser = parser_class(project_root, plugin_config)
    symbols, edges = parser.parse_file(filepath)
    return filepath, symbols, edges


class RepoScanner:
    def __init__(self, root_path: str, storage: DatabaseManager, parser: BaseParser,
                 batch_size: int = 500, max_workers: Optional[int] = None):
        self.root_path = Path(root_path).resolve()
        self.storage = storage
        self.parser = parser
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.tracker = DependencyTracker(storage.db_path)
        self.ignore_patterns = self._load_gitignore()

    def _load_gitignore(self) -> List[str]:
        patterns = ['__pycache__', '.git', '.venv']
        gitignore_path = self.root_path / '.gitignore'
        if gitignore_path.exists():
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        patterns.append(line)
        return patterns

    def _is_ignored(self, path: Path) -> bool:
        try:
            rel_path = path.relative_to(self.root_path)
        except ValueError:
            return True
            
        # Check against each part of the path for directory-level ignores
        for part in rel_path.parts:
            for pattern in self.ignore_patterns:
                if fnmatch.fnmatch(part, pattern):
                    return True
                    
        # Check against the full relative path
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(str(rel_path), pattern):
                return True
                
        return False

    def _compute_hash(self, filepath: str) -> str:
        hasher = hashlib.sha256()
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()

    def run(self):
        # Step 1: Traverse directory and compare hashes
        existing_files = {}
        with self.storage.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, filepath, file_hash FROM files")
            for row in cursor.fetchall():
                existing_files[row[1]] = {"id": row[0], "hash": row[2]}

        current_files = {}
        to_parse: Set[str] = set()
        to_delete: Set[str] = set()

        for root, dirs, files in os.walk(self.root_path):
            # Modify dirs in-place to prune ignored directories efficiently
            dirs[:] = [d for d in dirs if not self._is_ignored(Path(root) / d)]
            
            for file in files:
                if not file.endswith('.py'):
                    continue
                file_path = Path(root) / file
                if self._is_ignored(file_path):
                    continue
                
                abs_path = str(file_path.resolve())
                current_files[abs_path] = file_path
                
                try:
                    file_hash = self._compute_hash(abs_path)
                except Exception:
                    continue
                
                if abs_path not in existing_files:
                    to_parse.add(abs_path)
                elif existing_files[abs_path]["hash"] != file_hash:
                    to_parse.add(abs_path)

        for abs_path in existing_files:
            if abs_path not in current_files:
                to_delete.add(abs_path)

        # Step 3: Call DependencyTracker to find reverse-dependencies
        affected_files: Set[str] = set()
        for filepath in to_parse | to_delete:
            dependents = self.tracker.get_dependents(filepath, str(self.root_path))
            affected_files.update(dependents)

        # Merge affected files into to_parse
        for filepath in affected_files:
            if filepath in current_files and filepath not in to_parse:
                to_parse.add(filepath)

        # Handle deletions
        if to_delete:
            with self.storage.get_connection() as conn:
                cursor = conn.cursor()
                for filepath in to_delete:
                    cursor.execute("DELETE FROM files WHERE filepath = ?", (filepath,))
                    self.tracker.remove_file(filepath)
                conn.commit()

        if not to_parse:
            return

        # Step 4: Parallel execution with ProcessPoolExecutor
        to_parse_list = list(to_parse)
        parser_class = self.parser.__class__
        parsed_results = []
        
        with concurrent.futures.ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(_parse_task, filepath, parser_class, str(self.root_path), self.parser.plugin_config)
                for filepath in to_parse_list
            ]
            for future in concurrent.futures.as_completed(futures):
                try:
                    parsed_results.append(future.result())
                except Exception as e:
                    print(f"Error parsing file: {e}")
                    
                # Batch commit
                if len(parsed_results) >= self.batch_size:
                    self._commit_batch(parsed_results)
                    parsed_results.clear()
                    
        if parsed_results:
            self._commit_batch(parsed_results)

    def _commit_batch(self, batch: List[Tuple[str, List[Symbol], List[Edge]]]):
        try:
            with self.storage.get_connection() as conn:
                for filepath, symbols, edges in batch:
                    file_hash = self._compute_hash(filepath)
                    last_modified = os.path.getmtime(filepath)
                    
                    # Force cleanup: Ensures that previously recorded symbols and edges 
                    # are fully deleted before re-inserting, specifically addressing 
                    # the edge case where an affected file's hash hasn't changed.
                    conn.execute("DELETE FROM files WHERE filepath = ?", (filepath,))
                        
                    file_record = File(
                        filepath=filepath,
                        file_hash=file_hash,
                        last_modified=last_modified
                    )
                    file_id = self.storage.upsert_file(file_record, conn=conn)
                    
                    for sym in symbols:
                        sym.file_id = file_id
                        
                    # Maintain mapping between internal Parser ID to Database primary key ID
                    old_ids = {id(sym): sym.id for sym in symbols}
                    self.storage.insert_symbols(symbols, conn=conn)
                    old_to_new_id = {old_ids[id(sym)]: sym.id for sym in symbols}
                    
                    # Update edges with new source symbol DB IDs and extract imports
                    imports = set()
                    for edge in edges:
                        if edge.source_symbol_id in old_to_new_id:
                            edge.source_symbol_id = old_to_new_id[edge.source_symbol_id]
                        if edge.edge_type == 'imports':
                            imports.add(edge.target_qualname)
                            
                    self.storage.insert_edges(edges, conn=conn)
                    
                    # Update dependencies in Tracker
                    self.tracker.update_relations(filepath, imports, conn=conn)
                
                # Commit the entire batch atomically
                conn.commit()
        except Exception as e:
            print(f"Failed to commit batch. Rolling back. Error: {e}")
            # The context manager does not automatically rollback on exception in some Python versions 
            # if we are doing explicit commits, so let's be explicit. But with sqlite3 context manager 
            # it normally does rollback on exception. 
            # We log the error. The caller should be aware.
