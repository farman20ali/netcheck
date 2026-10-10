"""
Unit/Integration tests for netcheck.cli.main
"""
import sys
import pytest
from unittest.mock import patch
from netcheck.cli.main import main


@patch("sys.argv", ["netcheck", "--version"])
def test_main_version():
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0


@patch("sys.argv", ["netcheck", "-h"])
def test_main_help():
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
