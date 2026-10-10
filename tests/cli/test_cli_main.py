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


def test_main_keyboard_interrupt():
    from netcheck.cli.exitcodes import EXIT_INTERRUPT
    with patch("netcheck.cli.main._main_impl", side_effect=KeyboardInterrupt):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == EXIT_INTERRUPT
        assert exc.value.code == 130
