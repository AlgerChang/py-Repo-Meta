import os
import pytest
from src.parser.engine import SourceParser

@pytest.fixture
def parser():
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "complex_module.py")
    return SourceParser(fixture_path)

def test_symbol_extraction(parser):
    module = parser.parse()
    
    assert module.file_path.endswith("complex_module.py")
    assert "os" in module.imports
    assert "typing.List" in module.imports
    assert "typing.Optional" in module.imports
    
    assert len(module.classes) == 1
    outer_class = module.classes[0]
    assert outer_class.name == "OuterClass"
    
    assert len(outer_class.nested_classes) == 1
    inner_class = outer_class.nested_classes[0]
    assert inner_class.name == "InnerClass"
    
    # OuterClass should have update_data method
    assert len(outer_class.methods) == 1
    update_data_method = outer_class.methods[0]
    assert update_data_method.name == "update_data"
    assert update_data_method.is_async is True
    
    # Check functions in module
    assert len(module.functions) == 1
    complex_func = module.functions[0]
    assert complex_func.name == "_complex_pruning_target"

def test_private_member_flag(parser):
    module = parser.parse()
    
    # Check private function
    complex_func = module.functions[0]
    assert complex_func.name == "_complex_pruning_target"
    assert complex_func.is_private is True
    
    # Note: Currently the parser does not extract class attributes like _internal_state
    # If it did, we would check that here too. Since it extracts methods, we can check 
    # __init__ on InnerClass if we want, but __init__ isn't strictly private by the _ prefix rule.
    # The requirement was "驗證以 _ 開頭的成員其 is_private 欄位是否為 True".
    # _complex_pruning_target satisfies this.

def test_pruning_efficiency(parser):
    module = parser.parse()
    
    complex_func = module.functions[0]
    
    # The schema only has specific fields. Let's verify they don't contain implementation logic.
    assert complex_func.name == "_complex_pruning_target"
    assert complex_func.return_type == "int"
    assert complex_func.parameters == ["a: int", "b: int"]
    assert "complex logic" in complex_func.docstring
    
    # Pydantic schema will ensure no extra fields like 'body' or logic nodes exist
    assert not hasattr(complex_func, 'body')
    assert not hasattr(complex_func, 'if_statements')

def test_type_hint_unparsing(parser):
    module = parser.parse()
    outer_class = module.classes[0]
    update_data_method = outer_class.methods[0]
    
    # Verifying complex type hint for `items: list[str] | None = None`
    assert update_data_method.parameters == ["self", "items: list[str] | None=None"]
    assert update_data_method.return_type == "bool"
