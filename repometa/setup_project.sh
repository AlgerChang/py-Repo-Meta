#!/bin/bash
# PRMG Project Initialization Script

# Define target directories
DIRS=(
    "src/prmg/core"
    "src/prmg/storage"
    "src/prmg/formatter"
)

echo "Initializing Python Repository Metadata Generator (PRMG) project..."

for dir in "${DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        echo "Creating directory: $dir"
        mkdir -p "$dir"
        
        # Create __init__.py if it doesn't exist
        if [ ! -f "$dir/__init__.py" ]; then
            touch "$dir/__init__.py"
        fi
    else
        echo "Directory already exists: $dir"
    fi
done

echo "Project structure initialized successfully."
