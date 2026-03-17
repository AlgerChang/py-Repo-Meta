import typer
from pathlib import Path
from typing import Optional

from repometa.db import RepoMetaDB
from repometa.parser import parse_file
from repometa.views import format_file_focus

app = typer.Typer(help="repometa: Python repository metadata extractor")

@app.command()
def build(repo_path: Path = typer.Argument(..., help="Path to the repository to parse")):
    """
    Parse Python files in the repository, store metadata in SQLite, and prepare for export.
    """
    db = RepoMetaDB(repo_path)
    db.setup()
    db.clear_all()
    
    # Resolve to absolute path to ensure relative_to works safely
    abs_repo_path = repo_path.resolve()
    
    processed_count = 0
    for filepath in repo_path.rglob("*.py"):
        # Ignore .venv and .repometa directories
        if ".venv" in filepath.parts or ".repometa" in filepath.parts:
            continue
            
        symbols = parse_file(filepath)
        if symbols:
            # Store filepath strictly relative to repo_path with forward slashes
            try:
                rel_path = filepath.resolve().relative_to(abs_repo_path).as_posix()
            except ValueError:
                # Fallback if somehow not relative
                rel_path = filepath.as_posix()
                
            file_id = db.insert_file(rel_path)
            db.insert_symbols(file_id, symbols)
            processed_count += 1
            
    typer.echo(f"Successfully built metadata for {processed_count} files in {repo_path}")

@app.command()
def export(
    view: str = typer.Argument(..., help="The view to export (e.g., 'file_focus')"),
    target: str = typer.Option(..., "--target", help="The relative filepath to export"),
    repo_path: Path = typer.Option(Path("."), "--repo-path", help="Path to the repository")
):
    """
    Export metadata for a specific view and target as Markdown.
    """
    db = RepoMetaDB(repo_path)
    target_posix = Path(target).as_posix()
    
    if view == "file_focus":
        symbols = db.get_symbols_by_file(target_posix)
        if not symbols:
            typer.echo(f"No metadata found for target file: {target_posix}", err=True)
            raise typer.Exit(code=1)
            
        markdown_output = format_file_focus(target_posix, symbols)
        typer.echo(markdown_output)
    else:
        typer.echo(f"Unsupported view: {view}", err=True)
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
