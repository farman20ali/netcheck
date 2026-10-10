"""
Concurrent execution engine for NetCheck batch TCP checks.

This module is pure: it takes targets, runs them concurrently, and returns results.
No printing, no sys.exit — all I/O lives in the caller (main.py / batch.py).
"""
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Tuple

from netcheck.modules.tcp import check_tcp_connect
from netcheck.utils.formatters import get_colors
from netcheck.utils.retry import retry_call


def run_check_with_retry(
    check_fn: Callable,
    args: tuple = (),
    kwargs: Optional[dict] = None,
    retries: int = 1,
    delay: float = 1.0,
) -> Dict[str, Any]:
    """
    Run a check function and retry if it returns success=False.

    On final failure, returns the original failed result dict (with full metadata)
    rather than raising an exception.
    """
    if kwargs is None:
        kwargs = {}

    def _run() -> Dict[str, Any]:
        res = check_fn(*args, **kwargs)
        if not res.get("success", False):
            raise RuntimeError(res.get("error") or "Check returned unsuccessful status")
        return res

    try:
        return retry_call(_run, retries=retries, delay=delay)
    except Exception:
        # Re-run once to return the full failed result dict with metadata intact
        try:
            return check_fn(*args, **kwargs)
        except Exception as inner_e:
            return {
                "target": str(args[0]) if args else "unknown",
                "status": "FAILED",
                "latency_ms": 0.0,
                "success": False,
                "error": str(inner_e),
                "metadata": {},
            }


def execute_concurrent_checks(
    targets: List[Tuple[str, int]],
    timeout: float,
    max_jobs: int,
    retries: int,
    retry_delay: float,
    verbose: bool = False,
) -> List[Dict[str, Any]]:
    """
    Run TCP checks for a list of (host, port) targets concurrently.

    Returns a list of result dicts in completion order. Verbose mode prints
    real-time status lines to stderr (never stdout).
    """
    results: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=max_jobs) as executor:
        futures: Dict = {}
        for host, port in targets:
            try:
                port_val = int(port)
                fut = executor.submit(
                    run_check_with_retry,
                    check_tcp_connect,
                    args=(host, port_val, timeout),
                    retries=retries,
                    delay=retry_delay,
                )
                futures[fut] = (host, port)
            except ValueError:
                res = {
                    "type": "tcp",
                    "target": f"{host}:{port}",
                    "status": "FAILED",
                    "latency_ms": 0.0,
                    "success": False,
                    "error": f"Invalid port number: {port}",
                    "metadata": {"host": host, "port": port},
                }
                results.append(res)
                if verbose:
                    sys.stderr.write(f"✗ FAILED: {host}:{port} (Invalid port number)\n")
                    sys.stderr.flush()

        completed = 0
        total = len(futures)

        for fut in as_completed(futures):
            host, port = futures[fut]
            try:
                res = fut.result()
                results.append(res)
            except Exception as exc:
                res = {
                    "target": f"{host}:{port}",
                    "status": "FAILED",
                    "latency_ms": 0.0,
                    "success": False,
                    "error": str(exc),
                    "metadata": {"host": host, "port": port},
                }
                results.append(res)

            completed += 1

            if verbose:
                use_color = sys.stdout.isatty()
                c = get_colors(use_color)
                if res.get("success", False):
                    sys.stderr.write(
                        f"{c['green']}✓ SUCCESS:{c['reset']} {host}:{port} "
                        f"({res.get('latency_ms', '?')}ms)\n"
                    )
                else:
                    sys.stderr.write(
                        f"{c['red']}✗ FAILED:{c['reset']} {host}:{port} "
                        f"({res.get('error', 'unknown error')})\n"
                    )
                sys.stderr.flush()
            elif total > 5 and sys.stdout.isatty():
                pct = int(completed / total * 100)
                sys.stdout.write(f"\rProgress: {completed}/{total} completed ({pct}%)...")
                sys.stdout.flush()

        if total > 5 and sys.stdout.isatty() and not verbose:
            print("")

    return results
