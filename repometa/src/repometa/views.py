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
        
        lines.append(f"## `{prefix} {qualname}`")
        if docstring:
            lines.append(f"{docstring}")
        else:
            lines.append("*No docstring provided.*")
        lines.append("")
        
    return '\n'.join(lines).strip() + '\n'