"""
Watch mode loop for NetCheck CLI.

Decoupled from all CLI state — accepts any callable that executes one
check cycle and returns a bool (True = all passed).
"""
import sys
import threading
import time
from datetime import datetime
from typing import Callable


def _clear_screen() -> None:
    """Clear terminal screen using ANSI escape codes (no subprocess)."""
    if sys.stdout.isatty():
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


_watch_logs: list = []
_watch_logs_lock = threading.Lock()


def add_watch_log(msg: str) -> None:
    """Add a log entry to the watch mode rolling history (thread-safe)."""
    now_str = datetime.now().strftime("%H:%M:%S")
    entry = f"[{now_str}] {msg}"
    with _watch_logs_lock:
        _watch_logs.append(entry)
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
            except KeyboardInterrupt:
                raise  # Let the outer handler catch this
            except Exception as exc:  # noqa: BLE001
                err_msg = f"[watch] Error during check: {exc}"
                print(err_msg, file=sys.stderr)
                add_watch_log(err_msg)

            with _watch_logs_lock:
                logs_snapshot = list(_watch_logs)

            if logs_snapshot:
                print("\n🔔 RECENT WATCH ALERTS & LOGS:")
                print("─" * 60)
                for log in logs_snapshot:
                    print(log)
                print("─" * 60)

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nWatch mode stopped.")
        sys.exit(EXIT_OK)
