"""
NetCheck CLI package.
Entry point: netcheck.cli.main:main
"""
from netcheck.cli.executor import run_check_with_retry
from netcheck.cli.main import main

__all__ = ["main", "run_check_with_retry"]

