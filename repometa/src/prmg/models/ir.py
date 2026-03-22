from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class FunctionMeta:
    name: str
    signature: str
    docstring: Optional[str]
    is_async: bool
    plugins: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ClassMeta:
    name: str
    bases: List[str]
    docstring: Optional[str]
    methods: List[FunctionMeta]
    nested_classes: List['ClassMeta'] = field(default_factory=list)
    plugins: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ModuleMeta:
    filepath: str
    docstring: Optional[str]
    imports: List[str]
    classes: List[ClassMeta]
    functions: List[FunctionMeta]
