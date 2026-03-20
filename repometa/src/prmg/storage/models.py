from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class File:
    filepath: str
    file_hash: str
    last_modified: float
    id: Optional[int] = None

@dataclass
class Symbol:
    file_id: int
    symbol_type: str
    name: str
    qualname: str
    line_start: int
    line_end: int
    parent_id: Optional[int] = None
    parent_qualname: Optional[str] = None  # Helper for hierarchical insertion
    docstring: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    id: Optional[int] = None

@dataclass
class Edge:
    source_symbol_id: int
    target_qualname: str
    edge_type: str
