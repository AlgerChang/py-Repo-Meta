import json
from contextlib import contextmanager
from pathlib import Path
from typing import List, Dict, Any, Optional

class JsonQueryEngine:
    def __init__(self, db):
        self.db = db

    @contextmanager
    def _connection(self):
        conn = self.db.get_connection()
        try:
            yield conn
        finally:
            conn.close()

    def _dict_factory(self, cursor, row):
        return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

    def _path_lookup_sql(self, paths: List[str]) -> tuple[str, List[str]]:
        clauses = []
        params = []
        exact_paths = []
        for raw_path in paths:
            path = Path(raw_path)
            exact_paths.extend([raw_path, str(path)])
            try:
                exact_paths.append(str(path.resolve()))
            except OSError:
                pass

            normalized = raw_path.replace("\\", "/")
            while normalized.startswith("./"):
                normalized = normalized[2:]
            clauses.append("REPLACE(filepath, '\\', '/') = ?")
            params.append(normalized)
            if not path.is_absolute():
                clauses.append("REPLACE(filepath, '\\', '/') LIKE ?")
                params.append(f"%/{normalized}")

        exact_paths = list(dict.fromkeys(exact_paths))
        if exact_paths:
            placeholders = ",".join("?" for _ in exact_paths)
            clauses.insert(0, f"filepath IN ({placeholders})")
            params = exact_paths + params
        return " OR ".join(clauses), params

    def get_overview(self) -> Dict[str, Any]:
        with self._connection() as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM files")
            files = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM symbols WHERE symbol_type='module'")
            modules = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM symbols WHERE symbol_type='class'")
            classes = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM symbols WHERE symbol_type IN ('function', 'method')")
            funcs = c.fetchone()[0]
            return {
                "total_files": files,
                "total_modules": modules,
                "total_classes": classes,
                "total_functions": funcs
            }

    def get_schema(self) -> Dict[str, Any]:
        with self._connection() as conn:
            conn.row_factory = self._dict_factory
            c = conn.cursor()
            c.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")
            tables = c.fetchall()
            return {"tables": tables}

    def _get_file_ids(self, names: List[str], paths: List[str], ids: List[str], cursor) -> List[int]:
        file_ids = []
        if ids:
            module_ids = [int(i) for i in ids]
            placeholders = ",".join("?" for _ in module_ids)
            cursor.execute(
                f"SELECT file_id FROM symbols WHERE symbol_type='module' AND id IN ({placeholders})",
                module_ids,
            )
            file_ids.extend([row['file_id'] for row in cursor.fetchall()])
        if paths:
            where_sql, params = self._path_lookup_sql(paths)
            cursor.execute(f"SELECT id FROM files WHERE {where_sql}", params)
            file_ids.extend([row['id'] for row in cursor.fetchall()])
        if names:
            placeholders = ",".join("?" for _ in names)
            cursor.execute(
                f"""
                SELECT file_id FROM symbols
                WHERE symbol_type='module'
                AND (name IN ({placeholders}) OR qualname IN ({placeholders}))
                """,
                list(names) + list(names),
            )
            file_ids.extend([row['file_id'] for row in cursor.fetchall()])
        return list(set(file_ids))

    def _parse_metadata(self, meta_str: str) -> Dict:
        if not meta_str:
            return {}
        try:
            return json.loads(meta_str)
        except json.JSONDecodeError:
            return {}

    def query_module(self, names: List[str], paths: List[str], ids: List[str]) -> List[Dict]:
        results = []
        with self._connection() as conn:
            conn.row_factory = self._dict_factory
            cursor = conn.cursor()
            file_ids = self._get_file_ids(names, paths, ids, cursor)
            
            for file_id in file_ids:
                cursor.execute("SELECT filepath FROM files WHERE id=?", (file_id,))
                file_row = cursor.fetchone()
                if not file_row:
                    continue
                filepath = file_row['filepath']
                
                cursor.execute("SELECT * FROM symbols WHERE file_id=?", (file_id,))
                symbols = cursor.fetchall()
                
                module_sym = next((s for s in symbols if s['symbol_type'] == 'module'), None)
                if not module_sym:
                    continue
                    
                cursor.execute("SELECT target_qualname FROM edges WHERE source_symbol_id=? AND edge_type='imports'", (module_sym['id'],))
                imports = [r['target_qualname'] for r in cursor.fetchall()]
                
                classes = []
                functions = []
                for s in symbols:
                    meta = self._parse_metadata(s['metadata'])
                    if s['symbol_type'] == 'class':
                        classes.append({
                            "id": s['id'], "name": s['name'], "qualname": s['qualname'],
                            "line_start": s['line_start'], "line_end": s['line_end'],
                            "docstring": s['docstring']
                        })
                    elif s['symbol_type'] in ('function', 'method'):
                        functions.append({
                            "id": s['id'], "name": s['name'], "qualname": s['qualname'],
                            "symbol_type": s['symbol_type'],
                            "line_start": s['line_start'], "line_end": s['line_end'],
                            "args": meta.get('args', []),
                            "returns": meta.get('returns'),
                            "is_async": meta.get('is_async', False)
                        })
                        
                results.append({
                    "id": module_sym['id'],
                    "file_id": file_id,
                    "filepath": filepath,
                    "module_name": module_sym['name'],
                    "line_start": module_sym['line_start'],
                    "line_end": module_sym['line_end'],
                    "docstring": module_sym['docstring'],
                    "imports": imports,
                    "classes": classes,
                    "functions": functions
                })
        return results

    def query_deps(self, names: List[str], paths: List[str], ids: List[str]) -> List[Dict]:
        results = []
        with self._connection() as conn:
            conn.row_factory = self._dict_factory
            cursor = conn.cursor()
            file_ids = self._get_file_ids(names, paths, ids, cursor)
            
            for file_id in file_ids:
                cursor.execute("SELECT filepath FROM files WHERE id=?", (file_id,))
                f_row = cursor.fetchone()
                if not f_row:
                    continue
                filepath = f_row['filepath']
                
                cursor.execute("SELECT to_module FROM dependencies WHERE from_path=?", (filepath,))
                depends_on = [r['to_module'] for r in cursor.fetchall()]
                
                # Get module qualname to check who depends on it
                cursor.execute("SELECT qualname FROM symbols WHERE file_id=? AND symbol_type='module'", (file_id,))
                m_row = cursor.fetchone()
                depended_by = []
                if m_row:
                    qualname = m_row['qualname']
                    cursor.execute(
                        "SELECT from_path FROM dependencies WHERE to_module=? OR to_module LIKE ?",
                        (qualname, f"{qualname}.%"),
                    )
                    depended_by = [r['from_path'] for r in cursor.fetchall()]
                    
                results.append({
                    "filepath": filepath,
                    "module_name": m_row['qualname'] if m_row else None,
                    "depends_on": depends_on,
                    "depended_by": depended_by
                })
        return results

    def query_imports(self, names: List[str], paths: List[str], ids: List[str]) -> List[Dict]:
        results = []
        with self._connection() as conn:
            conn.row_factory = self._dict_factory
            cursor = conn.cursor()
            file_ids = self._get_file_ids(names, paths, ids, cursor)
            
            for file_id in file_ids:
                cursor.execute("SELECT filepath FROM files WHERE id=?", (file_id,))
                f_row = cursor.fetchone()
                if not f_row:
                    continue
                
                cursor.execute("SELECT id, name FROM symbols WHERE file_id=? AND symbol_type='module'", (file_id,))
                m_row = cursor.fetchone()
                if not m_row:
                    continue
                    
                cursor.execute("SELECT target_qualname FROM edges WHERE source_symbol_id=? AND edge_type='imports'", (m_row['id'],))
                imports = [r['target_qualname'] for r in cursor.fetchall()]
                
                results.append({
                    "filepath": f_row['filepath'],
                    "module_name": m_row['name'],
                    "imports": imports
                })
        return results

    def query_find(self, names: List[str]) -> List[Dict]:
        results = []
        if not names:
            return results
            
        seen = set()
        with self._connection() as conn:
            conn.row_factory = self._dict_factory
            cursor = conn.cursor()
            
            for name in names:
                like_pattern = f"%{name}%"
                cursor.execute("""
                    SELECT s.id, s.name, s.qualname, s.symbol_type, s.line_start, s.line_end, f.filepath
                    FROM symbols s
                    JOIN files f ON s.file_id = f.id
                    WHERE s.symbol_type IN ('class', 'function', 'method')
                    AND (s.name LIKE ? OR s.qualname LIKE ?)
                    LIMIT 50
                """, (like_pattern, like_pattern))
                
                rows = cursor.fetchall()
                for r in rows:
                    if r['id'] in seen:
                        continue
                    seen.add(r['id'])
                    results.append({
                        "id": r['id'],
                        "name": r['name'],
                        "qualname": r['qualname'],
                        "symbol_type": r['symbol_type'],
                        "filepath": r['filepath'],
                        "line_start": r['line_start'],
                        "line_end": r['line_end']
                    })
        return results

    def _get_symbols_by_names_or_ids(self, names: List[str], ids: List[str], symbol_types: tuple, cursor) -> List[Dict]:
        symbols = []
        
        # Helper to construct parameterized IN clauses
        if ids:
            placeholders = ",".join("?" for _ in ids)
            params = [int(i) for i in ids]
            type_placeholders = ",".join("?" for _ in symbol_types)
            params.extend(symbol_types)
            
            cursor.execute(f"""
                SELECT s.*, f.filepath FROM symbols s
                JOIN files f ON s.file_id = f.id
                WHERE s.id IN ({placeholders}) AND s.symbol_type IN ({type_placeholders})
            """, params)
            symbols.extend(cursor.fetchall())
            
        if names:
            placeholders = ",".join("?" for _ in names)
            params = list(names)
            type_placeholders = ",".join("?" for _ in symbol_types)
            params.extend(symbol_types)
            
            cursor.execute(f"""
                SELECT s.*, f.filepath FROM symbols s
                JOIN files f ON s.file_id = f.id
                WHERE s.name IN ({placeholders}) AND s.symbol_type IN ({type_placeholders})
            """, params)
            symbols.extend(cursor.fetchall())
            
        # Deduplicate by id
        seen = set()
        deduped = []
        for s in symbols:
            if s['id'] not in seen:
                seen.add(s['id'])
                deduped.append(s)
        return deduped

    def query_class(self, names: List[str], ids: List[str]) -> List[Dict]:
        results = []
        with self._connection() as conn:
            conn.row_factory = self._dict_factory
            cursor = conn.cursor()
            
            class_syms = self._get_symbols_by_names_or_ids(names, ids, ('class',), cursor)
            
            for c_sym in class_syms:
                c_id = c_sym['id']
                
                cursor.execute("SELECT target_qualname FROM edges WHERE source_symbol_id=? AND edge_type='inherits'", (c_id,))
                bases = [r['target_qualname'] for r in cursor.fetchall()]
                
                cursor.execute("SELECT id, name, line_start, line_end FROM symbols WHERE parent_id=? AND symbol_type='method'", (c_id,))
                methods = [{"id": r['id'], "name": r['name'], "line_start": r['line_start'], "line_end": r['line_end']} for r in cursor.fetchall()]
                
                meta = self._parse_metadata(c_sym['metadata'])
                
                results.append({
                    "id": c_id,
                    "filepath": c_sym['filepath'],
                    "name": c_sym['name'],
                    "qualname": c_sym['qualname'],
                    "line_start": c_sym['line_start'],
                    "line_end": c_sym['line_end'],
                    "docstring": c_sym['docstring'],
                    "bases": bases,
                    "methods": methods,
                    "plugins": meta.get('plugins', {})
                })
        return results

    def query_function(self, names: List[str], ids: List[str]) -> List[Dict]:
        results = []
        with self._connection() as conn:
            conn.row_factory = self._dict_factory
            cursor = conn.cursor()
            
            func_syms = self._get_symbols_by_names_or_ids(names, ids, ('function', 'method'), cursor)
            
            for f_sym in func_syms:
                meta = self._parse_metadata(f_sym['metadata'])
                results.append({
                    "id": f_sym['id'],
                    "filepath": f_sym['filepath'],
                    "name": f_sym['name'],
                    "qualname": f_sym['qualname'],
                    "symbol_type": f_sym['symbol_type'],
                    "line_start": f_sym['line_start'],
                    "line_end": f_sym['line_end'],
                    "docstring": f_sym['docstring'],
                    "args": meta.get('args', []),
                    "returns": meta.get('returns'),
                    "is_async": meta.get('is_async', False),
                    "plugins": meta.get('plugins', {})
                })
        return results
