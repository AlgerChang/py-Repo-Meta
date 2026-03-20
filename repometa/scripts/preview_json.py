import json
import os
import sys

# Add the project root to sys.path so we can import repometa modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from src.parser.engine import SourceParser

def main():
    fixture_path = os.path.join(project_root, "tests", "fixtures", "complex_module.py")
    parser = SourceParser(fixture_path)
    module = parser.parse()
    
    print(module.model_dump_json(indent=2))

if __name__ == "__main__":
    main()
