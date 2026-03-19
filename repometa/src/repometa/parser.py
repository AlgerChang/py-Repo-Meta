import ast
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

# =========================================================================
# Module 1: Core Data Models (Pydantic V2)
# =========================================================================

class FunctionNode(BaseModel):
    """Represents a parsed Python function or method."""
    name: str
    docstring: str | None = None
    args: list[str] = Field(default_factory=list)
    return_type: str | None = None
    is_async: bool
    decorators: list[str] = Field(default_factory=list)
    metadata_tags: dict[str, Any] = Field(default_factory=dict)


class ClassNode(BaseModel):
    """Represents a parsed Python class."""
    name: str
    docstring: str | None = None
    bases: list[str] = Field(default_factory=list)
    methods: list[FunctionNode] = Field(default_factory=list)
    metadata_tags: dict[str, Any] = Field(default_factory=dict)


class ModuleNode(BaseModel):
    """Represents a parsed Python module (file)."""
    file_path: str
    parse_status: str = "SUCCESS"  # "SUCCESS" or "UNPARSABLE"
    error_msg: str | None = None
    docstring: str | None = None
    imports: list[str] = Field(default_factory=list)
    classes: list[ClassNode] = Field(default_factory=list)
    functions: list[FunctionNode] = Field(default_factory=list)


# =========================================================================
# Module 2: Configuration Management
# =========================================================================

class ConfigLoader:
    """Loads and manages PRMG configuration from pyproject.toml."""
    
    def __init__(self, cwd: Path | str | None = None):
        self.cwd = Path(cwd) if cwd else Path.cwd()
        self.include_private: bool = False
        self.exclude_dirs: list[str] = []
        self.active_plugins: list[str] = []
        self._load_config()

    def _load_config(self) -> None:
        """Reads tool.prmg section from pyproject.toml."""
        pyproject_path = self.cwd / "pyproject.toml"
        if not pyproject_path.exists():
            return
        
        try:
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
            
            prmg_config = data.get("tool", {}).get("prmg", {})
            self.include_private = prmg_config.get("include_private", False)
            self.exclude_dirs = prmg_config.get("exclude_dirs", [])
            self.active_plugins = prmg_config.get("active_plugins", [])
        except Exception:
            # Silently fallback to defaults if parsing fails
            pass


# =========================================================================
# Module 3: Plugin Interface (Read-Only Observer)
# =========================================================================

class PluginBase:
    """Base class for PRMG plugins to observe and mutate metadata tags."""
    
    def on_function_extracted(
        self, 
        node: ast.FunctionDef | ast.AsyncFunctionDef, 
        meta: FunctionNode
    ) -> None:
        """Called when a function or method is extracted."""
        pass

    def on_class_extracted(self, node: ast.ClassDef, meta: ClassNode) -> None:
        """Called when a class is extracted."""
        pass


# =========================================================================
# Module 4: AST Parser & Extractor
# =========================================================================

class MetadataExtractor(ast.NodeVisitor):
    """Visits AST nodes and extracts structural metadata."""
    
    def __init__(self, config: ConfigLoader, plugins: list[PluginBase]):
        self.config = config
        self.plugins = plugins
        
        self.imports: list[str] = []
        self.classes: list[ClassNode] = []
        self.functions: list[FunctionNode] = []
        
        self._current_class: ClassNode | None = None

    def _should_include(self, name: str) -> bool:
        """Determines if a node should be included based on private filtering."""
        if self.config.include_private:
            return True
        if name.startswith("_") and name != "__init__":
            return False
        return True

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            import_str = f"import {alias.name}"
            if alias.asname:
                import_str += f" as {alias.asname}"
            self.imports.append(import_str)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        names = []
        for alias in node.names:
            name_str = alias.name
            if alias.asname:
                name_str += f" as {alias.asname}"
            names.append(name_str)
        
        level = "." * node.level if node.level > 0 else ""
        import_str = f"from {level}{module} import {', '.join(names)}"
        self.imports.append(import_str)
        self.generic_visit(node)

    def _extract_args(self, args: ast.arguments) -> list[str]:
        """Extracts and formats arguments, including type hints and defaults."""
        arg_list = []
        
        # Combine posonlyargs and standard args for default mapping
        all_pos_args = args.posonlyargs + args.args
        defaults_offset = len(all_pos_args) - len(args.defaults)
        
        for i, arg in enumerate(all_pos_args):
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {ast.unparse(arg.annotation)}"
            if i >= defaults_offset:
                default_val = ast.unparse(args.defaults[i - defaults_offset])
                arg_str += f" = {default_val}"
            arg_list.append(arg_str)
            
        if args.vararg:
            vararg_str = f"*{args.vararg.arg}"
            if args.vararg.annotation:
                vararg_str += f": {ast.unparse(args.vararg.annotation)}"
            arg_list.append(vararg_str)
            
        for i, arg in enumerate(args.kwonlyargs):
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {ast.unparse(arg.annotation)}"
            # In kwonlyargs, kw_defaults can be None for required kwargs
            if i < len(args.kw_defaults) and args.kw_defaults[i] is not None:
                default_val = ast.unparse(args.kw_defaults[i])
                arg_str += f" = {default_val}"
            arg_list.append(arg_str)
            
        if args.kwarg:
            kwarg_str = f"**{args.kwarg.arg}"
            if args.kwarg.annotation:
                kwarg_str += f": {ast.unparse(args.kwarg.annotation)}"
            arg_list.append(kwarg_str)

        return arg_list

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if not self._should_include(node.name):
            return

        bases = [ast.unparse(b) for b in node.bases]
        docstring = ast.get_docstring(node)

        class_node = ClassNode(
            name=node.name,
            docstring=docstring,
            bases=bases,
            methods=[]
        )
        
        for plugin in self.plugins:
            plugin.on_class_extracted(node, class_node)

        self.classes.append(class_node)

        prev_class = self._current_class
        self._current_class = class_node
        
        # Visit inner nodes to find methods
        for item in node.body:
            self.visit(item)
        
        self._current_class = prev_class

    def _process_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool) -> None:
        if not self._should_include(node.name):
            return

        docstring = ast.get_docstring(node)
        decorators = [ast.unparse(dec) for dec in node.decorator_list]
        args = self._extract_args(node.args)
        
        return_type = None
        if node.returns:
            return_type = ast.unparse(node.returns)

        func_node = FunctionNode(
            name=node.name,
            docstring=docstring,
            args=args,
            return_type=return_type,
            is_async=is_async,
            decorators=decorators
        )

        for plugin in self.plugins:
            plugin.on_function_extracted(node, func_node)

        if self._current_class is not None:
            self._current_class.methods.append(func_node)
        else:
            self.functions.append(func_node)
            
        # Intentionally NOT calling self.generic_visit(node)
        # This prevents traversing into the function body ensuring
        # constraints against internal AST visiting are completely adhered to.

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._process_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._process_function(node, is_async=True)


class RepositoryParser:
    """Parses a Python file and returns a structured ModuleNode."""
    
    def __init__(self, config: ConfigLoader | None = None, plugins: list[PluginBase] | None = None):
        self.config = config or ConfigLoader()
        self.plugins = plugins or []

    def parse_file(self, file_path: str) -> ModuleNode:
        path = Path(file_path)
        
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            return ModuleNode(
                file_path=file_path,
                parse_status="UNPARSABLE",
                error_msg=f"File read error: {e}"
            )

        try:
            tree = ast.parse(content, filename=file_path)
        except SyntaxError as e:
            return ModuleNode(
                file_path=file_path,
                parse_status="UNPARSABLE",
                error_msg=f"SyntaxError: {e}"
            )
        except Exception as e:
            return ModuleNode(
                file_path=file_path,
                parse_status="UNPARSABLE",
                error_msg=f"Parse error: {e}"
            )

        extractor = MetadataExtractor(self.config, self.plugins)
        
        # We need to extract top level items
        # To avoid generic_visit diving into local imports or functions,
        # we iterate explicitly or let visit_Module handle it.
        # But visit_Module would normally use generic_visit.
        # So we iterate over body items.
        for item in tree.body:
            extractor.visit(item)

        docstring = ast.get_docstring(tree)

        return ModuleNode(
            file_path=file_path,
            docstring=docstring,
            imports=extractor.imports,
            classes=extractor.classes,
            functions=extractor.functions
        )

# For backward compatibility with older code if any (parse_file)
def parse_file(filepath: Path) -> list[dict]:
    # A temporary wrapper if something is expecting the old signature
    parser = RepositoryParser()
    module = parser.parse_file(str(filepath))
    
    # map it back to old format
    symbols = []
    for cls in module.classes:
        symbols.append({
            'name': cls.name,
            'qualname': cls.name,
            'symbol_type': 'class',
            'docstring': cls.docstring
        })
        for method in cls.methods:
            symbols.append({
                'name': method.name,
                'qualname': f"{cls.name}.{method.name}",
                'symbol_type': 'async_function' if method.is_async else 'function',
                'docstring': method.docstring
            })
    for func in module.functions:
         symbols.append({
            'name': func.name,
            'qualname': func.name,
            'symbol_type': 'async_function' if func.is_async else 'function',
            'docstring': func.docstring
        })
    return symbols
