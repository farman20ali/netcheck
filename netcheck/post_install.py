"""
netcheck/post_install.py

Detects whether ~/.local/bin is on PATH on Linux/macOS and offers to fix it.
Called as the `netcheck-setup` console script after pip install.

Users are directed here by the pip install output:
    Successfully installed netcheckx-X.Y.Z
    Run `netcheck-setup` to finish PATH configuration.
"""

from __future__ import annotations

import os
import sys

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
    try:
        with open(rc_path, "a", encoding="utf-8") as f:
            f.write(f"\n{_MARKER}\n{_EXPORT_LINE}\n")
        return True
    except OSError:
        return False


def run() -> None:
    sep = "=" * 60

    # ── Windows: scripts go to Scripts\ which pip already puts on PATH ──
    if sys.platform == "win32":
        print("✅ Windows detected — no PATH setup needed.")
        return

    print(f"\n{sep}")
    print("  netcheck — post-install PATH setup")
    print(sep)

    # ── Already fine ────────────────────────────────────────────────────
    if _already_on_path():
        print("  ✅ ~/.local/bin is already on your PATH.")
        print("  Run:  netcheck --help")
        print(f"{sep}\n")
        return

    # ── Try to auto-fix ─────────────────────────────────────────────────
    patched: list[str] = []
    failed: list[str] = []

    for rc in _RC_FILES:
        rc_expanded = os.path.expanduser(rc)
        if _already_written(rc_expanded):
            continue                            # already patched on a previous run
        if _append_to_rc(rc_expanded):
            patched.append(rc)
        else:
            failed.append(rc)

    if patched:
        print(f"  ✅ Added ~/.local/bin to PATH in: {', '.join(patched)}")
        print()
        print("  Reload your shell now:")
        print("      source ~/.bashrc")
        print()
        print("  Then run:  netcheck --help")
    else:
        # Could not write — print manual step
        print("  ⚠️  Could not auto-update shell rc files.")
        print("  Run this command once to fix PATH manually:")
        print()
        print(f"      echo '{_EXPORT_LINE}' >> ~/.bashrc && source ~/.bashrc")
        print()
        print("  Then run:  netcheck --help")

    print(f"{sep}\n")


if __name__ == "__main__":
    run()
