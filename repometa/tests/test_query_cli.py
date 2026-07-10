import json
from pathlib import Path

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
    package_mod_path = tmp_path / "src" / "pkg" / "mod.py"
    consumer_path = tmp_path / "src" / "consumer.py"
    src_prefix_consumer_path = tmp_path / "src" / "src_prefix_consumer.py"
    with db.get_connection() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO files (id, filepath, file_hash, last_modified) VALUES (1, 'src/test_mod.py', 'hash1', 123.0)")
        c.execute("INSERT INTO files (id, filepath, file_hash, last_modified) VALUES (2, ?, 'hash2', 123.0)", (str(package_mod_path),))
        # Module
        c.execute("INSERT INTO symbols (id, file_id, symbol_type, name, qualname, line_start, line_end) VALUES (10, 1, 'module', 'test_mod', 'test_mod', 1, 10)")
        c.execute("INSERT INTO symbols (id, file_id, symbol_type, name, qualname, line_start, line_end) VALUES (20, 2, 'module', 'mod', 'pkg.mod', 1, 10)")
        # Class
        c.execute("INSERT INTO symbols (id, file_id, parent_id, symbol_type, name, qualname, line_start, line_end) VALUES (11, 1, 10, 'class', 'TestClass', 'test_mod.TestClass', 2, 5)")
        c.execute("INSERT INTO symbols (id, file_id, parent_id, symbol_type, name, qualname, line_start, line_end) VALUES (21, 2, 20, 'class', 'Widget', 'pkg.mod.Widget', 2, 5)")
        # Function
        c.execute("INSERT INTO symbols (id, file_id, parent_id, symbol_type, name, qualname, line_start, line_end) VALUES (12, 1, 10, 'function', 'test_func', 'test_mod.test_func', 7, 9)")
        # Method
        c.execute("INSERT INTO symbols (id, file_id, parent_id, symbol_type, name, qualname, line_start, line_end) VALUES (13, 1, 11, 'method', 'test_method', 'test_mod.TestClass.test_method', 3, 4)")
        
        # Edges
        c.execute("INSERT INTO edges (source_symbol_id, target_qualname, edge_type) VALUES (10, 'os', 'imports')")
        c.execute("INSERT INTO edges (source_symbol_id, target_qualname, edge_type) VALUES (11, 'BaseClass', 'inherits')")
        c.execute("INSERT INTO edges (source_symbol_id, target_qualname, edge_type) VALUES (20, 'json', 'imports')")
        
        # Dependencies
        c.execute("INSERT INTO dependencies (from_path, to_module) VALUES ('src/test_mod.py', 'sys')")
        c.execute("INSERT INTO dependencies (from_path, to_module) VALUES (?, 'pkg.mod.Widget')", (str(consumer_path),))
        c.execute("INSERT INTO dependencies (from_path, to_module) VALUES (?, 'src.pkg.mod.Widget')", (str(src_prefix_consumer_path),))
    return str(db_path)


@pytest.fixture
def export_repo(tmp_path):
    repo_path = tmp_path / "repo"
    db_dir = repo_path / ".repometa"
    db_dir.mkdir(parents=True)
    db = DatabaseManager(str(db_dir / "repometa.db"))
    db.create_tables()

    with db.get_connection() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO files (id, filepath, file_hash, last_modified) VALUES (1, 'src/example.py', 'hash1', 123.0)")
        c.execute("INSERT INTO symbols (id, file_id, symbol_type, name, qualname, line_start, line_end) VALUES (10, 1, 'module', 'example', 'example', 1, 10)")
        c.execute("INSERT INTO symbols (id, file_id, parent_id, symbol_type, name, qualname, metadata, line_start, line_end) VALUES (11, 1, 10, 'function', 'run', 'example.run', '{}', 3, 4)")
        c.execute("INSERT INTO edges (source_symbol_id, target_qualname, edge_type) VALUES (10, 'os', 'imports')")

    return repo_path


def test_query_overview(mock_db):
    result = runner.invoke(app, ["query", "overview", "--db-path", mock_db])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["total_files"] == 2
    assert data["total_modules"] == 2
    assert data["total_classes"] == 2
    assert data["total_functions"] == 2  # 1 function + 1 method

def test_query_schema(mock_db):
    result = runner.invoke(app, ["query", "schema", "--db-path", mock_db])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "tables" in data
    table_names = [t["name"] for t in data["tables"]]
    assert "files" in table_names
    assert "symbols" in table_names
    assert "dependencies" in table_names

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

def test_query_module_by_symbol_id(mock_db):
    result = runner.invoke(app, ["query", "module", "--id", "10", "--db-path", mock_db])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["module_name"] == "test_mod"
    assert data[0]["file_id"] == 1

def test_query_module_by_qualname(mock_db):
    result = runner.invoke(app, ["query", "module", "--name", "pkg.mod", "--db-path", mock_db])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["filepath"].endswith("src\\pkg\\mod.py") or data[0]["filepath"].endswith("src/pkg/mod.py")

def test_query_deps(mock_db):
    result = runner.invoke(app, ["query", "deps", "--name", "test_mod", "--db-path", mock_db])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert "sys" in data[0]["depends_on"]
    assert data[0]["filepath"] == "src/test_mod.py"

def test_query_deps_reverse_matches_sub_symbol_imports(mock_db):
    result = runner.invoke(app, ["query", "deps", "--name", "pkg.mod", "--db-path", mock_db])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert any(path.endswith("src\\consumer.py") or path.endswith("src/consumer.py") for path in data[0]["depended_by"])
    assert any(path.endswith("src\\src_prefix_consumer.py") or path.endswith("src/src_prefix_consumer.py") for path in data[0]["depended_by"])

def test_query_imports(mock_db):
    result = runner.invoke(app, ["query", "imports", "--path", "src/test_mod.py", "--db-path", mock_db])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert "os" in data[0]["imports"]

def test_query_imports_by_relative_path_for_absolute_db_path(mock_db):
    result = runner.invoke(app, ["query", "imports", "--path", "src/pkg/mod.py", "--db-path", mock_db])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert "json" in data[0]["imports"]

def test_query_imports_relative_path_treats_wildcards_literally(mock_db):
    db = DatabaseManager(mock_db)
    db_dir = Path(mock_db).parent
    exact_path = db_dir / "src" / "my_file.py"
    wildcard_match_path = db_dir / "src" / "myXfile.py"
    with db.get_connection() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO files (id, filepath, file_hash, last_modified) VALUES (30, ?, 'hash30', 123.0)", (str(exact_path),))
        c.execute("INSERT INTO files (id, filepath, file_hash, last_modified) VALUES (31, ?, 'hash31', 123.0)", (str(wildcard_match_path),))
        c.execute("INSERT INTO symbols (id, file_id, symbol_type, name, qualname, line_start, line_end) VALUES (300, 30, 'module', 'my_file', 'my_file', 1, 1)")
        c.execute("INSERT INTO symbols (id, file_id, symbol_type, name, qualname, line_start, line_end) VALUES (310, 31, 'module', 'myXfile', 'myXfile', 1, 1)")
        c.execute("INSERT INTO edges (source_symbol_id, target_qualname, edge_type) VALUES (300, 'os', 'imports')")
        c.execute("INSERT INTO edges (source_symbol_id, target_qualname, edge_type) VALUES (310, 'sys', 'imports')")

    result = runner.invoke(app, ["query", "imports", "--path", "src/my_file.py", "--db-path", mock_db])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["module_name"] == "my_file"
    assert data[0]["imports"] == ["os"]

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

def test_query_find_deduplicates_symbols(mock_db):
    result = runner.invoke(app, ["query", "find", "--name", "TestClass", "--name", "test_mod.TestClass", "--db-path", mock_db])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    ids = [item["id"] for item in data]
    assert len(ids) == len(set(ids))

def test_query_find_prioritizes_exact_qualname_before_limit(mock_db):
    db = DatabaseManager(mock_db)
    with db.get_connection() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO files (id, filepath, file_hash, last_modified) VALUES (40, 'src/noisy.py', 'hash40', 123.0)")
        c.execute("INSERT INTO symbols (id, file_id, symbol_type, name, qualname, line_start, line_end) VALUES (400, 40, 'module', 'noisy', 'pkg.noisy', 1, 1)")
        for i in range(55):
            c.execute(
                "INSERT INTO symbols (id, file_id, parent_id, symbol_type, name, qualname, line_start, line_end) VALUES (?, 40, 400, 'function', ?, ?, 2, 2)",
                (500 + i, f"partial_{i}", f"pkg.noisy.common.target_partial_{i:02d}"),
            )
        c.execute(
            "INSERT INTO symbols (id, file_id, parent_id, symbol_type, name, qualname, line_start, line_end) VALUES (900, 40, 400, 'function', 'target', 'pkg.noisy.common.target', 3, 3)"
        )

    result = runner.invoke(app, ["query", "find", "--name", "pkg.noisy.common.target", "--db-path", mock_db])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data[0]["qualname"] == "pkg.noisy.common.target"
    assert any(item["id"] == 900 for item in data)

def test_query_class(mock_db):
    result = runner.invoke(app, ["query", "class", "--name", "TestClass", "--db-path", mock_db])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["name"] == "TestClass"
    assert "BaseClass" in data[0]["bases"]
    assert data[0]["methods"][0]["name"] == "test_method"

def test_query_class_by_qualname(mock_db):
    result = runner.invoke(app, ["query", "class", "--name", "pkg.mod.Widget", "--db-path", mock_db])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["name"] == "Widget"
    
def test_query_function(mock_db):
    result = runner.invoke(app, ["query", "function", "--name", "test_func", "--db-path", mock_db])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["name"] == "test_func"
    assert data[0]["filepath"] == "src/test_mod.py"

def test_query_function_by_qualname(mock_db):
    result = runner.invoke(app, ["query", "function", "--name", "test_mod.test_func", "--db-path", mock_db])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["name"] == "test_func"


def test_build_indexes_private_module_function_for_navigation_queries(tmp_path):
    repo_path = tmp_path / "private_symbols_repo"
    module_path = repo_path / "src" / "pkg" / "module.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text(
        '''def public_function():
    pass


def _private_function():
    def nested_public_function():
        pass

    def _nested_private_function():
        pass


class PublicClass:
    def _private_method(self):
        pass

    def __name_mangled_method(self):
        pass
''',
        encoding="utf-8",
    )

    build_result = runner.invoke(app, ["build", str(repo_path)])
    assert build_result.exit_code == 0, build_result.output

    db_path = repo_path / ".repometa" / "repometa.db"
    db = DatabaseManager(str(db_path))
    with db.get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, name, qualname, symbol_type, line_start, line_end
            FROM symbols
            WHERE qualname = 'pkg.module._private_function'
            """
        ).fetchone()
    assert row is not None
    private_id = row[0]
    assert row[1:] == ("_private_function", "pkg.module._private_function", "function", 5, 10)

    find_result = runner.invoke(
        app,
        ["query", "find", "--name", "_private_function", "--db-path", str(db_path)],
    )
    assert find_result.exit_code == 0, find_result.output
    find_data = json.loads(find_result.stdout)
    assert find_data[0] == {
        "id": private_id,
        "name": "_private_function",
        "qualname": "pkg.module._private_function",
        "symbol_type": "function",
        "filepath": str(module_path.resolve()),
        "line_start": 5,
        "line_end": 10,
    }

    function_by_short_name_result = runner.invoke(
        app,
        ["query", "function", "--name", "_private_function", "--db-path", str(db_path)],
    )
    assert function_by_short_name_result.exit_code == 0, function_by_short_name_result.output
    assert json.loads(function_by_short_name_result.stdout)[0]["id"] == private_id

    function_result = runner.invoke(
        app,
        ["query", "function", "--name", "pkg.module._private_function", "--db-path", str(db_path)],
    )
    assert function_result.exit_code == 0, function_result.output
    function_data = json.loads(function_result.stdout)
    assert len(function_data) == 1
    assert function_data[0]["id"] == private_id
    assert function_data[0]["qualname"] == "pkg.module._private_function"

    function_by_id_result = runner.invoke(
        app,
        ["query", "function", "--id", str(private_id), "--db-path", str(db_path)],
    )
    assert function_by_id_result.exit_code == 0, function_by_id_result.output
    assert json.loads(function_by_id_result.stdout)[0]["qualname"] == "pkg.module._private_function"

    module_result = runner.invoke(
        app,
        ["query", "module", "--path", str(module_path), "--db-path", str(db_path)],
    )
    assert module_result.exit_code == 0, module_result.output
    module_data = json.loads(module_result.stdout)
    assert [function["qualname"] for function in module_data[0]["functions"]] == [
        "pkg.module.public_function",
        "pkg.module._private_function",
        "pkg.module._private_function.nested_public_function",
        "pkg.module._private_function._nested_private_function",
        "pkg.module.PublicClass._private_method",
        "pkg.module.PublicClass.__name_mangled_method",
    ]


def test_build_reindexes_legacy_database_when_symbol_visibility_is_unknown(tmp_path):
    repo_path = tmp_path / "legacy_visibility_repo"
    module_path = repo_path / "module.py"
    repo_path.mkdir()
    module_path.write_text("def _private_function():\n    pass\n", encoding="utf-8")
    config_path = repo_path / "pyproject.toml"
    config_path.write_text("[tool.prmg]\ninclude_private = false\n", encoding="utf-8")

    public_only_build = runner.invoke(app, ["build", str(repo_path)])
    assert public_only_build.exit_code == 0, public_only_build.output

    db_path = repo_path / ".repometa" / "repometa.db"
    db = DatabaseManager(str(db_path))
    with db.get_connection() as conn:
        private_count = conn.execute(
            "SELECT COUNT(*) FROM symbols WHERE qualname = 'module._private_function'"
        ).fetchone()[0]
        conn.execute("DELETE FROM index_metadata")
    assert private_count == 0

    config_path.unlink()
    upgraded_build = runner.invoke(app, ["build", str(repo_path)])
    assert upgraded_build.exit_code == 0, upgraded_build.output
    assert "Symbol visibility changed or is unknown; rebuilding the full index." in upgraded_build.output

    with db.get_connection() as conn:
        private_count = conn.execute(
            "SELECT COUNT(*) FROM symbols WHERE qualname = 'module._private_function'"
        ).fetchone()[0]
        visibility = conn.execute(
            "SELECT value FROM index_metadata WHERE key = 'symbol_visibility'"
        ).fetchone()[0]
    assert private_count == 1
    assert visibility == "all"


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

def test_validation_invalid_id(mock_db):
    result = runner.invoke(app, ["query", "module", "--id", "abc", "--db-path", mock_db])
    assert result.exit_code == 1
    assert "IDs must be numeric" in result.output


def test_export_all_writes_stdout_by_default(export_repo):
    result = runner.invoke(app, ["export", "all", "--repo-path", str(export_repo)])

    assert result.exit_code == 0
    assert "# File: src/example.py" in result.stdout
    assert "def run():" in result.stdout


def test_export_all_writes_output_path(export_repo, tmp_path):
    output_path = tmp_path / "nested" / "repo_meta.pyi"

    result = runner.invoke(
        app,
        ["export", "all", "--repo-path", str(export_repo), "--output-path", str(output_path)],
    )

    assert result.exit_code == 0
    assert result.stdout == ""
    assert output_path.read_text(encoding="utf-8").endswith("\n")
    assert "def run():" in output_path.read_text(encoding="utf-8")
