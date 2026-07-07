import json
import pytest
from typer.testing import CliRunner

from repometa.cli import app
from prmg.storage.storage import DatabaseManager

runner = CliRunner()

@pytest.fixture
def mock_db(tmp_path):
    db_path = tmp_path / "test_query.db"
    db = DatabaseManager(str(db_path))
    db.create_tables()
    with db.get_connection() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO files (id, filepath, file_hash, last_modified) VALUES (1, 'src/test_mod.py', 'hash1', 123.0)")
        # Module
        c.execute("INSERT INTO symbols (id, file_id, symbol_type, name, qualname, line_start, line_end) VALUES (10, 1, 'module', 'test_mod', 'test_mod', 1, 10)")
        # Class
        c.execute("INSERT INTO symbols (id, file_id, parent_id, symbol_type, name, qualname, line_start, line_end) VALUES (11, 1, 10, 'class', 'TestClass', 'test_mod.TestClass', 2, 5)")
        # Function
        c.execute("INSERT INTO symbols (id, file_id, parent_id, symbol_type, name, qualname, line_start, line_end) VALUES (12, 1, 10, 'function', 'test_func', 'test_mod.test_func', 7, 9)")
        # Method
        c.execute("INSERT INTO symbols (id, file_id, parent_id, symbol_type, name, qualname, line_start, line_end) VALUES (13, 1, 11, 'method', 'test_method', 'test_mod.TestClass.test_method', 3, 4)")
        
        # Edges
        c.execute("INSERT INTO edges (source_symbol_id, target_qualname, edge_type) VALUES (10, 'os', 'imports')")
        c.execute("INSERT INTO edges (source_symbol_id, target_qualname, edge_type) VALUES (11, 'BaseClass', 'inherits')")
        
        # Dependencies
        c.execute("CREATE TABLE dependencies (from_path TEXT NOT NULL, to_module TEXT NOT NULL, PRIMARY KEY (from_path, to_module))")
        c.execute("INSERT INTO dependencies (from_path, to_module) VALUES ('src/test_mod.py', 'sys')")
    return str(db_path)

def test_query_overview(mock_db):
    result = runner.invoke(app, ["query", "overview", "--db-path", mock_db])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["total_files"] == 1
    assert data["total_modules"] == 1
    assert data["total_classes"] == 1
    assert data["total_functions"] == 2  # 1 function + 1 method

def test_query_schema(mock_db):
    result = runner.invoke(app, ["query", "schema", "--db-path", mock_db])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "tables" in data
    table_names = [t["name"] for t in data["tables"]]
    assert "files" in table_names
    assert "symbols" in table_names

def test_query_module_by_name(mock_db):
    result = runner.invoke(app, ["query", "module", "--name", "test_mod", "--db-path", mock_db])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["module_name"] == "test_mod"
    assert data[0]["filepath"] == "src/test_mod.py"
    assert "os" in data[0]["imports"]
    assert data[0]["classes"][0]["name"] == "TestClass"
    assert data[0]["functions"][0]["name"] == "test_func"

def test_query_deps(mock_db):
    result = runner.invoke(app, ["query", "deps", "--name", "test_mod", "--db-path", mock_db])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert "sys" in data[0]["depends_on"]
    assert data[0]["filepath"] == "src/test_mod.py"

def test_query_imports(mock_db):
    result = runner.invoke(app, ["query", "imports", "--path", "src/test_mod.py", "--db-path", mock_db])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert "os" in data[0]["imports"]

def test_query_find(mock_db):
    result = runner.invoke(app, ["query", "find", "--name", "TestClass", "--db-path", mock_db])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 2
    names = [d["name"] for d in data]
    assert "TestClass" in names
    assert "test_method" in names
    assert data[0]["filepath"] == "src/test_mod.py"
    assert data[0]["line_start"] == 2

def test_query_class(mock_db):
    result = runner.invoke(app, ["query", "class", "--name", "TestClass", "--db-path", mock_db])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["name"] == "TestClass"
    assert "BaseClass" in data[0]["bases"]
    assert data[0]["methods"][0]["name"] == "test_method"
    
def test_query_function(mock_db):
    result = runner.invoke(app, ["query", "function", "--name", "test_func", "--db-path", mock_db])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["name"] == "test_func"
    assert data[0]["filepath"] == "src/test_mod.py"

def test_validation_mutually_exclusive(mock_db):
    result = runner.invoke(app, ["query", "module", "--name", "test", "--id", "1", "--db-path", mock_db])
    assert result.exit_code == 1
    assert "mutually exclusive" in result.output

def test_validation_max_targets(mock_db):
    args = ["query", "module", "--db-path", mock_db]
    for i in range(6):
        args.extend(["--name", f"mod{i}"])
    result = runner.invoke(app, args)
    assert result.exit_code == 1
    assert "more than 5 targets" in result.output

def test_validation_no_targets(mock_db):
    result = runner.invoke(app, ["query", "module", "--db-path", mock_db])
    assert result.exit_code == 1
    assert "Must provide at least one target" in result.output
