"""
Extension Layer (Plugin System) for Python Repository Metadata Generator (PRMG).

This module provides the architecture for a plugin-based system to enrich
AST-extracted metadata with framework-specific semantics without modifying
the core AST structure.
"""

import ast
import importlib
import importlib.metadata
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

@dataclass
class LocalContext:
    """Context passed to plugins during the local file-level AST traversal."""
    file_path: str
    current_module_name: str
    raw_ast: ast.AST

@dataclass
class GlobalContext:
    """Context passed to plugins after the full dependency graph is built."""
    # Assuming DependencyGraph and GlobalSymbolTable are typed as Any
    # since they are not explicitly defined in the provided scope, 
    # but the architectural requirements dictate their presence.
    dependency_graph: Any
    global_symbol_table: Any

class BasePlugin(ABC):
    """
    Abstract base class for all PRMG plugins.
    Plugins MUST NOT modify the AST; they only return a dictionary to be appended
    to ext_metadata: Dict[str, Any].
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

    @abstractmethod
    def visit_node(self, node: ast.AST, context: LocalContext) -> Optional[Dict[str, Any]]:
        """
        Triggered during file-level AST traversal for each node.
        Returns a dictionary of enriched metadata to be added to ext_metadata,
        or None if no enrichment applies to this node.
        """
        pass

    @abstractmethod
    def after_indexing(self, context: GlobalContext) -> None:
        """
        Triggered after the full dependency graph is built (GlobalPhase).
        """
        pass

class PluginManager:
    """
    Manages discovery, loading, and execution of PRMG plugins.
    Ensures that plugin exceptions are isolated from the main process
    and plugin outputs are correctly namespaced.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self.plugins: Dict[str, BasePlugin] = {}
        self._load_plugins_from_entry_points()

    def _load_plugins_from_entry_points(self) -> None:
        """Discovers and loads plugins registered via importlib.metadata entry points.
        Requires Python 3.10+ entry_points API."""
        entry_points = importlib.metadata.entry_points(group='prmg.plugins')

        for ep in entry_points:
            try:
                plugin_class = ep.load()
                plugin_config = self.config.get(ep.name, {})
                plugin_instance = plugin_class(plugin_config)
                self.plugins[ep.name] = plugin_instance
                logger.info(f"Loaded plugin '{ep.name}' via entry point.")
            except Exception as e:
                logger.error(f"Failed to load plugin '{ep.name}' via entry point: {e}", exc_info=True)

    def load_from_config_string(self, name: str, config_str: str, plugin_config: Optional[Dict[str, Any]] = None) -> None:
        """
        Loads a plugin from a configuration string (e.g., 'module.path:ClassName').
        
        Args:
            name: The namespace key for the plugin.
            config_str: String specifying the module and class to load.
            plugin_config: Configuration dictionary for the plugin instance.
        """
        try:
            module_path, class_name = config_str.split(':')
            module = importlib.import_module(module_path)
            plugin_class = getattr(module, class_name)
            plugin_instance = plugin_class(plugin_config or {})
            self.plugins[name] = plugin_instance
            logger.info(f"Loaded plugin '{name}' from config string '{config_str}'.")
        except Exception as e:
            logger.error(f"Failed to load plugin '{name}' from config string '{config_str}': {e}", exc_info=True)

    def run_visit_node(self, node: ast.AST, context: LocalContext) -> Dict[str, Any]:
        """
        Executes visit_node on all registered plugins for a given AST node.
        To ensure high performance, plugins are only evaluated for high-value nodes
        (e.g., FunctionDef, AsyncFunctionDef, ClassDef).
        
        Returns:
            A dictionary containing namespaced metadata from plugins that returned data.
        """
        # Restrict plugin evaluation to high-value nodes for performance
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return {}

        ext_metadata: Dict[str, Any] = {}
        for name, plugin in self.plugins.items():
            try:
                result = plugin.visit_node(node, context)
                if result is not None:
                    # Namespace isolation: plugin output is keyed by plugin name
                    ext_metadata[name] = result
            except Exception as e:
                # Exception isolation per plugin with full traceback logged
                logger.error(f"Plugin '{name}' failed during visit_node: {e}", exc_info=True)
        return ext_metadata

    def run_after_indexing(self, context: GlobalContext) -> None:
        """
        Executes after_indexing on all registered plugins.
        """
        for name, plugin in self.plugins.items():
            try:
                plugin.after_indexing(context)
            except Exception as e:
                # Exception isolation per plugin
                logger.error(f"Plugin '{name}' failed during after_indexing: {e}", exc_info=True)

class FastAPIPlugin(BasePlugin):
    """
    Reference Implementation: FastAPIPlugin.
    Identifies functions decorated with @app.get, @app.post, etc.
    Extracts the path and method from the decorator and adds it to ext_metadata.
    """

    def visit_node(self, node: ast.AST, context: LocalContext) -> Optional[Dict[str, Any]]:
        # Only interested in function definitions
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return None

        # Process decorators
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue

            func = decorator.func
            if not isinstance(func, ast.Attribute):
                continue

            # Check if the decorator is an attribute of a router/app (e.g., app.get)
            if not isinstance(func.value, ast.Name):
                continue

            method = func.attr.upper()
            if method not in {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD", "TRACE"}:
                continue

            # Extract the path argument
            path = None
            # Check positional arguments first
            if decorator.args and isinstance(decorator.args[0], ast.Constant):
                path = decorator.args[0].value
            else:
                # Check keyword arguments
                for kw in decorator.keywords:
                    if kw.arg == 'path' and isinstance(kw.value, ast.Constant):
                        path = kw.value.value
                        break

            if path is not None:
                return {"method": method, "path": path}

        return None

    def after_indexing(self, context: GlobalContext) -> None:
        # No global phase action needed for this simple reference implementation
        pass
