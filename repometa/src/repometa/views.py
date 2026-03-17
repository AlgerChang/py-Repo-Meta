def format_file_focus(filepath: str, symbols: list[dict]) -> str:
    lines = [f"# File: {filepath}"]
    
    for symbol in symbols:
        sym_type = symbol['symbol_type']
        
        if sym_type == 'class':
            prefix = 'class'
        else:
            prefix = 'def'
            
        qualname = symbol['qualname']
        start = symbol['start_line']
        end = symbol['end_line']
        docstring = symbol['docstring']
        
        lines.append(f"## `{prefix} {qualname}` (Lines: {start} - {end})")
        if docstring:
            lines.append(f"{docstring}")
        else:
            lines.append("*No docstring provided.*")
        lines.append("")
        
    return '\n'.join(lines).strip() + '\n'