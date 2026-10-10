"""
Unit/Integration tests for netcheck.cli.main
"""
import sys
from unittest.mock import patch
import pytest

import netcheck.cli.main
from netcheck.cli import main


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
    mod = sys.modules["netcheck.cli.main"]
    with patch.object(mod, "_main_impl", side_effect=KeyboardInterrupt):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == EXIT_INTERRUPT
        assert exc.value.code == 130
