import json
import sys
from pathlib import Path
from typing import Any, List, Optional
import typer

from prmg.storage.storage import DatabaseManager
from prmg.storage.json_query import JsonQueryEngine

query_app = typer.Typer(help="Query the repository metadata database (Output as JSON)")

def get_db_path(db_path: Optional[str]) -> Path:
    if db_path:
        return Path(db_path)
    return Path(".repometa/repometa.db")

def _validate_targets(names: Optional[List[str]], paths: Optional[List[str]], ids: Optional[List[str]]):
    provided = sum(1 for x in (names, paths, ids) if x)
    if provided == 0:
        typer.echo(json.dumps({"error": "Must provide at least one target using --name, --path, or --id"}), err=True)
        raise typer.Exit(code=1)
    if provided > 1:
        typer.echo(json.dumps({"error": "Arguments --name, --path, and --id are mutually exclusive. Use only one type."}), err=True)
        raise typer.Exit(code=1)
        
    for targets in (names, paths, ids):
        if targets and len(targets) > 5:
            typer.echo(json.dumps({"error": "Cannot provide more than 5 targets per query."}), err=True)
            raise typer.Exit(code=1)

    if ids:
        for value in ids:
            if not value.isdigit():
                typer.echo(json.dumps({"error": f"Invalid ID: '{value}'. IDs must be numeric."}), err=True)
                raise typer.Exit(code=1)

def _get_engine(db_path: Optional[str]) -> JsonQueryEngine:
    path = get_db_path(db_path)
    if not path.exists():
        typer.echo(json.dumps({"error": f"Database not found at {path}"}), err=True)
        raise typer.Exit(code=1)
    return JsonQueryEngine(DatabaseManager(str(path)))

def _output(data: Any):
    payload = json.dumps(data, indent=None, ensure_ascii=False).encode("utf-8") + b"\n"
    sys.stdout.buffer.write(payload)

@query_app.command("overview")
def query_overview(db_path: Optional[str] = typer.Option(None, "--db-path", help="Path to database file")):
    engine = _get_engine(db_path)
    _output(engine.get_overview())

@query_app.command("schema")
def query_schema(db_path: Optional[str] = typer.Option(None, "--db-path", help="Path to database file")):
    engine = _get_engine(db_path)
    _output(engine.get_schema())

@query_app.command("module")
def query_module(
    name: Optional[List[str]] = typer.Option(None, "--name", help="Module names"),
    path: Optional[List[str]] = typer.Option(None, "--path", help="Module file paths"),
    id: Optional[List[str]] = typer.Option(None, "--id", help="Module IDs"),
    db_path: Optional[str] = typer.Option(None, "--db-path")
):
    _validate_targets(name, path, id)
    engine = _get_engine(db_path)
    _output(engine.query_module(name or [], path or [], id or []))

@query_app.command("deps")
def query_deps(
    name: Optional[List[str]] = typer.Option(None, "--name"),
    path: Optional[List[str]] = typer.Option(None, "--path"),
    id: Optional[List[str]] = typer.Option(None, "--id"),
    db_path: Optional[str] = typer.Option(None, "--db-path")
):
    _validate_targets(name, path, id)
    engine = _get_engine(db_path)
    _output(engine.query_deps(name or [], path or [], id or []))

@query_app.command("imports")
def query_imports(
    name: Optional[List[str]] = typer.Option(None, "--name"),
    path: Optional[List[str]] = typer.Option(None, "--path"),
    id: Optional[List[str]] = typer.Option(None, "--id"),
    db_path: Optional[str] = typer.Option(None, "--db-path")
):
    _validate_targets(name, path, id)
    engine = _get_engine(db_path)
    _output(engine.query_imports(name or [], path or [], id or []))

@query_app.command("find")
def query_find(
    name: List[str] = typer.Option(..., "--name", help="Fuzzy search names"),
    db_path: Optional[str] = typer.Option(None, "--db-path")
):
    if len(name) > 5:
        typer.echo(json.dumps({"error": "Cannot provide more than 5 targets per query."}), err=True)
        raise typer.Exit(code=1)
    engine = _get_engine(db_path)
    _output(engine.query_find(name))

@query_app.command("class")
def query_class(
    name: Optional[List[str]] = typer.Option(None, "--name"),
    id: Optional[List[str]] = typer.Option(None, "--id"),
    db_path: Optional[str] = typer.Option(None, "--db-path")
):
    _validate_targets(name, [], id)
    engine = _get_engine(db_path)
    _output(engine.query_class(name or [], id or []))

@query_app.command("function")
def query_function(
    name: Optional[List[str]] = typer.Option(None, "--name"),
    id: Optional[List[str]] = typer.Option(None, "--id"),
    db_path: Optional[str] = typer.Option(None, "--db-path")
):
    _validate_targets(name, [], id)
    engine = _get_engine(db_path)
    _output(engine.query_function(name or [], id or []))
