import ast
import inspect
from typing import List, Optional
from ..models.schemas import ModuleSchema, ClassSchema, FunctionSchema

def clean_docstring(doc: str | None) -> str | None:
    if doc is None:
        return None
    return inspect.cleandoc(doc)

class SymbolVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.module = ModuleSchema(file_path=file_path)
        self._current_classes: List[ClassSchema] = []

    def visit_Module(self, node: ast.Module):
        self.module.docstring = clean_docstring(ast.get_docstring(node))
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.module.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module_name = node.module or ""
        for alias in node.names:
            if module_name:
                self.module.imports.append(f"{module_name}.{alias.name}")
            else:
                self.module.imports.append(f".{alias.name}")
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        is_private = node.name.startswith("_")
        bases = [ast.unparse(b) for b in node.bases]
        docstring = clean_docstring(ast.get_docstring(node))
        
        cls_schema = ClassSchema(
            name=node.name,
            line_number=node.lineno,
            docstring=docstring,
            is_private=is_private,
            bases=bases
        )

        if self._current_classes:
            self._current_classes[-1].nested_classes.append(cls_schema)
        else:
            self.module.classes.append(cls_schema)

        self._current_classes.append(cls_schema)
        
        # We must visit children explicitly because generic_visit 
        # visits everything including docstring again, but we just 
        # want to extract methods and nested classes without their bodies
        for child in node.body:
            self.visit(child)
            
        self._current_classes.pop()

    def _extract_parameters(self, args: ast.arguments) -> List[str]:
        params = []
        
        defaults_offset = len(args.posonlyargs) + len(args.args) - len(args.defaults)
        idx = 0
        for arg in args.posonlyargs + args.args:
            param_str = ast.unparse(arg)
            if idx >= defaults_offset:
                default_val = ast.unparse(args.defaults[idx - defaults_offset])
                param_str += f"={default_val}"
            params.append(param_str)
            idx += 1
            
        if args.vararg:
            params.append(f"*{ast.unparse(args.vararg)}")
            
        for i, arg in enumerate(args.kwonlyargs):
            param_str = ast.unparse(arg)
            if args.kw_defaults[i] is not None:
                default_val = ast.unparse(args.kw_defaults[i])
                param_str += f"={default_val}"
            params.append(param_str)
            
        if args.kwarg:
            params.append(f"**{ast.unparse(args.kwarg)}")
            
        return params

    def _parse_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool) -> FunctionSchema:
        is_private = node.name.startswith("_")
        docstring = clean_docstring(ast.get_docstring(node))
        
        parameters = self._extract_parameters(node.args)
            
        return_type = None
        if node.returns:
            return_type = ast.unparse(node.returns)
            
        func_schema = FunctionSchema(
            name=node.name,
            line_number=node.lineno,
            docstring=docstring,
            is_private=is_private,
            parameters=parameters,
            return_type=return_type,
            is_async=is_async
        )
        return func_schema

    def visit_FunctionDef(self, node: ast.FunctionDef):
        func_schema = self._parse_function(node, is_async=False)
        if self._current_classes:
            self._current_classes[-1].methods.append(func_schema)
        else:
            self.module.functions.append(func_schema)
        # Note: We intentionally do NOT visit the children of FunctionDef 
        # to ensure the body logic is pruned.

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        func_schema = self._parse_function(node, is_async=True)
        if self._current_classes:
            self._current_classes[-1].methods.append(func_schema)
        else:
            self.module.functions.append(func_schema)
        # Note: We intentionally do NOT visit the children of AsyncFunctionDef 
        # to ensure the body logic is pruned.
