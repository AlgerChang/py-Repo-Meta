import textwrap
from typing import Iterator

from prmg.formatter.base import BaseFormatter
from prmg.models.ir import ClassMeta, FunctionMeta, ModuleMeta

class PyiFormatter(BaseFormatter):
    def format_function(self, func: FunctionMeta, indent_level: int = 0) -> str:
        indent = " " * (4 * indent_level)
        lines = []
        
        if func.plugins:
            for plugin_name, plugin_data in func.plugins.items():
                if plugin_name == 'fastapi' and 'method' in plugin_data and 'path' in plugin_data:
                    lines.append(f"{indent}@{plugin_name}({plugin_data['method']} '{plugin_data['path']}')")
                else:
                    lines.append(f"{indent}# @plugin:{plugin_name} {plugin_data}")
                    
        prefix = "async def " if func.is_async else "def "
        lines.append(f"{indent}{prefix}{func.name}{func.signature}:")
        
        doc_indent = " " * (4 * (indent_level + 1))
        if self.include_docstrings and func.docstring:
            if "\n" in func.docstring:
                doc = f'"""\n{func.docstring}\n"""'
            else:
                doc = f'"""{func.docstring}"""'
            lines.append(textwrap.indent(doc, doc_indent))
            
        lines.append(f"{doc_indent}...")
        
        return "\n".join(lines)

    def format_class(self, cls: ClassMeta, indent_level: int = 0) -> str:
        indent = " " * (4 * indent_level)
        
        if cls.bases:
            bases_joined = ", ".join(cls.bases)
            class_def = f"{indent}class {cls.name}({bases_joined}):"
        else:
            class_def = f"{indent}class {cls.name}:"
            
        lines = [class_def]
        
        has_body = False
        doc_indent = " " * (4 * (indent_level + 1))
        
        if self.include_docstrings and cls.docstring:
            if "\n" in cls.docstring:
                doc = f'"""\n{cls.docstring}\n"""'
            else:
                doc = f'"""{cls.docstring}"""'
            lines.append(textwrap.indent(doc, doc_indent))
            has_body = True
            
        for nested in cls.nested_classes:
            lines.append(self.format_class(nested, indent_level + 1))
            has_body = True
            
        for method in cls.methods:
            lines.append(self.format_function(method, indent_level + 1))
            has_body = True
            
        if not has_body:
            lines.append(f"{doc_indent}...")
            
        return "\n".join(lines)

    def format_module(self, module: ModuleMeta) -> str:
        sections = []
        
        # Header (Filepath and module docstring)
        header_lines = [f"# File: {module.filepath}"]
        if self.include_docstrings and module.docstring:
            if "\n" in module.docstring:
                header_lines.append(f'"""\n{module.docstring}\n"""')
            else:
                header_lines.append(f'"""{module.docstring}"""')
        sections.append("\n".join(header_lines))
        
        # Imports
        if module.imports:
            sections.append("\n".join(module.imports))
            
        # Classes
        if module.classes:
            sections.append("\n\n".join(self.format_class(cls) for cls in module.classes))
            
        # Functions
        if module.functions:
            sections.append("\n\n".join(self.format_function(func) for func in module.functions))
            
        return "\n\n".join(sections)

    def generate_repository_context(self, modules: Iterator[ModuleMeta]) -> str:
        separator = "\n\n# " + ("=" * 40) + "\n\n"
        return separator.join(self.format_module(mod) for mod in modules)
