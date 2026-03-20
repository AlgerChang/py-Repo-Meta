"""
Module docstring for complex_module.py
"""
import os
from typing import List, Optional

GLOBAL_VAR: str = "test"
"""This is a docstring for the global variable."""

class OuterClass:
    """This is the outer class."""
    
    _internal_state: int = 0
    
    class InnerClass:
        """This is the inner class."""
        def __init__(self):
            pass

    async def update_data(self, items: list[str] | None = None) -> bool:
        """
        Updates the internal data state.
        """
        if items:
            for i in items:
                self._internal_state += len(i)
                
        try:
            return True
        except Exception:
            return False

def _complex_pruning_target(a: int, b: int) -> int:
    """This function has complex logic to test pruning."""
    if a > b:
        return a
    else:
        for i in range(b):
            a += i
        return a
