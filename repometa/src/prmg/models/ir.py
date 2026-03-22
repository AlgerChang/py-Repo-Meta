from dataclasses import dataclass
from typing import List, Optional

@dataclass
class FunctionMeta:
    name: str
    signature: str
    docstring: Optional[str]
    is_async: bool

@dataclass
class ClassMeta:
    name: str
    bases: List[str]
    docstring: Optional[str]
    methods: List[FunctionMeta]

@dataclass
class ModuleMeta:
    filepath: str
    docstring: Optional[str]
    imports: List[str]
    classes: List[ClassMeta]
    functions: List[FunctionMeta]
