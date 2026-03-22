import os
import sys
from pathlib import Path

# Add src directory to sys.path so modules can be found without installation
sys.path.insert(0, str(Path(__file__).parent.resolve() / "src"))

from prmg.storage.storage import DatabaseManager
from prmg.parser.ast_parser import ASTParser
from prmg.core.scanner import RepoScanner
from prmg.core.extension import PluginManager, GlobalContext
from prmg.storage.query import QueryEngine
from prmg.formatter.pyi import PyiFormatter

def main():
    # Resolve the repository root directory (assuming main.py is in the root)
    root_path = str(Path(__file__).parent.resolve())
    db_path = os.path.join(root_path, "repometa.db")
    
    print(f"Initializing PRMG on project: {root_path}")
    
    # 1. Initialize storage and Database
    storage = DatabaseManager(db_path)
    storage.create_tables()
    print("Database tables initialized.")
    
    # Enable specific plugins using configuration
    plugin_config = {
        "prmg.plugins.fastapi": "prmg.core.extension:FastAPIPlugin"
    }
    
    # 2. Initialize AST Parser with plugin config
    parser = ASTParser(project_root=root_path, plugin_config=plugin_config)
    
    # 3. Initialize the RepoScanner Orchestrator
    scanner = RepoScanner(
        root_path=root_path,
        storage=storage,
        parser=parser,
        batch_size=100,  # Adjustable for testing
        max_workers=os.cpu_count() or 4
    )
    
    print("Starting incremental repository scan...")
    scanner.run()
    print("Scan completed successfully!")

    # 4. Global Phase for Plugins
    print("Running Global Phase for plugins...")
    pm = PluginManager(plugin_config)
    # Instantiate from config string manually for the FastAPI reference plugin
    pm.load_from_config_string("fastapi", "prmg.core.extension:FastAPIPlugin")
    
    global_context = GlobalContext(dependency_graph=scanner.tracker, global_symbol_table=storage)
    pm.run_after_indexing(global_context)
    print("Global Phase completed.")

    # 5. Output Layer
    print("Generating Pyi output...")
    query_engine = QueryEngine(storage)
    formatter = PyiFormatter()
    
    output = formatter.generate_repository_context(query_engine.iter_all_modules())
    
    out_path = os.path.join(root_path, "output.pyi")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(output)
    print(f"Output generated successfully at {out_path}!")

if __name__ == "__main__":
    main()
