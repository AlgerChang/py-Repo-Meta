import ast
import pathlib
from typing import Any, Optional

from .base import BaseParser
from prmg.core.command_dependencies import (
    extract_command_targets,
    extract_command_token_targets,
)
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


class _LocalNameCollector(ast.NodeVisitor):
    """Collect names bound by one function without entering nested scopes."""

    def __init__(self) -> None:
        self.names: set[str] = set()
        self.nonlocal_names: set[str] = set()
        self.definitions: set[str] = set()
        self._comprehension_targets: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        if (
            isinstance(node.ctx, (ast.Store, ast.Del))
            and node.id not in self._comprehension_targets
        ):
            self.names.add(node.id)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.names.add(node.name)
        self.definitions.add(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.names.add(node.name)
        self.definitions.add(node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.names.add(node.name)
        self.definitions.add(node.name)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    def _visit_comprehension(
        self,
        node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp,
        values: list[ast.AST],
    ) -> None:
        saved_targets = set(self._comprehension_targets)
        for generator in node.generators:
            self.visit(generator.iter)
            self._comprehension_targets.update(
                child.id
                for child in ast.walk(generator.target)
                if isinstance(child, ast.Name)
            )
            for condition in generator.ifs:
                self.visit(condition)
        for value in values:
            self.visit(value)
        self._comprehension_targets = saved_targets

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension(node, [node.elt])

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension(node, [node.elt])

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension(node, [node.key, node.value])

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension(node, [node.elt])

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.names.add(alias.asname or alias.name.split(".")[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name != "*":
                self.names.add(alias.asname or alias.name)

    def visit_Global(self, node: ast.Global) -> None:
        self.nonlocal_names.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.nonlocal_names.update(node.names)


class _MetadataVisitor(ast.NodeVisitor):
    def __init__(
        self,
        module_fqn: str,
        filepath: str,
        project_root: str,
        plugin_manager: PluginManager,
        raw_ast: ast.AST,
        include_private: bool = True,
    ):
        self.module_fqn = module_fqn
        self.filepath = filepath
        self.project_root = pathlib.Path(project_root).resolve()
        self.plugin_manager = plugin_manager
        self.raw_ast = raw_ast
        self.symbols: list[Symbol] = []
        self.edges: list[Edge] = []
        self.current_id = 0
        self.include_private = include_private
        
        # 維護命名空間狀態: list of (name, type, symbol_id)
        self._namespace_stack: list[tuple[str, str, int]] = []
        self._binding_stack: list[dict[str, Optional[str]]] = []
        self._call_alias_stack: list[dict[str, Optional[str]]] = []
        self._type_stack: list[dict[str, Optional[str]]] = []
        self._command_stack: list[dict[str, Optional[list[str]]]] = []
        self._constant_stack: list[dict[str, Optional[str]]] = []
        self._symbol_qualnames: set[str] = set()
        self._symbol_ids_by_qualname: dict[str, int] = {}
        self._declared_code_qualnames: set[str] = set()

    def _should_include(self, name: str) -> bool:
        if self.include_private:
            return True
        if name.startswith("_") and name != "__init__":
            return False
        return True

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

    def _push_namespace(
        self,
        name: str,
        node_type: str,
        sym_id: int,
        bindings: Optional[dict[str, Optional[str]]] = None,
    ):
        self._namespace_stack.append((name, node_type, sym_id))
        initial_bindings = dict(bindings or {})
        shadowed_names = {bound_name: None for bound_name in initial_bindings}
        self._binding_stack.append(initial_bindings)
        self._call_alias_stack.append(dict(shadowed_names))
        self._type_stack.append(dict(shadowed_names))
        self._command_stack.append(dict(shadowed_names))
        self._constant_stack.append(dict(shadowed_names))
        
    def _pop_namespace(self):
        self._namespace_stack.pop()
        self._binding_stack.pop()
        self._call_alias_stack.pop()
        self._type_stack.pop()
        self._command_stack.pop()
        self._constant_stack.pop()

    @property
    def _current_symbol_id(self) -> int:
        return self._namespace_stack[-1][2] if self._namespace_stack else 0

    @property
    def _current_namespace_type(self) -> str:
        return self._namespace_stack[-1][1] if self._namespace_stack else "module"

    def _claim_symbol_id(self, qualname: str) -> tuple[int, bool]:
        existing_id = self._symbol_ids_by_qualname.get(qualname)
        if existing_id is not None:
            # ponytail: alternative definitions share first-definition metadata;
            # add branch-aware symbol variants before exposing both definitions.
            return existing_id, False
        self.current_id += 1
        self._symbol_ids_by_qualname[qualname] = self.current_id
        return self.current_id, True

    def _lookup(self, stack: list[dict[str, Any]], name: str) -> Any:
        skip_class_scope = self._current_namespace_type in {"function", "method"}
        for scope, (_, namespace_type, _) in zip(
            reversed(stack),
            reversed(self._namespace_stack),
        ):
            if skip_class_scope and namespace_type == "class":
                continue
            if name in scope:
                return scope[name]
        return None

    def _bind(self, name: str, target: Optional[str]) -> None:
        if self._binding_stack:
            self._binding_stack[-1][name] = target

    def _bind_call_alias(self, name: str, target: str) -> None:
        if self._call_alias_stack:
            self._call_alias_stack[-1][name] = target

    def _bind_type(self, name: str, target: str) -> None:
        if self._type_stack:
            self._type_stack[-1][name] = target

    def _bind_command(self, name: str, tokens: list[str]) -> None:
        if self._command_stack:
            self._command_stack[-1][name] = tokens

    def _bind_constant(self, name: str, value: str) -> None:
        if self._constant_stack:
            self._constant_stack[-1][name] = value

    def _clear_derived_bindings(self, name: str) -> None:
        if self._call_alias_stack:
            self._call_alias_stack[-1][name] = None
        if self._type_stack:
            self._type_stack[-1][name] = None
        if self._command_stack:
            self._command_stack[-1][name] = None
        if self._constant_stack:
            self._constant_stack[-1][name] = None

    def _resolve_expr(self, node: ast.AST | None) -> Optional[str]:
        if isinstance(node, ast.Name):
            return self._lookup(self._binding_stack, node.id)
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                value_type = self._lookup(self._type_stack, node.value.id)
                if value_type:
                    return f"{value_type}.{node.attr}"
                call_alias = self._lookup(self._call_alias_stack, node.value.id)
                if call_alias:
                    return f"{call_alias}.{node.attr}"
            base = self._resolve_expr(node.value)
            if base:
                return f"{base}.{node.attr}"
        return None

    def _resolve_call_target(self, node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Name):
            call_alias = self._lookup(self._call_alias_stack, node.id)
            if call_alias:
                return call_alias
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Call):
            constructed_type = self._resolve_call_target(node.value.func)
            if constructed_type:
                return f"{constructed_type}.{node.attr}"
        return self._resolve_expr(node)

    def _raw(self, node: ast.AST) -> str:
        try:
            return ast.unparse(node)
        except Exception:
            return ""

    def _annotation_targets(self, node: ast.AST | None) -> list[tuple[str, ast.AST]]:
        if node is None:
            return []
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                parsed = ast.parse(node.value, mode="eval").body
            except SyntaxError:
                return []
            return [
                (target, node)
                for target, _ in self._annotation_targets(parsed)
            ]
        if isinstance(node, ast.Attribute):
            target = self._resolve_expr(node)
            return [(target, node)] if target else []
        if isinstance(node, ast.Name):
            target = self._resolve_expr(node)
            return [(target, node)] if target else []

        targets: list[tuple[str, ast.AST]] = []
        for child in ast.iter_child_nodes(node):
            targets.extend(self._annotation_targets(child))
        return targets

    def _append_edge(self, target: Optional[str], edge_type: str, node: ast.AST) -> None:
        if not target:
            return
        self.edges.append(
            Edge(
                source_symbol_id=self._current_symbol_id,
                target_qualname=target,
                edge_type=edge_type,
                line_start=getattr(node, "lineno", 1),
                col_start=getattr(node, "col_offset", 0),
                raw_reference=self._raw(node),
            )
        )

    def _prebind_symbol_definitions(self, body: list[ast.stmt]) -> None:
        parent = self.current_qualname
        collector = _LocalNameCollector()
        for child in body:
            collector.visit(child)
        for name in collector.definitions:
            qualname = f"{parent}.{name}"
            self._bind(name, qualname)
            self._declared_code_qualnames.add(qualname)

        for child in body:
            if self._current_namespace_type in {"module", "class"}:
                targets: list[ast.expr] = []
                if isinstance(child, ast.Assign):
                    targets = child.targets
                elif isinstance(child, ast.AnnAssign):
                    targets = [child.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        self._bind(target.id, f"{parent}.{target.id}")

    def _add_data_symbol(self, name: str, node: ast.AST) -> None:
        if self._current_namespace_type not in {"module", "class"}:
            return
        if not self._should_include(name):
            return
        qualname = f"{self.current_qualname}.{name}"
        if qualname in self._symbol_qualnames or qualname in self._declared_code_qualnames:
            return
        sym_id, _ = self._claim_symbol_id(qualname)
        self.symbols.append(
            Symbol(
                file_id=0,
                id=sym_id,
                symbol_type="data",
                name=name,
                qualname=qualname,
                line_start=getattr(node, "lineno", 1),
                line_end=getattr(node, "end_lineno", getattr(node, "lineno", 1)),
                parent_id=None,
                parent_qualname=self.current_qualname,
                docstring=None,
                metadata={},
            )
        )
        self._symbol_qualnames.add(qualname)

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
        qualname = self.module_fqn
        name = self.module_fqn.split('.')[-1] if self.module_fqn else ''
        sym_id, _ = self._claim_symbol_id(qualname)
        
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
        self._symbol_qualnames.add(qualname)
        self._push_namespace(self.module_fqn, 'module', sym_id)
        self._prebind_symbol_definitions(node.body)

        for child in node.body:
            self.visit(child)
        
        self._pop_namespace()

    def visit_ClassDef(self, node: ast.ClassDef):
        if not self._should_include(node.name):
            return

        for decorator in node.decorator_list:
            self.visit(decorator)

        parent_qualname = self._get_parent_qualname()
        
        qualname = f"{parent_qualname}.{node.name}" if parent_qualname else node.name
        sym_id, is_new = self._claim_symbol_id(qualname)
        if is_new:
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
            self._symbol_qualnames.add(qualname)
        
        for base in node.bases:
            base_target = self._resolve_expr(base) or self._raw(base)
            self.edges.append(
                Edge(
                    source_symbol_id=sym_id,
                    target_qualname=base_target,
                    edge_type='inherits',
                    line_start=getattr(base, "lineno", node.lineno),
                    col_start=getattr(base, "col_offset", node.col_offset),
                    raw_reference=self._raw(base),
                )
            )
            if any(isinstance(child, ast.Call) for child in ast.walk(base)):
                self.visit(base)

        self._push_namespace(node.name, 'class', sym_id)
        self._prebind_symbol_definitions(node.body)
        for child in node.body:
            self.visit(child)
                
        self._pop_namespace()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._handle_function(node, is_async=False)
        
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._handle_function(node, is_async=True)

    def _handle_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool):
        if not self._should_include(node.name):
            return

        for decorator in node.decorator_list:
            self.visit(decorator)
        for default in [*node.args.defaults, *[value for value in node.args.kw_defaults if value is not None]]:
            self.visit(default)

        parent_qualname = self._get_parent_qualname()
        parent_type = self._namespace_stack[-1][1] if self._namespace_stack else 'module'
        sym_type = 'method' if parent_type == 'class' else 'function'

        argument_types: dict[str, str] = {}
        annotation_references: list[tuple[str, ast.AST]] = []
        all_arguments = [
            *getattr(node.args, "posonlyargs", []),
            *node.args.args,
            *node.args.kwonlyargs,
        ]
        if node.args.vararg:
            all_arguments.append(node.args.vararg)
        if node.args.kwarg:
            all_arguments.append(node.args.kwarg)
        for argument in all_arguments:
            annotation_targets = self._annotation_targets(argument.annotation)
            annotation_references.extend(annotation_targets)
            resolved_annotation = self._resolve_expr(argument.annotation)
            if not resolved_annotation:
                if annotation_targets:
                    resolved_annotation = annotation_targets[-1][0]
            if resolved_annotation:
                argument_types[argument.arg] = resolved_annotation
        annotation_references.extend(self._annotation_targets(node.returns))
        
        qualname = f"{parent_qualname}.{node.name}" if parent_qualname else node.name
        sym_id, is_new = self._claim_symbol_id(qualname)
        if is_new:
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
            self._symbol_qualnames.add(qualname)

        collector = _LocalNameCollector()
        for child in node.body:
            collector.visit(child)
        collector.names.difference_update(collector.nonlocal_names)
        for argument in all_arguments:
            collector.names.add(argument.arg)

        self._push_namespace(
            node.name,
            sym_type,
            sym_id,
            bindings={name: None for name in collector.names},
        )
        self._prebind_symbol_definitions(node.body)
        for argument_name, target in argument_types.items():
            self._bind_type(argument_name, target)
        for target, target_node in annotation_references:
            self._append_edge(target, "type_reference", target_node)

        if parent_type == "class" and parent_qualname and all_arguments:
            receiver_name = all_arguments[0].arg
            if receiver_name in {"self", "cls"}:
                self._bind(receiver_name, parent_qualname)
                self._bind_type(receiver_name, parent_qualname)

        for child in node.body:
            self.visit(child)
                
        self._pop_namespace()

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self._append_edge(alias.name, "imports", node)
            if alias.asname:
                self._clear_derived_bindings(alias.asname)
                self._bind(alias.asname, alias.name)
            else:
                root_name = alias.name.split(".")[0]
                self._clear_derived_bindings(root_name)
                self._bind(root_name, root_name)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        level = node.level or 0

        if level > 0:
            package_parts = self.module_fqn.split(".") if self.module_fqn else []
            if pathlib.Path(self.filepath).name != "__init__.py":
                package_parts = package_parts[:-1]
            ascend = max(level - 1, 0)
            if ascend:
                package_parts = package_parts[:-ascend] if len(package_parts) >= ascend else []
            base = ".".join(package_parts)
            target_mod = f"{base}.{module}" if base and module else base or module
        else:
            target_mod = module

        for alias in node.names:
            target_qualname = (
                target_mod
                if alias.name == "*"
                else f"{target_mod}.{alias.name}" if target_mod else alias.name
            )
            self._append_edge(target_qualname, "imports", node)
            if alias.name != "*":
                bound_name = alias.asname or alias.name
                self._clear_derived_bindings(bound_name)
                self._bind(bound_name, target_qualname)

    def _assignment_names(self, node: ast.AST) -> list[str]:
        if isinstance(node, ast.Name):
            return [node.id]
        if isinstance(node, (ast.Tuple, ast.List)):
            names: list[str] = []
            for element in node.elts:
                names.extend(self._assignment_names(element))
            return names
        return []

    def _record_assignment_bindings(self, names: list[str], value: ast.AST) -> None:
        alias_target = None
        inferred_type = None
        if isinstance(value, (ast.Name, ast.Attribute)):
            alias_target = self._resolve_expr(value)
        elif isinstance(value, ast.Call):
            inferred_type = self._resolve_call_target(value.func)
        command_tokens = self._command_tokens_from_ast(value)
        constant_value = (
            value.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str)
            else None
        )

        for name in names:
            self._clear_derived_bindings(name)
            if self._current_namespace_type in {"module", "class"}:
                self._add_data_symbol(name, value)
                self._bind(name, f"{self.current_qualname}.{name}")
            else:
                self._bind(name, None)
            if alias_target:
                self._bind_call_alias(name, alias_target)
            if inferred_type:
                self._bind_type(name, inferred_type)
            if command_tokens:
                self._bind_command(name, command_tokens)
            if constant_value is not None:
                self._bind_constant(name, constant_value)

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        names: list[str] = []
        for target in node.targets:
            names.extend(self._assignment_names(target))
        self._record_assignment_bindings(names, node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        for target, target_node in self._annotation_targets(node.annotation):
            self._append_edge(target, "type_reference", target_node)
        if node.value is not None:
            self.visit(node.value)
            self._record_assignment_bindings(
                self._assignment_names(node.target),
                node.value,
            )
        else:
            for name in self._assignment_names(node.target):
                self._clear_derived_bindings(name)
                if self._current_namespace_type in {"module", "class"}:
                    self._add_data_symbol(name, node)
                    self._bind(name, f"{self.current_qualname}.{name}")
                else:
                    self._bind(name, None)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.visit(node.value)
        self._record_assignment_bindings(
            self._assignment_names(node.target),
            node.value,
        )

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        target = self._resolve_expr(node.target)
        if target:
            self._append_edge(target, "references", node.target)
        else:
            self.visit(node.target)
        self.visit(node.value)

    def _command_tokens_from_ast(self, node: ast.AST) -> Optional[list[str]]:
        if isinstance(node, (ast.List, ast.Tuple)):
            tokens: list[str] = []
            for element in node.elts:
                if isinstance(element, ast.Constant) and isinstance(element.value, str):
                    tokens.append(element.value)
                elif isinstance(element, ast.Attribute) and self._raw(element) == "sys.executable":
                    tokens.append("python")
                elif isinstance(element, ast.Name):
                    constant = self._lookup(self._constant_stack, element.id)
                    if constant is None:
                        return None
                    tokens.append(constant)
                else:
                    return None
            return tokens
        return None

    def _record_command_dependency(self, node: ast.Call, call_target: Optional[str]) -> None:
        if call_target not in {
            "os.system",
            "subprocess.call",
            "subprocess.check_call",
            "subprocess.check_output",
            "subprocess.Popen",
            "subprocess.run",
        }:
            return

        command_node: ast.AST | None = node.args[0] if node.args else None
        if command_node is None:
            command_node = next(
                (keyword.value for keyword in node.keywords if keyword.arg in {"args", "command"}),
                None,
            )
        if command_node is None:
            return

        targets: list[str] = []
        if isinstance(command_node, ast.Constant) and isinstance(command_node.value, str):
            targets = extract_command_targets(command_node.value, self.project_root)
        elif isinstance(command_node, ast.Name):
            tokens = self._lookup(self._command_stack, command_node.id)
            if tokens:
                targets = extract_command_token_targets(tokens, self.project_root)
            else:
                command = self._lookup(self._constant_stack, command_node.id)
                if command:
                    targets = extract_command_targets(command, self.project_root)
        else:
            tokens = self._command_tokens_from_ast(command_node)
            if tokens:
                targets = extract_command_token_targets(tokens, self.project_root)
        for target in targets:
            self._append_edge(target, "command_dependency", node)

    def visit_Call(self, node: ast.Call) -> None:
        call_target = self._resolve_call_target(node.func)
        self._append_edge(call_target, "calls", node)
        self._record_command_dependency(node, call_target)
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Call):
            self.visit(node.func.value)
        elif call_target is None:
            self.visit(node.func)
        for argument in node.args:
            self.visit(argument)
        for keyword in node.keywords:
            self.visit(keyword.value)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for default in [
            *node.args.defaults,
            *[value for value in node.args.kw_defaults if value is not None],
        ]:
            self.visit(default)
        arguments = [
            *getattr(node.args, "posonlyargs", []),
            *node.args.args,
            *node.args.kwonlyargs,
        ]
        if node.args.vararg:
            arguments.append(node.args.vararg)
        if node.args.kwarg:
            arguments.append(node.args.kwarg)

        source_symbol_id = self._current_symbol_id
        self._push_namespace(
            "",
            "function",
            source_symbol_id,
            bindings={argument.arg: None for argument in arguments},
        )
        self.visit(node.body)
        self._pop_namespace()

    def _visit_comprehension(
        self,
        node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp,
        values: list[ast.AST],
    ) -> None:
        source_symbol_id = self._current_symbol_id
        first_generator = node.generators[0]
        self.visit(first_generator.iter)
        self._push_namespace("", "function", source_symbol_id)
        for index, generator in enumerate(node.generators):
            if index:
                self.visit(generator.iter)
            for name in self._assignment_names(generator.target):
                self._bind(name, None)
                self._clear_derived_bindings(name)
            for condition in generator.ifs:
                self.visit(condition)
        for value in values:
            self.visit(value)
        self._pop_namespace()

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension(node, [node.elt])

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension(node, [node.elt])

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension(node, [node.key, node.value])

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension(node, [node.elt])

    def visit_Name(self, node: ast.Name) -> None:
        if not isinstance(node.ctx, ast.Load):
            return
        self._append_edge(self._resolve_expr(node), "references", node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if not isinstance(node.ctx, ast.Load):
            return
        target = self._resolve_expr(node)
        if target:
            self._append_edge(target, "references", node)
        else:
            self.visit(node.value)


import tomllib

class ASTParser(BaseParser):
    def _load_config(self) -> dict:
        pyproject_path = pathlib.Path(self.project_root) / "pyproject.toml"
        if pyproject_path.exists():
            try:
                with open(pyproject_path, "rb") as f:
                    data = tomllib.load(f)
                return data.get("tool", {}).get("prmg", {})
            except Exception:
                pass
        return {}

    def symbol_visibility(self) -> str:
        config = self._load_config()
        return "all" if config.get("include_private", True) else "public_only"

    def parse_file(self, filepath: str) -> tuple[list[Symbol], list[Edge]]:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            source = f.read()
            
        tree = ast.parse(source, filename=filepath)
        module_fqn = _get_module_fqn(self.project_root, filepath)
        
        config = self._load_config()
        # Navigation must be able to locate every defined symbol by default.
        # A repository can explicitly opt into a public-only summary with
        # ``[tool.prmg] include_private = false``.
        include_private = config.get("include_private", True)
        
        plugin_manager = PluginManager(self.plugin_config)
        visitor = _MetadataVisitor(
            module_fqn,
            filepath,
            self.project_root,
            plugin_manager,
            tree,
            include_private=include_private,
        )
        visitor.visit(tree)
        
        return visitor.symbols, visitor.edges
