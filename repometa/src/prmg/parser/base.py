from abc import ABC, abstractmethod
from typing import Tuple, List

from prmg.storage.models import Symbol, Edge

class BaseParser(ABC):
    def __init__(self, project_root: str):
        self.project_root = project_root
        
    @abstractmethod
    def parse_file(self, filepath: str) -> tuple[list[Symbol], list[Edge]]:
        pass
