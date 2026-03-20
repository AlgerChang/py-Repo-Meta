import os
from pathlib import Path

# Adjust python path if needed or run with python -m 
from prmg.storage.storage import DatabaseManager
from prmg.parser.ast_parser import ASTParser
from prmg.core.scanner import RepoScanner

def main():
    # Resolve the repository root directory (assuming main.py is in the root)
    root_path = str(Path(__file__).parent.resolve())
    db_path = os.path.join(root_path, "repometa.db")
    
    print(f"Initializing PRMG on project: {root_path}")
    
    # 1. Initialize storage and Database
    storage = DatabaseManager(db_path)
    storage.create_tables()
    print("Database tables initialized.")
    
    # 2. Initialize AST Parser
    parser = ASTParser(project_root=root_path)
    
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

if __name__ == "__main__":
    main()
