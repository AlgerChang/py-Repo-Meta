import json
from dataclasses import asdict
from src.prmg.core.parser import parse_python_file

def main():
    target_file = "src/prmg/core/parser.py"
    print(f"Parsing target file: {target_file}")
    
    # Parse the target file
    metadata = parse_python_file(target_file)
    
    # Convert dataclass to dictionary and print as pretty JSON
    json_output = json.dumps(asdict(metadata), indent=4, ensure_ascii=False)
    print("\n--- Metadata JSON ---")
    print(json_output)

if __name__ == "__main__":
    main()
