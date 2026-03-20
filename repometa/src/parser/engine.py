import ast
from .visitor import SymbolVisitor
from ..models.schemas import ModuleSchema

class SourceParser:
    def __init__(self, file_path: str):
        self.file_path = file_path

    def parse(self) -> ModuleSchema:
        with open(self.file_path, "r", encoding="utf-8") as f:
            source = f.read()
            
        tree = ast.parse(source, filename=self.file_path)
        visitor = SymbolVisitor(self.file_path)
        visitor.visit(tree)
        
        return visitor.module
