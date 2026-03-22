import ast
import pathlib
from typing import Any, Optional

from .base import BaseParser
from prmg.storage.models import Symbol, Edge
from prmg.core.extension import PluginManager, LocalContext

def _get_module_fqn(project_root: str, filepath: str) -> str:
    root_path = pathlib.Path(project_root).resolve()
    file_path = pathlib.Path(filepath).resolve()
    
    try:
        rel_path = file_path.relative_to(root_path)
    except ValueError:
        rel_path = pathlib.Path(filepath)
        
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


class _MetadataVisitor(ast.NodeVisitor):
    def __init__(self, module_fqn: str, filepath: str, plugin_manager: PluginManager, raw_ast: ast.AST):
        self.module_fqn = module_fqn
        self.filepath = filepath
        self.plugin_manager = plugin_manager
        self.raw_ast = raw_ast
        self.symbols: list[Symbol] = []
        self.edges: list[Edge] = []
        self.current_id = 0
        
        # 維護命名空間狀態: list of (name, type, symbol_id)
        self._namespace_stack: list[tuple[str, str, int]] = []

    def _get_local_context(self) -> LocalContext:
        return LocalContext(
            file_path=self.filepath,
            current_module_name=self.module_fqn,
            raw_ast=self.raw_ast
        )
        
    @property
    def current_qualname(self) -> str:
        parts = [name for name, _, _ in self._namespace_stack if name]
        return ".".join(parts)

    def _get_parent_qualname(self) -> Optional[str]:
        if not self._namespace_stack:
            return None
        return self.current_qualname

    def _push_namespace(self, name: str, node_type: str, sym_id: int):
        self._namespace_stack.append((name, node_type, sym_id))
        
    def _pop_namespace(self):
        self._namespace_stack.pop()

    def _extract_args(self, args: ast.arguments) -> list[dict[str, Any]]:
        parsed_args = []
        
        all_pos_args = getattr(args, 'posonlyargs', []) + args.args
        defaults = args.defaults
        defaults_start = len(all_pos_args) - len(defaults)
        
        for i, arg in enumerate(all_pos_args):
            default_str = None
            if i >= defaults_start:
                def_node = defaults[i - defaults_start]
                try:
                    default_str = ast.unparse(def_node)
                except Exception:
                    pass
            type_str = None
            if arg.annotation:
                try:
                    type_str = ast.unparse(arg.annotation)
                except Exception:
                    pass
            parsed_args.append({"name": arg.arg, "type": type_str, "default": default_str})
            
        if args.vararg:
            type_str = None
            if args.vararg.annotation:
                try:
                    type_str = ast.unparse(args.vararg.annotation)
                except Exception:
                    pass
            parsed_args.append({"name": f"*{args.vararg.arg}", "type": type_str, "default": None})
            
        for i, arg in enumerate(args.kwonlyargs):
            default_str = None
            if args.kw_defaults and i < len(args.kw_defaults) and args.kw_defaults[i] is not None:
                try:
                    default_str = ast.unparse(args.kw_defaults[i])
                except Exception:
                    pass
            type_str = None
            if arg.annotation:
                try:
                    type_str = ast.unparse(arg.annotation)
                except Exception:
                    pass
            parsed_args.append({"name": arg.arg, "type": type_str, "default": default_str})
            
        if args.kwarg:
            type_str = None
            if args.kwarg.annotation:
                try:
                    type_str = ast.unparse(args.kwarg.annotation)
                except Exception:
                    pass
            parsed_args.append({"name": f"**{args.kwarg.arg}", "type": type_str, "default": None})
            
        return parsed_args

    def _extract_return_type(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> Optional[str]:
        if node.returns:
            try:
                return ast.unparse(node.returns)
            except Exception:
                pass
        return None

    def visit_Module(self, node: ast.Module):
        self.current_id += 1
        sym_id = self.current_id
        
        qualname = self.module_fqn
        name = self.module_fqn.split('.')[-1] if self.module_fqn else ''
        
        sym = Symbol(
            file_id=0,
            id=sym_id,
            symbol_type='module',
            name=name,
            qualname=qualname,
            line_start=getattr(node, 'lineno', 1),
            line_end=getattr(node, 'end_lineno', 1),
            parent_id=None,
            parent_qualname=None,
            docstring=ast.get_docstring(node),
            metadata={}
        )
        ext_meta = self.plugin_manager.run_visit_node(node, self._get_local_context())
        if ext_meta:
            sym.metadata["plugins"] = ext_meta
        self.symbols.append(sym)
        self._push_namespace(self.module_fqn, 'module', sym_id)
        
        for child in getattr(node, 'body', []):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
                self.visit(child)
        
        self._pop_namespace()

    def visit_ClassDef(self, node: ast.ClassDef):
        parent_qualname = self._get_parent_qualname()
        
        self.current_id += 1
        sym_id = self.current_id
        
        self._push_namespace(node.name, 'class', sym_id)
        qualname = self.current_qualname
        
        sym = Symbol(
            file_id=0,
            id=sym_id,
            symbol_type='class',
            name=node.name,
            qualname=qualname,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            parent_id=None,
            parent_qualname=parent_qualname,
            docstring=ast.get_docstring(node),
            metadata={}
        )
        ext_meta = self.plugin_manager.run_visit_node(node, self._get_local_context())
        if ext_meta:
            sym.metadata["plugins"] = ext_meta
        self.symbols.append(sym)
        
        for base in node.bases:
            try:
                base_str = ast.unparse(base)
                self.edges.append(Edge(
                    source_symbol_id=sym_id,
                    target_qualname=base_str,
                    edge_type='inherits'
                ))
            except Exception:
                pass
                
        for child in getattr(node, 'body', []):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self.visit(child)
                
        self._pop_namespace()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._handle_function(node, is_async=False)
        
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._handle_function(node, is_async=True)

    def _handle_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool):
        parent_qualname = self._get_parent_qualname()
        parent_type = self._namespace_stack[-1][1] if self._namespace_stack else 'module'
        sym_type = 'method' if parent_type == 'class' else 'function'
        
        self.current_id += 1
        sym_id = self.current_id
        
        self._push_namespace(node.name, sym_type, sym_id)
        qualname = self.current_qualname
        
        sym = Symbol(
            file_id=0,
            id=sym_id,
            symbol_type=sym_type,
            name=node.name,
            qualname=qualname,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            parent_id=None,
            parent_qualname=parent_qualname,
            docstring=ast.get_docstring(node),
            metadata={
                "is_async": is_async,
                "args": self._extract_args(node.args),
                "returns": self._extract_return_type(node)
            }
        )
        ext_meta = self.plugin_manager.run_visit_node(node, self._get_local_context())
        if ext_meta:
            sym.metadata["plugins"] = ext_meta
        self.symbols.append(sym)
        
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self.visit(child)
                
        self._pop_namespace()

    def visit_Import(self, node: ast.Import):
        current_id = self._namespace_stack[-1][2] if self._namespace_stack else 0
        for alias in node.names:
            self.edges.append(Edge(
                source_symbol_id=current_id,
                target_qualname=alias.name,
                edge_type='imports'
            ))

    def visit_ImportFrom(self, node: ast.ImportFrom):
        current_id = self._namespace_stack[-1][2] if self._namespace_stack else 0
        module = node.module or ""
        level = node.level or 0
        
        if level > 0:
            parts = self.module_fqn.split('.') if self.module_fqn else []
            if len(parts) >= level:
                base = ".".join(parts[:-level])
                if base:
                    target_mod = f"{base}.{module}" if module else base
                else:
                    target_mod = module
            else:
                target_mod = module
        else:
            target_mod = module
            
        for alias in node.names:
            target_qualname = f"{target_mod}.{alias.name}" if target_mod else alias.name
            self.edges.append(Edge(
                source_symbol_id=current_id,
                target_qualname=target_qualname,
                edge_type='imports'
            ))


class ASTParser(BaseParser):
    def parse_file(self, filepath: str) -> tuple[list[Symbol], list[Edge]]:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
            
        tree = ast.parse(source, filename=filepath)
        module_fqn = _get_module_fqn(self.project_root, filepath)
        
        plugin_manager = PluginManager(self.plugin_config)
        visitor = _MetadataVisitor(module_fqn, filepath, plugin_manager, tree)
        visitor.visit(tree)
        
        return visitor.symbols, visitor.edges
