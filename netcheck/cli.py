"""
netcheck/cli.py — backward-compatibility shim.

All logic has been moved to netcheck/cli/ (the package).
This module re-exports everything that external code (including
netcheck/mcp/tools.py) imported from here directly.

DO NOT add new logic here. Edit netcheck/cli/main.py instead.
"""
# Re-export for any code that still does: from netcheck.cli import main
# Batch helpers imported by tests
from netcheck.cli.batch import (  # noqa: F401
    parse_batch_content,
    parse_batch_file,
    parse_csv_content,
    parse_csv_file,
    run_batch_lines,
    run_batch_targets,
)

# run_check_with_retry is imported by netcheck/mcp/tools.py
from netcheck.cli.executor import run_check_with_retry  # noqa: F401
from netcheck.cli.main import main, print_help, run_quick_test  # noqa: F401
