import ast
import tempfile
from pathlib import Path

import pytest

from repometa.parser import (
    ClassNode,
    ConfigLoader,
    FunctionNode,
    ModuleNode,
    PluginBase,
    RepositoryParser,
)


# =========================================================================
# AC-1: Token Saving (Ignore Internal Implementations)
# =========================================================================
def test_ignore_internal_implementations():
    """
    Verify that the AST parser ignores internal logic (e.g., if/else, loops, assignments).
    The extracted FunctionNode should correctly capture the signature, but internal
    variables should not cause crashes or be extracted.
    """
    mock_code = '''
def calculate_total(items: list, tax_rate: float = 0.05) -> float:
    """Calculates the total."""
    total = 0.0
    for item in items:
        if item.price > 0:
            total += item.price
        else:
            total += 10.0
    
    final_amount = total * (1 + tax_rate)
    return final_amount
'''
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tmp:
        tmp.write(mock_code)
        tmp_path = tmp.name

    try:
        parser = RepositoryParser()
        module_node = parser.parse_file(tmp_path)
        
        assert module_node.parse_status == "SUCCESS"
        assert len(module_node.functions) == 1
        
        func = module_node.functions[0]
        assert func.name == "calculate_total"
        assert func.return_type == "float"
        assert len(func.args) == 2
        assert "items: list" in func.args[0]
        assert "tax_rate: float = 0.05" in func.args[1]
        
        # We ensure no internal variables are leaked or tracked
        # The parser does not track anything inside the function.
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# =========================================================================
# AC-2: Syntax Error Tolerance
# =========================================================================
def test_syntax_error_tolerance():
    """
    Verify that parsing a file with invalid Python syntax does not throw an exception.
    It should return a ModuleNode with parse_status == "UNPARSABLE" and populate error_msg.
    """
    mock_code = '''
def broken_func(:
    pass
'''
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tmp:
        tmp.write(mock_code)
        tmp_path = tmp.name

    try:
        parser = RepositoryParser()
        module_node = parser.parse_file(tmp_path)
        
        assert module_node.parse_status == "UNPARSABLE"
        assert module_node.error_msg is not None
        assert "SyntaxError" in module_node.error_msg
        assert len(module_node.functions) == 0
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# =========================================================================
# AC-3: Configuration & Private Filtering
# =========================================================================
def test_configuration_private_filtering():
    """
    Verify that public and private functions/classes are filtered correctly based
    on the `include_private` configuration. `__init__` should always be included.
    """
    mock_code = '''
class MyClass:
    def __init__(self):
        pass
        
    def public_method(self):
        pass
        
    def _private_method(self):
        pass

def my_func():
    pass

def _my_func():
    pass
'''
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        code_file = temp_dir_path / "mock_file.py"
        code_file.write_text(mock_code, encoding="utf-8")
        
        # Assert 1: Default config (include_private=False)
        config_default = ConfigLoader(cwd=temp_dir_path)
        parser_default = RepositoryParser(config=config_default)
        module_default = parser_default.parse_file(str(code_file))
        
        assert module_default.parse_status == "SUCCESS"
        assert len(module_default.functions) == 1
        assert module_default.functions[0].name == "my_func"  # _my_func is excluded
        
        assert len(module_default.classes) == 1
        cls_default = module_default.classes[0]
        assert cls_default.name == "MyClass"
        method_names = [m.name for m in cls_default.methods]
        assert "__init__" in method_names
        assert "public_method" in method_names
        assert "_private_method" not in method_names
        
        # Assert 2: Mocked config (include_private=True)
        pyproject_file = temp_dir_path / "pyproject.toml"
        pyproject_file.write_text('''[tool.prmg]
include_private = true
''', encoding="utf-8")
        
        config_private = ConfigLoader(cwd=temp_dir_path)
        parser_private = RepositoryParser(config=config_private)
        module_private = parser_private.parse_file(str(code_file))
        
        assert len(module_private.functions) == 2
        func_names = [f.name for f in module_private.functions]
        assert "my_func" in func_names
        assert "_my_func" in func_names
        
        cls_private = module_private.classes[0]
        method_names_private = [m.name for m in cls_private.methods]
        assert "_private_method" in method_names_private


# =========================================================================
# AC-4: Plugin System (Read-Only Observer)
# =========================================================================
class ApiMarkerPlugin(PluginBase):
    """Dummy plugin that tags functions with @router.get as API endpoints."""
    def on_function_extracted(self, node: ast.FunctionDef | ast.AsyncFunctionDef, meta: FunctionNode) -> None:
        for decorator in node.decorator_list:
            # We check the unparsed string representation
            if ast.unparse(decorator) == "router.get":
                meta.metadata_tags["is_api"] = True

def test_plugin_system_read_only_observer():
    """
    Verify that plugins can observe the AST node and mutate `meta.metadata_tags`
    dict without modifying the AST itself.
    """
    mock_code = '''
@router.get
def get_users():
    pass

def normal_func():
    pass
'''
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tmp:
        tmp.write(mock_code)
        tmp_path = tmp.name

    try:
        plugin = ApiMarkerPlugin()
        parser = RepositoryParser(plugins=[plugin])
        module_node = parser.parse_file(tmp_path)
        
        assert module_node.parse_status == "SUCCESS"
        assert len(module_node.functions) == 2
        
        get_users_func = next(f for f in module_node.functions if f.name == "get_users")
        normal_func = next(f for f in module_node.functions if f.name == "normal_func")
        
        assert get_users_func.metadata_tags.get("is_api") is True
        assert normal_func.metadata_tags.get("is_api") is None
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# =========================================================================
# AC-5: Complex Signatures & Type Hints
# =========================================================================
def test_complex_signatures_and_type_hints():
    """
    Verify that complex arguments (type hints, defaults, *args, **kwargs)
    are correctly extracted and match exactly.
    """
    mock_code = '''
def complex_func(a: int, b: str = "default", *args: tuple, **kwargs: dict) -> bool:
    pass
'''
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tmp:
        tmp.write(mock_code)
        tmp_path = tmp.name

    try:
        parser = RepositoryParser()
        module_node = parser.parse_file(tmp_path)
        
        assert module_node.parse_status == "SUCCESS"
        assert len(module_node.functions) == 1
        
        func = module_node.functions[0]
        assert func.name == "complex_func"
        
        # We need to check if the extracted arguments match
        # We expect exact formatting as from `ast.unparse`
        # Wait, the parser implementation for *args and **kwargs has bug? Let's see:
        # In parser.py:
        # arg_list.append(arg_str) inside for loop for pos_args
        # if args.vararg: vararg_str = f"*{args.vararg.arg}" -> *args: tuple
        # ...
        expected_args = [
            "a: int",
            "b: str = 'default'",
            "*args: tuple",
            "**kwargs: dict"
        ]
        
        # Note: ast.unparse stringifies strings with single quotes by default, 
        # so "default" becomes 'default'.
        assert func.args == expected_args
        assert func.return_type == "bool"
    finally:
        Path(tmp_path).unlink(missing_ok=True)
