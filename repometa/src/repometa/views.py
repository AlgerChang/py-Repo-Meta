def format_file_focus(filepath: str, symbols: list[dict]) -> str:
    lines = [f"# File: {filepath}"]
    
    for symbol in symbols:
        sym_type = symbol['symbol_type']
        
        if sym_type == 'class':
            prefix = 'class'
        elif sym_type == 'async_function':
            prefix = 'async def'
        else:
            prefix = 'def'
            
        qualname = symbol['qualname']
        docstring = symbol.get('docstring')
        line_start = symbol.get('line_start')
        line_end = symbol.get('line_end')
        
        span_str = ""
        if line_start is not None and line_end is not None:
            span_str = f" (L{line_start}-L{line_end})"
            
        lines.append(f"## `{prefix} {qualname}`{span_str}")
        if docstring:
            lines.append(f"{docstring}")
        else:
            lines.append("*No docstring provided.*")
        lines.append("")
        
    return '\n'.join(lines).strip() + '\n'