import ast
from pathlib import Path

class MetadataVisitor(ast.NodeVisitor):
    def __init__(self):
        self.symbols = []
        self.current_class = None

    def visit_ClassDef(self, node: ast.ClassDef):
        name = node.name
        qualname = node.name
        start_line = node.lineno
        end_line = getattr(node, 'end_lineno', node.lineno)
        docstring = ast.get_docstring(node)
        
        self.symbols.append({
            'name': name,
            'qualname': qualname,
            'symbol_type': 'class',
            'start_line': start_line,
            'end_line': end_line,
            'docstring': docstring
        })
        
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = None

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._process_function(node, 'function')

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._process_function(node, 'async_function')
        
    def _process_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, symbol_type: str):
        name = node.name
        if self.current_class:
            qualname = f"{self.current_class}.{name}"
        else:
            qualname = name
            
        start_line = node.lineno
        end_line = getattr(node, 'end_lineno', node.lineno)
        docstring = ast.get_docstring(node)
        
        self.symbols.append({
            'name': name,
            'qualname': qualname,
            'symbol_type': symbol_type,
            'start_line': start_line,
            'end_line': end_line,
            'docstring': docstring
        })
        # Explicitly not calling generic_visit to avoid nested functions

def parse_file(filepath: Path) -> list[dict]:
    try:
        content = filepath.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(filepath))
        visitor = MetadataVisitor()
        visitor.visit(tree)
        return visitor.symbols
    except SyntaxError as e:
        print(f"Warning: SyntaxError parsing {filepath}: {e}")
        return []
    except Exception as e:
        print(f"Warning: Failed to parse {filepath}: {e}")
        return []
