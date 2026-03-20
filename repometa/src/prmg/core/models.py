from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class FunctionMetadata:
    """Represents metadata for a Python function or method."""
    name: str
    args: List[str]  # e.g., ["arg_name: type", "self"]
    return_type: Optional[str]
    docstring: Optional[str]
    is_async: bool = False

@dataclass
class ClassMetadata:
    """Represents metadata for a Python class."""
    name: str
    bases: List[str]  # List of inherited classes
    docstring: Optional[str]
    functions: List[FunctionMetadata] = field(default_factory=list)

@dataclass
class ModuleMetadata:
    """Represents metadata for a Python module (file)."""
    file_path: str
    file_hash: str  # SHA256 hash of the file content
    docstring: Optional[str]
    imports: List[str] = field(default_factory=list)
    classes: List[ClassMetadata] = field(default_factory=list)
    functions: List[FunctionMetadata] = field(default_factory=list)
