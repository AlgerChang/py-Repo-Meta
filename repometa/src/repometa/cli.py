import os
import sys
import multiprocessing
import typer
from pathlib import Path
from typing import Optional

from prmg.storage.storage import DatabaseManager
from prmg.parser.ast_parser import ASTParser
from prmg.core.scanner import RepoScanner
from prmg.core.extension import PluginManager, GlobalContext
from prmg.storage.query import QueryEngine
from prmg.formatter.pyi import PyiFormatter

from repometa.query_cli import query_app

app = typer.Typer(help="repometa: Python repository metadata extractor")
app.add_typer(query_app, name="query")

CONSUMER_INDEX_VERSION = "1"


def get_db_path(repo_path: Path) -> Path:
    db_dir = repo_path / ".repometa"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "repometa.db"


def write_export_output(output: str, output_path: Optional[Path]) -> None:
    output_with_newline = output + "\n"
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_with_newline, encoding="utf-8")
        return

    stdout_buffer = getattr(sys.stdout, "buffer", None)
    if stdout_buffer is not None:
        stdout_buffer.write(output_with_newline.encode("utf-8"))
    else:
        sys.stdout.write(output_with_newline)


@app.command()
def build(repo_path: Path = typer.Argument(..., help="Path to the repository to parse")):
    """
    Parse Python files in the repository using the new PRMG engine and store metadata in SQLite.
    """
    abs_repo_path = str(repo_path.resolve())
    db_path = str(get_db_path(repo_path))
    
    typer.echo(f"Initializing PRMG on project: {abs_repo_path}")
    
    storage = DatabaseManager(db_path)
    storage.create_tables()
    
    plugin_config = {
        "prmg.plugins.fastapi": "prmg.core.extension:FastAPIPlugin"
    }
    
    parser = ASTParser(project_root=abs_repo_path, plugin_config=plugin_config)
    symbol_visibility = parser.symbol_visibility()
    visibility_requires_rebuild = (
        storage.get_index_setting("symbol_visibility") != symbol_visibility
    )
    consumers_require_rebuild = (
        storage.get_index_setting("consumer_index_version") != CONSUMER_INDEX_VERSION
    )
    if visibility_requires_rebuild or consumers_require_rebuild:
        if visibility_requires_rebuild:
            typer.echo("Symbol visibility changed or is unknown; rebuilding the full index.")
        else:
            typer.echo("Consumer index changed or is unknown; rebuilding the full index.")
        storage.clear_index()
    
    scanner = RepoScanner(
        root_path=abs_repo_path,
        storage=storage,
        parser=parser,
        batch_size=100,
        max_workers=os.cpu_count() or 4
    )
    
    typer.echo("Starting incremental repository scan...")
    scanner.run()
    typer.echo("Scan completed successfully!")

    typer.echo("Running Global Phase for plugins...")
    pm = PluginManager(plugin_config)
    pm.load_from_config_string("fastapi", "prmg.core.extension:FastAPIPlugin")
    
    global_context = GlobalContext(dependency_graph=scanner.tracker, global_symbol_table=storage)
    pm.run_after_indexing(global_context)
    storage.set_index_setting("symbol_visibility", symbol_visibility)
    storage.set_index_setting("consumer_index_version", CONSUMER_INDEX_VERSION)
    typer.echo("Global Phase completed.")
    typer.echo(f"Successfully built metadata in {db_path}")

@app.command()
def export(
    view: str = typer.Argument(..., help="The view to export (e.g., 'all', 'file_focus')"),
    target: Optional[str] = typer.Option(None, "--target", help="The relative filepath to export for 'file_focus'"),
    repo_path: Path = typer.Option(Path("."), "--repo-path", help="Path to the repository"),
    output_path: Optional[Path] = typer.Option(None, "--output-path", help="Write export output to this file")
):
    """
    Export metadata using PRMG engine formatters.
    """
    db_path = str(get_db_path(repo_path))
    if not Path(db_path).exists():
        typer.echo("Database not found. Please run 'build' first.", err=True)
        raise typer.Exit(code=1)
        
    storage = DatabaseManager(db_path)
    query_engine = QueryEngine(storage)
    formatter = PyiFormatter()
    
    if view == "all":
        output = formatter.generate_repository_context(query_engine.iter_all_modules())
        write_export_output(output, output_path)
    elif view == "file_focus":
        if not target:
            typer.echo("Target file must be specified for 'file_focus' view.", err=True)
            raise typer.Exit(code=1)
            
        target_path = str(Path(target).resolve())
        mod_meta = query_engine.get_module_meta(target_path)
        if not mod_meta:
            typer.echo(f"No metadata found for target file: {target_path}", err=True)
            raise typer.Exit(code=1)
            
        output = formatter.format_module(mod_meta)
        write_export_output(output, output_path)
    else:
        typer.echo(f"Unsupported view: {view}", err=True)
        raise typer.Exit(code=1)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    app()
