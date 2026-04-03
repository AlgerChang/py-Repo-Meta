# File: D:\MyRepo\py-Repo-Meta\repometa\check_db.py

json
sqlite3

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\main.py

argparse
multiprocessing
os
pathlib.Path
prmg.core.extension.GlobalContext
prmg.core.extension.PluginManager
prmg.core.scanner.RepoScanner
prmg.formatter.pyi.PyiFormatter
prmg.parser.ast_parser.ASTParser
prmg.storage.query.QueryEngine
prmg.storage.storage.DatabaseManager
sys

def main():
    ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\scripts\preview_json.py

json
os
src.parser.engine.SourceParser
sys

def main():
    ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\scripts\verify_db.py

json
sqlite3

def verify():
    ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\models\schemas.py

__future__.annotations
pydantic.BaseModel
pydantic.Field
typing.List
typing.Optional

class FunctionSchema(BaseModel):
    ...

class ClassSchema(BaseModel):
    ...

class ModuleSchema(BaseModel):
    ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\parser\engine.py

ast
repometa.src.models.schemas.ModuleSchema
repometa.src.parser.visitor.SymbolVisitor

class SourceParser:
    def __init__(self, file_path: str):
        ...
    def parse(self) -> ModuleSchema:
        ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\parser\visitor.py

ast
inspect
repometa.src.models.schemas.ClassSchema
repometa.src.models.schemas.FunctionSchema
repometa.src.models.schemas.ModuleSchema
typing.List
typing.Optional

class SymbolVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str):
        ...
    def visit_Module(self, node: ast.Module):
        ...
    def visit_Import(self, node: ast.Import):
        ...
    def visit_ImportFrom(self, node: ast.ImportFrom):
        ...
    def visit_ClassDef(self, node: ast.ClassDef):
        ...
    def visit_FunctionDef(self, node: ast.FunctionDef):
        ...
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        ...

def clean_docstring(doc: str | None) -> str | None:
    ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\prmg\__init__.py

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\prmg\core\__init__.py

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\prmg\core\extension.py
"""
Extension Layer (Plugin System) for Python Repository Metadata Generator (PRMG).

This module provides the architecture for a plugin-based system to enrich
AST-extracted metadata with framework-specific semantics without modifying
the core AST structure.
"""

abc.ABC
abc.abstractmethod
ast
dataclasses.dataclass
importlib
importlib.metadata
logging
typing.Any
typing.Dict
typing.Optional

class LocalContext:
    """Context passed to plugins during the local file-level AST traversal."""

class GlobalContext:
    """Context passed to plugins after the full dependency graph is built."""

class BasePlugin(ABC):
    """
    Abstract base class for all PRMG plugins.
    Plugins MUST NOT modify the AST; they only return a dictionary to be appended
    to ext_metadata: Dict[str, Any].
    """
    def __init__(self, config: Dict[str, Any]) -> None:
        ...
    def visit_node(self, node: ast.AST, context: LocalContext) -> Optional[Dict[str, Any]]:
        """
        Triggered during file-level AST traversal for each node.
        Returns a dictionary of enriched metadata to be added to ext_metadata,
        or None if no enrichment applies to this node.
        """
        ...
    def after_indexing(self, context: GlobalContext) -> None:
        """Triggered after the full dependency graph is built (GlobalPhase)."""
        ...

class PluginManager:
    """
    Manages discovery, loading, and execution of PRMG plugins.
    Ensures that plugin exceptions are isolated from the main process
    and plugin outputs are correctly namespaced.
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        ...
    def load_from_config_string(self, name: str, config_str: str, plugin_config: Optional[Dict[str, Any]] = None) -> None:
        """
        Loads a plugin from a configuration string (e.g., 'module.path:ClassName').

        Args:
            name: The namespace key for the plugin.
            config_str: String specifying the module and class to load.
            plugin_config: Configuration dictionary for the plugin instance.
        """
        ...
    def run_visit_node(self, node: ast.AST, context: LocalContext) -> Dict[str, Any]:
        """
        Executes visit_node on all registered plugins for a given AST node.

        Returns:
            A dictionary containing namespaced metadata from plugins that returned data.
        """
        ...
    def run_after_indexing(self, context: GlobalContext) -> None:
        """Executes after_indexing on all registered plugins."""
        ...

class FastAPIPlugin(BasePlugin):
    """
    Reference Implementation: FastAPIPlugin.
    Identifies functions decorated with @app.get, @app.post, etc.
    Extracts the path and method from the decorator and adds it to ext_metadata.
    """
    def visit_node(self, node: ast.AST, context: LocalContext) -> Optional[Dict[str, Any]]:
        ...
    def after_indexing(self, context: GlobalContext) -> None:
        ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\prmg\core\models.py

dataclasses.dataclass
dataclasses.field
typing.List
typing.Optional

class FunctionMetadata:
    """Represents metadata for a Python function or method."""

class ClassMetadata:
    """Represents metadata for a Python class."""

class ModuleMetadata:
    """Represents metadata for a Python module (file)."""

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\prmg\core\parser.py

ast
hashlib
repometa.src.prmg.core.models.ClassMetadata
repometa.src.prmg.core.models.FunctionMetadata
repometa.src.prmg.core.models.ModuleMetadata
typing.Any
typing.List
typing.Optional

class MetadataExtractor(ast.NodeVisitor):
    """AST NodeVisitor that extracts metadata from a Python file."""
    def __init__(self, file_path: str, file_content: str):
        ...
    def visit_Module(self, node: ast.Module) -> Any:
        """Extract module-level docstring."""
        ...
    def visit_Import(self, node: ast.Import) -> Any:
        """Extract standard imports."""
        ...
    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        """Extract 'from ... import ...' statements."""
        ...
    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        """Extract class definitions and its methods."""
        ...
    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        """Extract synchronous function metadata."""
        ...
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        """Extract asynchronous function metadata."""
        ...

def parse_python_file(file_path: str) -> ModuleMetadata:
    """Helper function to parse a python file and return its ModuleMetadata."""
    ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\prmg\core\scanner.py

concurrent.futures
fnmatch
hashlib
os
pathlib.Path
prmg.core.tracker.DependencyTracker
prmg.parser.base.BaseParser
prmg.storage.models.Edge
prmg.storage.models.File
prmg.storage.models.Symbol
prmg.storage.storage.DatabaseManager
typing.List
typing.Optional
typing.Set
typing.Tuple

class RepoScanner:
    def __init__(self, root_path: str, storage: DatabaseManager, parser: BaseParser, batch_size: int = 500, max_workers: Optional[int] = None):
        ...
    def run(self):
        ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\prmg\core\tracker.py

pathlib.Path
sqlite3
typing.Set

class DependencyTracker:
    def __init__(self, db_path: str):
        ...
    def update_relations(self, file_path: str, imports: Set[str], conn: sqlite3.Connection = None):
        ...
    def get_dependents(self, file_path: str, project_root: str) -> Set[str]:
        ...
    def remove_file(self, file_path: str):
        ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\prmg\formatter\__init__.py

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\prmg\formatter\base.py

abc.ABC
abc.abstractmethod
prmg.models.ir.ClassMeta
prmg.models.ir.FunctionMeta
prmg.models.ir.ModuleMeta
typing.Iterator

class BaseFormatter(ABC):
    def __init__(self, include_docstrings: bool = True, optimize_tokens: bool = True) -> None:
        ...
    def format_function(self, func: FunctionMeta, indent_level: int = 0) -> str:
        ...
    def format_class(self, cls: ClassMeta, indent_level: int = 0) -> str:
        ...
    def format_module(self, module: ModuleMeta) -> str:
        ...
    def generate_repository_context(self, modules: Iterator[ModuleMeta]) -> str:
        ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\prmg\formatter\pyi.py

prmg.formatter.base.BaseFormatter
prmg.models.ir.ClassMeta
prmg.models.ir.FunctionMeta
prmg.models.ir.ModuleMeta
textwrap
typing.Iterator

class PyiFormatter(BaseFormatter):
    def format_function(self, func: FunctionMeta, indent_level: int = 0) -> str:
        ...
    def format_class(self, cls: ClassMeta, indent_level: int = 0) -> str:
        ...
    def format_module(self, module: ModuleMeta) -> str:
        ...
    def generate_repository_context(self, modules: Iterator[ModuleMeta]) -> str:
        ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\prmg\models\ir.py

dataclasses.dataclass
dataclasses.field
typing.Any
typing.Dict
typing.List
typing.Optional

class FunctionMeta:
    ...

class ClassMeta:
    ...

class ModuleMeta:
    ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\prmg\parser\__init__.py

repometa.src.prmg.ast_parser.ASTParser
repometa.src.prmg.base.BaseParser

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\prmg\parser\ast_parser.py

ast
pathlib
prmg.core.extension.LocalContext
prmg.core.extension.PluginManager
prmg.storage.models.Edge
prmg.storage.models.Symbol
repometa.src.prmg.parser.base.BaseParser
tomllib
typing.Any
typing.Optional

class ASTParser(BaseParser):
    def parse_file(self, filepath: str) -> tuple[list[Symbol], list[Edge]]:
        ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\prmg\parser\base.py

abc.ABC
abc.abstractmethod
prmg.storage.models.Edge
prmg.storage.models.Symbol
typing.List
typing.Tuple

class BaseParser(ABC):
    def __init__(self, project_root: str, plugin_config: dict | None = None):
        ...
    def parse_file(self, filepath: str) -> tuple[list[Symbol], list[Edge]]:
        ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\prmg\storage\__init__.py

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\prmg\storage\models.py

dataclasses.dataclass
typing.Any
typing.Dict
typing.Optional

class File:
    ...

class Symbol:
    ...

class Edge:
    ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\prmg\storage\query.py

json
prmg.models.ir.ClassMeta
prmg.models.ir.FunctionMeta
prmg.models.ir.ModuleMeta
prmg.storage.storage.DatabaseManager
typing.Any
typing.Dict
typing.List
typing.Optional

class QueryEngine:
    def __init__(self, db: DatabaseManager):
        ...
    def get_module_meta(self, filepath: str) -> Optional[ModuleMeta]:
        ...
    def iter_all_modules(self):
        ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\prmg\storage\storage.py

json
repometa.src.prmg.storage.models.Edge
repometa.src.prmg.storage.models.File
repometa.src.prmg.storage.models.Symbol
sqlite3
typing.List

class DatabaseManager:
    def __init__(self, db_path: str):
        ...
    def get_connection(self) -> sqlite3.Connection:
        """Establish a connection to SQLite with necessary PRAGMAs."""
        ...
    def create_tables(self) -> None:
        """Initialize the v0.2 SQLite Schema."""
        ...
    def upsert_file(self, file: File, conn: sqlite3.Connection = None) -> int:
        """
        Insert a new file or update an existing one based on filepath.
        If the file exists but hash changed, delete it first to trigger
        ON DELETE CASCADE for old symbols and edges, preventing duplication.
        Returns the file ID.
        """
        ...
    def insert_symbols(self, symbols: List[Symbol], conn: sqlite3.Connection = None) -> List[int]:
        """
        Insert a list of symbols hierarchically to satisfy FK constraints.
        It resolves `parent_id` dynamically using `parent_qualname`.
        """
        ...
    def insert_edges(self, edges: List[Edge], conn: sqlite3.Connection = None) -> None:
        """Insert a list of dependency/relationship edges."""
        ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\repometa\__init__.py
"""repometa package for extracting local Python repository metadata."""

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\repometa\cli.py

multiprocessing
os
pathlib.Path
prmg.core.extension.GlobalContext
prmg.core.extension.PluginManager
prmg.core.scanner.RepoScanner
prmg.formatter.pyi.PyiFormatter
prmg.parser.ast_parser.ASTParser
prmg.storage.query.QueryEngine
prmg.storage.storage.DatabaseManager
sys
typer
typing.Optional

def get_db_path(repo_path: Path) -> Path:
    ...

def build(repo_path: Path = typer.Argument(..., help='Path to the repository to parse')):
    """Parse Python files in the repository using the new PRMG engine and store metadata in SQLite."""
    ...

def export(view: str = typer.Argument(..., help="The view to export (e.g., 'all', 'file_focus')"), target: Optional[str] = typer.Option(None, '--target', help="The relative filepath to export for 'file_focus'"), repo_path: Path = typer.Option(Path('.'), '--repo-path', help='Path to the repository')):
    """Export metadata using PRMG engine formatters."""
    ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\repometa\db.py

pathlib.Path
sqlite3

class RepoMetaDB:
    def __init__(self, repo_path: Path):
        ...
    def setup(self):
        ...
    def clear_all(self):
        ...
    def insert_file(self, filepath: str) -> int:
        ...
    def insert_symbols(self, file_id: int, symbols: list[dict]):
        ...
    def get_symbols_by_file(self, filepath: str) -> list[dict]:
        ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\repometa\parser.py

ast
pathlib.Path
pydantic.BaseModel
pydantic.Field
tomllib
typing.Any

class FunctionNode(BaseModel):
    """Represents a parsed Python function or method."""

class ClassNode(BaseModel):
    """Represents a parsed Python class."""

class ModuleNode(BaseModel):
    """Represents a parsed Python module (file)."""

class ConfigLoader:
    """Loads and manages PRMG configuration from pyproject.toml."""
    def __init__(self, cwd: Path | str | None = None):
        ...

class PluginBase:
    """Base class for PRMG plugins to observe and mutate metadata tags."""
    def on_function_extracted(self, node: ast.FunctionDef | ast.AsyncFunctionDef, meta: FunctionNode) -> None:
        """Called when a function or method is extracted."""
        ...
    def on_class_extracted(self, node: ast.ClassDef, meta: ClassNode) -> None:
        """Called when a class is extracted."""
        ...

class MetadataExtractor(ast.NodeVisitor):
    """Visits AST nodes and extracts structural metadata."""
    def __init__(self, config: ConfigLoader, plugins: list[PluginBase]):
        ...
    def visit_Import(self, node: ast.Import) -> None:
        ...
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        ...
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        ...
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        ...
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        ...

class RepositoryParser:
    """Parses a Python file and returns a structured ModuleNode."""
    def __init__(self, config: ConfigLoader | None = None, plugins: list[PluginBase] | None = None):
        ...
    def parse_file(self, file_path: str) -> ModuleNode:
        ...

def parse_file(filepath: Path) -> list[dict]:
    ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\repometa\views.py

def format_file_focus(filepath: str, symbols: list[dict]) -> str:
    ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\src\test_app.py

pydantic.BaseModel
typing.List
typing.Optional

class User(BaseModel):
    """User data model."""

class UserService:
    """Business logic for User."""
    def __init__(self, db_conn: str):
        ...
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        ...

@fastapi(GET '/users/{user_id}')
async def read_user(user_id: int, q: Optional[str] = None) -> User:
    """
    Fetch a user by ID.
    Returns the user object if found.
    """
    ...

@fastapi(POST '/users/')
async def create_user(user: User) -> User:
    ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\tests\__init__.py

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\tests\fixtures\complex_module.py
"""Module docstring for complex_module.py"""

os
typing.List
typing.Optional

class OuterClass:
    """This is the outer class."""
    class InnerClass:
        """This is the inner class."""
        def __init__(self):
            ...
    async def update_data(self, items: list[str] | None = None) -> bool:
        """Updates the internal data state."""
        ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\tests\fixtures\inherit_test.py

class A(Exception):
    ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\tests\test_parser.py

os
pytest
src.parser.engine.SourceParser

def parser():
    ...

def test_symbol_extraction(parser):
    ...

def test_private_member_flag(parser):
    ...

def test_pruning_efficiency(parser):
    ...

def test_type_hint_unparsing(parser):
    ...

# ========================================

# File: D:\MyRepo\py-Repo-Meta\repometa\tests\test_parser_ac.py

ast
pathlib.Path
pytest
repometa.parser.ClassNode
repometa.parser.ConfigLoader
repometa.parser.FunctionNode
repometa.parser.ModuleNode
repometa.parser.PluginBase
repometa.parser.RepositoryParser
tempfile

class ApiMarkerPlugin(PluginBase):
    """Dummy plugin that tags functions with @router.get as API endpoints."""
    def on_function_extracted(self, node: ast.FunctionDef | ast.AsyncFunctionDef, meta: FunctionNode) -> None:
        ...

def test_ignore_internal_implementations():
    """
    Verify that the AST parser ignores internal logic (e.g., if/else, loops, assignments).
    The extracted FunctionNode should correctly capture the signature, but internal
    variables should not cause crashes or be extracted.
    """
    ...

def test_syntax_error_tolerance():
    """
    Verify that parsing a file with invalid Python syntax does not throw an exception.
    It should return a ModuleNode with parse_status == "UNPARSABLE" and populate error_msg.
    """
    ...

def test_configuration_private_filtering():
    """
    Verify that public and private functions/classes are filtered correctly based
    on the `include_private` configuration. `__init__` should always be included.
    """
    ...

def test_plugin_system_read_only_observer():
    """
    Verify that plugins can observe the AST node and mutate `meta.metadata_tags`
    dict without modifying the AST itself.
    """
    ...

def test_complex_signatures_and_type_hints():
    """
    Verify that complex arguments (type hints, defaults, *args, **kwargs)
    are correctly extracted and match exactly.
    """
    ...