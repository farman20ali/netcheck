"""
Watch mode loop for NetCheck CLI.

Decoupled from all CLI state — accepts any callable that executes one
check cycle and returns a bool (True = all passed).
"""
import os
import platform
import sys
import time
from datetime import datetime
from typing import Callable


def _clear_screen() -> None:
    """Clear terminal screen cross-platform."""
    if platform.system().lower() == "windows":
        os.system("cls")
    else:
        os.system("clear")


_watch_logs = []


def add_watch_log(msg: str) -> None:
    """Add a log entry to the watch mode rolling history."""
    now_str = datetime.now().strftime("%H:%M:%S")
    _watch_logs.append(f"[{now_str}] {msg}")
    if len(_watch_logs) > 8:
        _watch_logs.pop(0)


def run_watch_loop(execute_fn: Callable[[], bool], interval: float) -> None:
    """
    Loop indefinitely, calling execute_fn every `interval` seconds.

    Clears the screen before each run and shows a timestamp header.
    Exits cleanly on KeyboardInterrupt (Ctrl+C) with exit code 0.

    Important: SystemExit raised inside execute_fn (e.g. from sys.exit() in
    subcommand helpers) is caught and suppressed so the watch loop continues.
    Only KeyboardInterrupt (Ctrl+C) stops the loop.
    """
    from netcheck.cli.exitcodes import EXIT_OK

    print(
        "Watch mode active — press Ctrl+C to stop.\n"
        f"Refreshing every {interval}s."
    )

    try:
        while True:
            _clear_screen()
            print(
                f"NetCheck Watch Mode — Interval: {interval}s — "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            try:
                execute_fn()
            except SystemExit:
                # Subcommands call sys.exit(); absorb it so the loop continues.
                pass
            except Exception as exc:  # noqa: BLE001
                err_msg = f"[watch] Error during check: {exc}"
                print(err_msg, file=sys.stderr)
                add_watch_log(err_msg)

            if _watch_logs:
                print("\n🔔 RECENT WATCH ALERTS & LOGS:")
                print("─" * 60)
                for log in _watch_logs:
                    print(log)
                print("─" * 60)

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nWatch mode stopped.")
        sys.exit(EXIT_OK)
