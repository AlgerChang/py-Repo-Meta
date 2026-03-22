import json
from typing import List, Optional, Dict, Any

from prmg.storage.storage import DatabaseManager
from prmg.models.ir import ModuleMeta, ClassMeta, FunctionMeta

class QueryEngine:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def _build_function_meta(self, sym_dict: Dict[str, Any]) -> FunctionMeta:
        meta = json.loads(sym_dict['metadata'] or '{}')
        args = meta.get('args', [])
        
        # Build signature string
        arg_strs = []
        for arg in args:
            arg_str = arg['name']
            if arg.get('type'):
                arg_str += f": {arg['type']}"
            if arg.get('default'):
                arg_str += f" = {arg['default']}"
            arg_strs.append(arg_str)
            
        returns = meta.get('returns')
        sig = f"({', '.join(arg_strs)})"
        if returns:
            sig += f" -> {returns}"

        return FunctionMeta(
            name=sym_dict['name'],
            signature=sig,
            docstring=sym_dict['docstring'],
            is_async=meta.get('is_async', False),
            plugins=meta.get('plugins', {})
        )

    def get_module_meta(self, filepath: str) -> Optional[ModuleMeta]:
        with self.db.get_connection() as conn:
            conn.row_factory = lambda cursor, row: {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
            cursor = conn.cursor()
            
            # Find file
            cursor.execute("SELECT id, filepath FROM files WHERE filepath = ?", (filepath,))
            file_row = cursor.fetchone()
            if not file_row:
                return None
                
            file_id = file_row['id']
            
            # Get all symbols for this file
            cursor.execute("SELECT * FROM symbols WHERE file_id = ?", (file_id,))
            symbols = cursor.fetchall()
            
            if not symbols:
                return None
                
            # Separate by type
            module_sym = next((s for s in symbols if s['symbol_type'] == 'module'), None)
            class_syms = [s for s in symbols if s['symbol_type'] == 'class']
            func_syms = [s for s in symbols if s['symbol_type'] == 'function']
            method_syms = [s for s in symbols if s['symbol_type'] == 'method']
            
            # Get imports
            imports = []
            if module_sym:
                cursor.execute("""
                    SELECT target_qualname FROM edges 
                    WHERE source_symbol_id = ? AND edge_type = 'imports'
                """, (module_sym['id'],))
                imports = [row['target_qualname'] for row in cursor.fetchall()]

            class_dict = {}
            for c_sym in class_syms:
                c_meta = json.loads(c_sym['metadata'] or '{}')
                cursor.execute("""
                    SELECT target_qualname FROM edges 
                    WHERE source_symbol_id = ? AND edge_type = 'inherits'
                """, (c_sym['id'],))
                bases = [row['target_qualname'] for row in cursor.fetchall()]
                
                methods = []
                for m_sym in method_syms:
                    if m_sym['parent_id'] == c_sym['id']:
                        methods.append(self._build_function_meta(m_sym))
                        
                class_dict[c_sym['id']] = ClassMeta(
                    name=c_sym['name'],
                    bases=bases,
                    docstring=c_sym['docstring'],
                    methods=methods,
                    nested_classes=[],
                    plugins=c_meta.get('plugins', {})
                )

            top_level_classes = []
            for c_sym in class_syms:
                c_id = c_sym['id']
                p_id = c_sym['parent_id']
                if p_id in class_dict:
                    class_dict[p_id].nested_classes.append(class_dict[c_id])
                else:
                    top_level_classes.append(class_dict[c_id])
                
            functions = [self._build_function_meta(f_sym) for f_sym in func_syms]
            
            module_doc = module_sym['docstring'] if module_sym else None
            
            return ModuleMeta(
                filepath=file_row['filepath'],
                docstring=module_doc,
                imports=imports,
                classes=top_level_classes,
                functions=functions
            )
            
    def iter_all_modules(self):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT filepath FROM files")
            filepaths = [row[0] for row in cursor.fetchall()]
            
        for filepath in filepaths:
            mod_meta = self.get_module_meta(filepath)
            if mod_meta:
                yield mod_meta
