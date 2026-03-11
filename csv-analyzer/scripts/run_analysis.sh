#!/bin/bash
# CSV Analyzer - Shell wrapper
# Ensures dependencies are installed before running analysis.
#
# Usage:
#   bash run_analysis.sh /path/to/data.csv
#   bash run_analysis.sh --check-deps   # just install deps

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
PYTHON="$VENV_DIR/bin/python3"

# Check-deps-only mode
if [ "$1" = "--check-deps" ]; then
    python3 "$SCRIPT_DIR/check_deps.py"
    exit $?
fi

# If no venv, try system Python first
if [ ! -d "$VENV_DIR" ]; then
    python3 -c "import pandas, matplotlib, seaborn" 2>/dev/null
    if [ $? -eq 0 ]; then
        PYTHON="python3"
    else
        echo "Setting up virtual environment..."
        python3 -m venv "$VENV_DIR"
        "$VENV_DIR/bin/pip" install -q -r "$SCRIPT_DIR/../requirements.txt"
        echo "Environment ready"
    fi
else
    # venv exists, use it
    PYTHON="$VENV_DIR/bin/python3"
fi

# Run the analysis with all arguments passed through
"$PYTHON" "$SCRIPT_DIR/analyze.py" "$@"
