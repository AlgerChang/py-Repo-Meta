from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional

class FunctionSchema(BaseModel):
    name: str
    line_number: int
    docstring: Optional[str] = None
    is_private: bool = False
    parameters: List[str] = Field(default_factory=list)
    return_type: Optional[str] = None
    is_async: bool = False

class ClassSchema(BaseModel):
    name: str
    line_number: int
    docstring: Optional[str] = None
    is_private: bool = False
    bases: List[str] = Field(default_factory=list)
    methods: List[FunctionSchema] = Field(default_factory=list)
    nested_classes: List[ClassSchema] = Field(default_factory=list)

class ModuleSchema(BaseModel):
    file_path: str
    docstring: Optional[str] = None
    imports: List[str] = Field(default_factory=list)
    classes: List[ClassSchema] = Field(default_factory=list)
    functions: List[FunctionSchema] = Field(default_factory=list)
