"""
Exit code constants for NetCheck CLI.

These codes are contracts — CI pipelines and scripts depend on them.
Never change values; only add new codes if needed.
"""

EXIT_OK = 0        # All checks passed successfully
EXIT_FAIL = 1      # One or more network checks failed
EXIT_BAD_ARGS = 2  # Invalid arguments or usage error
EXIT_ERROR = 3     # Unexpected runtime error
