"""
Batch input parsing and batch execution for NetCheck.

Handles CSV files, plain-text host:port files, and stdin batch mode.
All functions are pure (no sys.exit) except run_batch_targets which
calls sys.exit at completion to set the correct exit code.
"""
import csv
import io
import sys
from datetime import datetime
from typing import List, Tuple

from netcheck.cli.executor import execute_concurrent_checks
from netcheck.cli.exitcodes import EXIT_FAIL, EXIT_OK
from netcheck.utils.formatters import format_csv, format_json, format_text, format_xml
from netcheck.utils.normalize import parse_line_to_raw_host_port
from netcheck.utils.range_expanders import expand_ip_range, expand_port_range

# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_csv_content(content: str) -> List[Tuple[str, str]]:
    """Parse CSV content (host,port) into a list of (host, port_str) tuples."""
    targets: List[Tuple[str, str]] = []
    try:
        reader = csv.reader(io.StringIO(content))
        first_row = next(reader, None)
        if first_row:
            if not (
                len(first_row) >= 2
                and (
                    first_row[0].lower() in ("host", "target", "hostname")
                    or first_row[1].lower() in ("port", "ports")
                )
            ):
                targets.append((first_row[0].strip(), first_row[1].strip()))
        for row in reader:
            if len(row) >= 2:
                targets.append((row[0].strip(), row[1].strip()))
    except Exception as exc:
        print(f"Error parsing CSV content: {exc}", file=sys.stderr)
    return targets


def parse_csv_file(filepath: str) -> List[Tuple[str, str]]:
    """Read and parse a CSV file of (host,port) pairs."""
    try:
        with open(filepath, "r", newline="") as fh:
            return parse_csv_content(fh.read())
    except Exception as exc:
        print(f"Error reading CSV file {filepath}: {exc}", file=sys.stderr)
        return []


def parse_batch_content(content: str) -> List[Tuple[str, str]]:
    """
    Parse lenient plain-text batch content.

    Each non-blank, non-comment line is parsed by parse_line_to_raw_host_port
    which understands: IP:port, host port, URL, CIDR, ranges, etc.
    """
    targets: List[Tuple[str, str]] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        h, p = parse_line_to_raw_host_port(line)
        if h and p:
            targets.append((h, p))
        else:
            print(
                f"⚠️  Warning: skipping malformed line: '{stripped}'",
                file=sys.stderr,
            )
    return targets


def parse_batch_file(filepath: str) -> List[Tuple[str, str]]:
    """Read and parse a plain-text batch file of targets."""
    try:
        with open(filepath, "r") as fh:
            return parse_batch_content(fh.read())
    except Exception as exc:
        print(f"Error reading batch file {filepath}: {exc}", file=sys.stderr)
        return []


# ---------------------------------------------------------------------------
# Output helper (shared between batch and quick modes)
# ---------------------------------------------------------------------------

def _format_output(results, format_name: str, verbose: bool = False, use_color=None) -> str:
    if format_name == "json":
        return format_json(results)
    elif format_name == "csv":
        return format_csv(results)
    elif format_name == "xml":
        return format_xml(results)
    else:
        return format_text(results, verbose=verbose, use_color=use_color)


# ---------------------------------------------------------------------------
# Batch execution
# ---------------------------------------------------------------------------

def run_batch_targets(
    targets: List[Tuple[str, str]],
    timeout: float,
    max_jobs: int,
    fmt: str,
    combined: bool,
    retries: int,
    retry_delay: float,
    verbose: bool = False,
) -> None:
    """
    Expand targets, run concurrent TCP checks, write result files, and exit.

    Writes:
      result-YYYY-MM-DD.{ext}   — successful checks
      fail-YYYY-MM-DD.{ext}     — failed checks
      combined-YYYY-MM-DD.{ext} — all results (only when --combined is set)
    """
    expanded: List[Tuple[str, int]] = []
    for host, p_str in targets:
        ports = expand_port_range(p_str)
        hosts = expand_ip_range(host)
        for h in hosts:
            for p in ports:
                expanded.append((h, p))

    if not expanded:
        print("Error: No targets found to test", file=sys.stderr)
        sys.exit(EXIT_FAIL)

    results = execute_concurrent_checks(expanded, timeout, max_jobs, retries, retry_delay, verbose=verbose)

    date_str = datetime.now().strftime("%Y-%m-%d")
    ext_map = {"json": "json", "csv": "csv", "xml": "xml"}
    ext = ext_map.get(fmt, "txt")

    success_results = [r for r in results if r["success"]]
    fail_results = [r for r in results if not r["success"]]

    res_filename = f"result-{date_str}.{ext}"
    fail_filename = f"fail-{date_str}.{ext}"
    comb_filename = f"combined-{date_str}.{ext}"

    if success_results:
        try:
            with open(res_filename, "w", encoding="utf-8") as fh:
                fh.write(_format_output(success_results, fmt, verbose=verbose, use_color=False))
            print(f"Successful checks written to: {res_filename} ({len(success_results)} items)")
        except Exception as exc:
            print(f"Error saving successful results to {res_filename}: {exc}", file=sys.stderr)

    if fail_results:
        try:
            with open(fail_filename, "w", encoding="utf-8") as fh:
                fh.write(_format_output(fail_results, fmt, verbose=verbose, use_color=False))
            print(f"Failed checks written to: {fail_filename} ({len(fail_results)} items)")
        except Exception as exc:
            print(f"Error saving failed results to {fail_filename}: {exc}", file=sys.stderr)

    if combined:
        try:
            with open(comb_filename, "w", encoding="utf-8") as fh:
                fh.write(_format_output(results, fmt, verbose=verbose, use_color=False))
            print(f"Combined report written to: {comb_filename}")
        except Exception as exc:
            print(f"Error saving combined report to {comb_filename}: {exc}", file=sys.stderr)

    print("Check Complete!")
    print(_format_output(results, fmt, verbose=verbose))
    sys.exit(EXIT_OK if not fail_results else EXIT_FAIL)


def run_batch_lines(
    lines: List[str],
    timeout: float,
    max_jobs: int,
    format_name: str,
    combined: bool,
    retries: int,
    retry_delay: float,
    verbose: bool = False,
) -> None:
    """Parse lines from stdin and delegate to run_batch_targets."""
    content = "\n".join(lines)
    targets = parse_batch_content(content)
    run_batch_targets(targets, timeout, max_jobs, format_name, combined, retries, retry_delay, verbose=verbose)
