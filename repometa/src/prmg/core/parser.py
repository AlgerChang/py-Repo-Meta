import ast
import hashlib
from typing import List, Optional, Any
from .models import FunctionMetadata, ClassMetadata, ModuleMetadata

class MetadataExtractor(ast.NodeVisitor):
    """
    AST NodeVisitor that extracts metadata from a Python file.
    """
    def __init__(self, file_path: str, file_content: str):
        self.file_path = file_path
        self.file_content = file_content
        self.module_meta = ModuleMetadata(
            file_path=file_path,
            file_hash=self._compute_hash(file_content),
            docstring=None
        )
        self.current_class: Optional[ClassMetadata] = None

    def _compute_hash(self, content: str) -> str:
        """Calculate the SHA-256 hash of the content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _unparse_annotation(self, node: ast.expr) -> str:
        """Convert an AST annotation node to its string representation."""
        try:
            return ast.unparse(node)
        except Exception:
            return ""

    def _parse_arguments(self, args: ast.arguments) -> List[str]:
        """Extract arguments, type hints, and default values as a list of strings."""
        parsed_args = []
        
        # In Python 3.9+, ast.unparse can unparse the entire arguments node.
        # We can unparse it, but since models.py expects List[str], it's easier to split
        # the unparsed string if we don't care about commas inside type hints.
        # However, a robust way is to rebuild it using the same logic ast.unparse uses internally,
        # or we can change our approach and use `inspect.signature` like behavior.
        # Since we just want the string representation of each arg for our List[str],
        # let's write a robust manual extractor that includes defaults.
        
        # Normal args and posonlyargs (combining them for simplicity here)
        all_args = getattr(args, 'posonlyargs', []) + args.args
        defaults_offset = len(all_args) - len(args.defaults)
        
        for i, arg in enumerate(all_args):
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {self._unparse_annotation(arg.annotation)}"
            # Add default value if present
            if i >= defaults_offset:
                default_idx = i - defaults_offset
                default_val = self._unparse_annotation(args.defaults[default_idx])
                arg_str += f" = {default_val}"
            parsed_args.append(arg_str)
            
        # *args
        if args.vararg:
            arg_str = f"*{args.vararg.arg}"
            if args.vararg.annotation:
                arg_str += f": {self._unparse_annotation(args.vararg.annotation)}"
            parsed_args.append(arg_str)
            
        # keyword-only arguments
        for i, arg in enumerate(args.kwonlyargs):
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {self._unparse_annotation(arg.annotation)}"
            if args.kw_defaults[i] is not None:
                default_val = self._unparse_annotation(args.kw_defaults[i])
                arg_str += f" = {default_val}"
            parsed_args.append(arg_str)
            
        # **kwargs
        if args.kwarg:
            arg_str = f"**{args.kwarg.arg}"
            if args.kwarg.annotation:
                arg_str += f": {self._unparse_annotation(args.kwarg.annotation)}"
            parsed_args.append(arg_str)
            
        return parsed_args

    def visit_Module(self, node: ast.Module) -> Any:
        """Extract module-level docstring."""
        self.module_meta.docstring = ast.get_docstring(node)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> Any:
        """Extract standard imports."""
        for alias in node.names:
            self.module_meta.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        """Extract 'from ... import ...' statements."""
        module = node.module or ""
        for alias in node.names:
            self.module_meta.imports.append(f"{module}.{alias.name}" if module else alias.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        """Extract class definitions and its methods."""
        bases = [self._unparse_annotation(b) for b in node.bases]
        class_meta = ClassMetadata(
            name=node.name,
            bases=bases,
            docstring=ast.get_docstring(node),
        )
        self.module_meta.classes.append(class_meta)
        
        # Save previous context and set current to allow nested definitions handling (if needed)
        prev_class = self.current_class
        self.current_class = class_meta
        self.generic_visit(node)
        self.current_class = prev_class

    def _handle_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool):
        """Helper to process both synchronous and asynchronous functions."""
        return_type = self._unparse_annotation(node.returns) if node.returns else None
        
        func_meta = FunctionMetadata(
            name=node.name,
            args=self._parse_arguments(node.args),
            return_type=return_type,
            docstring=ast.get_docstring(node),
            is_async=is_async
        )
        
        # Attach to the current class if it's a method, else attach to module
        if self.current_class:
            self.current_class.functions.append(func_meta)
        else:
            self.module_meta.functions.append(func_meta)
            
        # 關鍵優化：不調用 self.generic_visit(node)，跳過函數體內部細節解析
        # 這樣可大幅減少 Token 浪費，避免遞迴解析不必要的局部變數與邏輯

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        """Extract synchronous function metadata."""
        self._handle_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        """Extract asynchronous function metadata."""
        self._handle_function(node, is_async=True)


def parse_python_file(file_path: str) -> ModuleMetadata:
    """Helper function to parse a python file and return its ModuleMetadata."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    tree = ast.parse(content, filename=file_path)
    extractor = MetadataExtractor(file_path, content)
    extractor.visit(tree)
    
    return extractor.module_meta
