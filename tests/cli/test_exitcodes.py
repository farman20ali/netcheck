"""
Unit tests for netcheck.cli.exitcodes
"""
from netcheck.cli.exitcodes import EXIT_OK, EXIT_FAIL, EXIT_BAD_ARGS, EXIT_ERROR


def test_exit_codes_defined():
    assert EXIT_OK == 0
    assert EXIT_FAIL == 1
    assert EXIT_BAD_ARGS == 2
    assert EXIT_ERROR == 3
