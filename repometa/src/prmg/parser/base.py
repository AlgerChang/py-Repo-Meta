from abc import ABC, abstractmethod
from typing import Tuple, List

from prmg.storage.models import Symbol, Edge

class BaseParser(ABC):
    def __init__(self, project_root: str, plugin_config: dict | None = None):
        self.project_root = project_root
        self.plugin_config = plugin_config or {}
        
    @abstractmethod
    def parse_file(self, filepath: str) -> tuple[list[Symbol], list[Edge]]:
        pass
