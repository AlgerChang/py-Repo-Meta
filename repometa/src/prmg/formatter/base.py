from abc import ABC, abstractmethod
from typing import Iterator

from prmg.models.ir import ClassMeta, FunctionMeta, ModuleMeta

class BaseFormatter(ABC):
    def __init__(self, include_docstrings: bool = True, optimize_tokens: bool = True) -> None:
        self.include_docstrings = include_docstrings
        self.optimize_tokens = optimize_tokens

    @abstractmethod
    def format_function(self, func: FunctionMeta, indent_level: int = 0) -> str:
        pass

    @abstractmethod
    def format_class(self, cls: ClassMeta, indent_level: int = 0) -> str:
        pass

    @abstractmethod
    def format_module(self, module: ModuleMeta) -> str:
        pass

    @abstractmethod
    def generate_repository_context(self, modules: Iterator[ModuleMeta]) -> str:
        pass
