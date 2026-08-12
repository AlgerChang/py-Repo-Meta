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
    line_start: Optional[int] = None
    col_start: Optional[int] = None
    raw_reference: Optional[str] = None


@dataclass
class ConsumerReference:
    source_path: str
    source_symbol_qualname: str
    target_qualname: str
    base_edge_kind: str
    line_start: int
    col_start: int
    raw_reference: str
    origin: str = "python_ast"
