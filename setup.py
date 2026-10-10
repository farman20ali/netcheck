"""
setup.py — post-install PATH fix for Linux/macOS pip installs.

When `pip install --user netcheckx` is run on Linux/macOS, scripts land
in ~/.local/bin which is often not on PATH.  This hook detects that and
automatically adds the export to the user's shell rc files.

This file is intentionally minimal; all package metadata lives in pyproject.toml.
"""

import os
import sys

from setuptools import setup
from setuptools.command.install import install
from setuptools.command.develop import develop


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EXPORT_LINE = 'export PATH="$HOME/.local/bin:$PATH"'
_MARKER = "# added by netcheckx installer"
_RC_FILES = ["~/.bashrc", "~/.zshrc", "~/.profile"]


def _local_bin() -> str:
    return os.path.expanduser("~/.local/bin")


def _already_on_path() -> bool:
    return _local_bin() in os.environ.get("PATH", "").split(":")


def _already_written(rc_path: str) -> bool:
    if not os.path.exists(rc_path):
        return False
    with open(rc_path, "r", encoding="utf-8", errors="ignore") as f:
        return _EXPORT_LINE in f.read()


def _append_to_rc(rc_path: str) -> bool:
    """Append the PATH export to rc_path. Returns True on success."""
    try:
        with open(rc_path, "a", encoding="utf-8") as f:
            f.write(f"\n{_MARKER}\n{_EXPORT_LINE}\n")
        return True
    except OSError:
        return False


def _fix_path() -> None:
    """Run after install: ensure ~/.local/bin is on PATH."""
    # Skip on Windows — pip puts scripts in Scripts\ which is already on PATH
    if sys.platform == "win32":
        return

    # Skip if already on PATH (system-wide install, virtualenv, etc.)
    if _already_on_path():
        return

    sep = "=" * 60
    print(f"\n{sep}")
    print("  netcheck — PATH setup")
    print(sep)

    patched: list[str] = []
    skipped: list[str] = []

    for rc in _RC_FILES:
        rc_expanded = os.path.expanduser(rc)
        if _already_written(rc_expanded):
            skipped.append(rc)
            continue
        if _append_to_rc(rc_expanded):
            patched.append(rc)
        else:
            skipped.append(rc)

    if patched:
        print(f"  ✅ Added ~/.local/bin to PATH in: {', '.join(patched)}")
        print()
        print("  Reload your shell to activate:")
        print("      source ~/.bashrc")
        print()
        print("  Then run:  netcheck --help")
    else:
        # Auto-fix failed — print manual instructions
        print("  ⚠️  ~/.local/bin is not on your PATH.")
        print("  Run this once to fix it:")
        print()
        print(f"      echo '{_EXPORT_LINE}' >> ~/.bashrc && source ~/.bashrc")
        print()
        print("  Then run:  netcheck --help")

    print(sep + "\n")


# ---------------------------------------------------------------------------
# Custom install commands
# ---------------------------------------------------------------------------

class PostInstall(install):
    def run(self):
        super().run()
        _fix_path()


class PostDevelop(develop):
    def run(self):
        super().run()
        _fix_path()


# ---------------------------------------------------------------------------
# setup() — metadata lives in pyproject.toml; only hooks defined here
# ---------------------------------------------------------------------------

setup(
    cmdclass={
        "install": PostInstall,
        "develop": PostDevelop,
    },
)
