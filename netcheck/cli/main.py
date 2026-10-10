"""
NetCheck CLI main entry point.

Responsibilities (only routing — no business logic):
  1. Normalize legacy single-dash args
  2. Configure stdout/stderr encoding
  3. Load environment defaults
  4. Route to subcommand dispatcher or legacy flag parser
  5. Delegate to batch, quick-test, or single-check handlers

All heavy logic lives in: subcommands.py, batch.py, executor.py
"""
import os
import signal
import sys
from typing import Optional

from netcheck.cli.exitcodes import EXIT_BAD_ARGS, EXIT_ERROR, EXIT_FAIL, EXIT_INTERRUPT, EXIT_OK
from netcheck.cli.subcommands import SUBCOMMANDS, handle_subcommands

# Suppress BrokenPipeError when output is piped to head/grep/etc.
if hasattr(signal, "SIGPIPE"):
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------

def print_help() -> None:
    from netcheck import __version__

    cmd_name = "netcheck"
    if len(sys.argv) > 0:
        prog = sys.argv[0]
        if "netcheck" not in prog and ("__main__.py" in prog or "cli.py" in prog):
            cmd_name = "python3 -m netcheck"

    help_text = f"""Network Connectivity Checker - Advanced Version

Usage: {cmd_name} [OPTIONS] [input_file]
       {cmd_name} SUBCOMMAND [sub_args]

OPTIONS:
    -t, --timeout <seconds>     Connection timeout (default: 5)
    -j, --jobs <number>         Max parallel jobs (default: 10)
    -V, --verbose               Verbose output
    -f, --format <format>       Output format: text, json, csv, xml (default: text)
    -c, --combined              Create combined report with all results
    -q, --quick <host> <port>   Quick test mode (supports ranges: 80,443 or 8000-8100)
    -q, --quick <host:port>    Shorthand: -q 8.8.8.8:53  or  -q host:80,443  or  -q host:8000-9000
    -o, --output <file>         Save quick mode results to file
    -d, --dns <host>            Resolve DNS and show IP address (accepts URLs)
    -p, --ping <host>           Ping host using ICMP (accepts IPs/URLs/ranges)
    -s, --status <url>          Check HTTP/HTTPS status code and response time
    --cert <host>               Check SSL/TLS certificate validity and expiration
    --my-ip, -ip                Show all network interfaces and IP addresses (UP only)
    --my-ip --all               Show all interfaces including inactive ones
    --public                    Fetch and show public IP address
    --retry <number>            Retry failed connections N times (default: 1)
    --retry-delay <seconds>     Delay between retries in seconds (default: 1)
    --csv                       Input file is in CSV format (host,port)
    --json                      Output in JSON format (alias for -f json)
    --show <filter>             Filter -q/tcp results: all (default), success, or fail
    --alert <channels>          Alert channels to use: email,slack,webhook,desktop
    --alert-on <trigger>        When to alert: any (default), down, up
    --alert-cooldown <seconds>  Min seconds between same-direction alerts (default: 60)
    -h, --help                  Show this help message
    -v, --version               Show version information

SUBCOMMANDS (v{__version__}):
    tcp <host> <port>           Check TCP connectivity (accepts ranges)
    dns <host>                  Perform DNS lookup and show nameservers
    http <url>                  Validate HTTP response and size
    ssl <host> [port]           Validate SSL/TLS certificate validity
    ping <host>                 Ping host via native ICMP
    udp <host> <port>           UDP probe check
    mtr <host>                  MTR-style hop-by-hop latency analysis
    interfaces                  List local network interfaces
    ports                       List local listening ports and services
    traceroute <host>           Trace route to destination host
    scan <host>                 Perform quick concurrent port scan
    whois <target>              Lookup domain/IP registrar and registration details
    mcp                         Start MCP server (stdio transport)
    mcp install                 Print Claude Desktop config snippet
    mcp status                  Test MCP server health
    config [action]             Manage configuration (init, show, path, set-password, clear-password)
    serve <hosts_file>          Continuous check loop exposing Prometheus metrics

WATCH MODE:
    Any subcommand can be looped with:
      -w, --watch               Enable watch mode (clear screen and refresh)
      -i, --interval <seconds>  Refresh interval in seconds (default: 2.0)

    Combine with --alert to get notified on UP/DOWN transitions:
      {cmd_name} tcp google.com 443 -w --alert slack
      {cmd_name} tcp google.com 443 -w --alert slack --alert-on down
      {cmd_name} http https://example.com -w --alert email,slack -i 30

EXIT CODES:
    0   All checks passed
    1   One or more checks failed
    2   Invalid arguments / usage error
    3   Unexpected runtime error

INPUT:
    input_file                  File containing IP:port pairs (one per line)
                               If not specified, reads from stdin
                               Use --csv flag for CSV format files

EXAMPLES:
    # Quick TCP check (multiple formats)
    {cmd_name} -q google.com 443
    {cmd_name} -q 8.8.8.8:53
    {cmd_name} 192.168.1.1:80,443
    {cmd_name} -q myserver.com 8000-8010

    # Subcommand style
    {cmd_name} tcp google.com 443
    {cmd_name} dns github.com
    {cmd_name} http https://example.com
    {cmd_name} ssl github.com
    {cmd_name} ping 8.8.8.8
    {cmd_name} traceroute google.com
    {cmd_name} scan 192.168.1.1 -p 1-1000
    {cmd_name} whois google.com
    {cmd_name} mtr 8.8.8.8

    # Watch mode (loops until Ctrl+C)
    {cmd_name} tcp google.com 443 -w
    {cmd_name} tcp google.com 443 -w -i 10 --alert slack
    {cmd_name} tcp google.com 443 -w -i 10 --alert slack --alert-on down
    {cmd_name} http https://myapi.com -w --alert email,desktop --alert-cooldown 30

    # Batch mode
    {cmd_name} targets.txt
    echo "8.8.8.8 53" | {cmd_name}
    {cmd_name} --csv hosts.csv -f json

    # Configuration & alerts
    {cmd_name} config init
    {cmd_name} config set-password slack
    {cmd_name} config show

    # Local info
    {cmd_name} --my-ip
    {cmd_name} interfaces
    {cmd_name} ports"""
    print(help_text)


# ---------------------------------------------------------------------------
# Quick-test helper (legacy -q / tcp subcommand shared path)
# ---------------------------------------------------------------------------

def run_quick_test(
    host: str,
    port_str: str,
    timeout: float,
    max_jobs: int,
    fmt: str,
    output_file: Optional[str],
    retries: int,
    retry_delay: float,
    verbose: bool = False,
    exit_on_complete: bool = True,
    show_filter: str = "all",
) -> bool:
    from netcheck.cli.executor import execute_concurrent_checks
    from netcheck.utils.formatters import format_csv, format_json, format_text, format_xml
    from netcheck.utils.range_expanders import expand_ip_range, expand_port_range

    def _fmt(results, use_color=None) -> str:
        if fmt == "json":
            return format_json(results)
        elif fmt == "csv":
            return format_csv(results)
        elif fmt == "xml":
            return format_xml(results)
        return format_text(results, verbose=verbose, use_color=use_color)

    hosts = expand_ip_range(host)
    ports = expand_port_range(port_str)
    targets = [(h, p) for h in hosts for p in ports]

    if not targets:
        print("Error: No valid host or port specified", file=sys.stderr)
        if exit_on_complete:
            sys.exit(EXIT_BAD_ARGS)
        return False

    try:
        results = execute_concurrent_checks(targets, timeout, max_jobs, retries, retry_delay, verbose=verbose)
    except KeyboardInterrupt:
        sys.stderr.write("\nInterrupted.\n")
        sys.stderr.flush()
        if exit_on_complete:
            sys.exit(EXIT_INTERRUPT)
        raise

    if show_filter == "success":
        display = [r for r in results if r["success"]]
    elif show_filter == "fail":
        display = [r for r in results if not r["success"]]
    else:
        display = results

    if display:
        print(_fmt(display))
    else:
        label = "successful" if show_filter == "success" else "failed"
        print(f"No {label} results to display.")

    if output_file:
        try:
            with open(output_file, "w") as fh:
                fh.write(_fmt(display, use_color=False))
            print(f"Results saved to: {output_file} ({len(display)} items)")
        except Exception as exc:
            print(f"Error saving results to file {output_file}: {exc}", file=sys.stderr)

    all_success = all(r["success"] for r in results)
    if exit_on_complete:
        sys.exit(EXIT_OK if all_success else EXIT_FAIL)
    return all_success


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def _main_impl() -> None:
    # 1. Normalize legacy single-dash multi-char options
    for idx in range(1, len(sys.argv)):
        arg = sys.argv[idx]
        if arg == "-dns":
            sys.argv[idx] = "--dns"
        elif arg == "-ping":
            sys.argv[idx] = "--ping"
        elif arg == "-status":
            sys.argv[idx] = "--status"
        elif arg == "-cert":
            sys.argv[idx] = "--cert"
        elif arg in ("-tcp", "-udp", "-mtr", "-scan", "-whois",
                     "-http", "-ssl", "-traceroute", "-interfaces",
                     "-ports", "-serve", "-config"):
            # Route bare -subcmd → subcmd (e.g. -tcp → tcp)
            sys.argv[idx] = arg[1:]

    # 2. Force UTF-8 on stdout/stderr (prevents UnicodeEncodeError on Windows)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, TypeError):
        pass

    # PATH hint — Linux/macOS only.
    # Only warn when the netcheck binary actually lives in ~/.local/bin but
    # that directory is absent from PATH.  This means the user installed via
    # `pip install --user` and the shell `netcheck` command won't work even
    # though they are currently running us through `python -m netcheck` or a
    # full path.  Suppress the warning with NETCHECK_NO_PATH_WARN=1.
    if sys.platform != "win32" and "NETCHECK_NO_PATH_WARN" not in os.environ:  # Windows-only dev env: skipped on win32
        _local_bin = os.path.expanduser("~/.local/bin")
        _path_dirs = os.environ.get("PATH", "").split(":")
        if _local_bin not in _path_dirs:
            # Only warn when the binary genuinely exists there — otherwise the
            # warning is irrelevant (e.g. system-wide pip install, venv, etc.)
            _netcheck_bin = os.path.join(_local_bin, "netcheck")
            if os.path.isfile(_netcheck_bin):
                print(
                    "\n⚠️  netcheck is installed in ~/.local/bin but that directory "
                    "is not on your PATH.\n"
                    "   The  netcheck  command will not work from a new shell.\n"
                    "   Fix it by running:\n"
                    "     echo 'export PATH=\"$HOME/.local/bin:$PATH\"' >> ~/.bashrc && source ~/.bashrc\n"
                    "   (suppress this warning: export NETCHECK_NO_PATH_WARN=1)\n",
                    file=sys.stderr,
                )

    # 3. Load environment defaults
    env_timeout = 5.0
    if "NETCHECK_TIMEOUT" in os.environ:
        try:
            env_timeout = float(os.environ["NETCHECK_TIMEOUT"])
        except ValueError:
            pass

    env_jobs = 10
    if "NETCHECK_MAX_WORKERS" in os.environ:
        try:
            env_jobs = int(os.environ["NETCHECK_MAX_WORKERS"])
        except ValueError:
            pass

    env_no_color = "NO_COLOR" in os.environ or "NETCHECK_NO_COLOR" in os.environ

    # 4. No args — read stdin or show help
    if len(sys.argv) < 2:
        if not sys.stdin.isatty():
            lines = sys.stdin.read().splitlines()
            from netcheck.cli.batch import run_batch_lines
            run_batch_lines(lines, timeout=env_timeout, max_jobs=env_jobs,
                            format_name="text", combined=False, retries=1, retry_delay=1.0, verbose=False)
            return
        print_help()
        sys.exit(EXIT_BAD_ARGS)

    first_arg = sys.argv[1]

    # 5. Subcommand routing
    if first_arg in SUBCOMMANDS:
        handle_subcommands(first_arg, sys.argv[2:],
                           env_timeout=env_timeout, env_jobs=env_jobs, env_no_color=env_no_color)
        return

    # 5b. Bare target shorthand: netcheck host:port[,port|-range]
    #     e.g.  netcheck 8.8.8.8:53
    #           netcheck google.com:80,443
    #           netcheck 192.168.1.1:8000-8100
    #           netcheck [::1]:80
    from netcheck.utils.range_expanders import parse_target_string
    _maybe_host, _maybe_port = parse_target_string(first_arg)
    if _maybe_port is not None:
        run_quick_test(
            _maybe_host,
            _maybe_port,
            timeout=env_timeout,
            max_jobs=env_jobs,
            fmt="text",
            output_file=None,
            retries=1,
            retry_delay=1.0,
            verbose=False,
            show_filter="all",
        )
        return

    # 6. Legacy flags mode
    from netcheck.cli.args import make_legacy_parser
    parser = make_legacy_parser(env_timeout=env_timeout, env_jobs=env_jobs, env_no_color=env_no_color)
    args, _ = parser.parse_known_args()

    if args.help:
        print_help()
        sys.exit(EXIT_OK)

    if args.version:
        from netcheck import __version__
        print(f"netcheck version {__version__}")
        sys.exit(EXIT_OK)

    if args.mcp:
        from netcheck.mcp.server import start_mcp_server
        start_mcp_server()
        return

    fmt = "json" if args.json else args.format
    timeout = args.timeout
    retries = args.retry
    retry_delay = args.retry_delay
    verbose = args.verbose

    # Lazy imports for modules used only in legacy mode
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from netcheck.cli.executor import run_check_with_retry
    from netcheck.modules.dns import dns_lookup
    from netcheck.modules.http import check_http_status
    from netcheck.modules.interfaces import get_network_interfaces
    from netcheck.modules.ping import ping_host
    from netcheck.modules.ssl import check_ssl_certificate
    from netcheck.utils.formatters import format_csv, format_json, format_text, format_xml
    from netcheck.utils.range_expanders import expand_ip_range

    def _fmt(results, use_color=None) -> str:
        if fmt == "json":
            return format_json(results)
        elif fmt == "csv":
            return format_csv(results)
        elif fmt == "xml":
            return format_xml(results)
        return format_text(results, verbose=verbose, use_color=use_color)

    if args.my_ip:
        res = get_network_interfaces(all_interfaces=args.all, include_public=args.public)
        print(_fmt([res]))
        sys.exit(EXIT_OK if res["success"] else EXIT_FAIL)

    if args.dns:
        res = run_check_with_retry(dns_lookup, (args.dns, timeout), retries=retries, delay=retry_delay)
        print(_fmt([res]))
        sys.exit(EXIT_OK if res["success"] else EXIT_FAIL)

    if args.ping:
        hosts = expand_ip_range(args.ping)
        if len(hosts) == 1:
            res = run_check_with_retry(ping_host, (hosts[0], 4, timeout), retries=retries, delay=retry_delay)
            print(_fmt([res]))
            sys.exit(EXIT_OK if res["success"] else EXIT_FAIL)
        else:
            results = []
            try:
                with ThreadPoolExecutor(max_workers=args.jobs) as executor:
                    futures = {executor.submit(ping_host, h, 4, timeout): h for h in hosts}
                    for future in as_completed(futures):
                        try:
                            results.append(future.result())
                        except Exception as exc:
                            h = futures[future]
                            results.append({"type": "ping", "target": h, "status": "FAILED",
                                            "latency_ms": 0.0, "success": False,
                                            "error": str(exc), "metadata": {}})
            except KeyboardInterrupt:
                print("\nInterrupted.", file=sys.stderr)
                sys.exit(EXIT_INTERRUPT)
            results.sort(key=lambda r: r.get("target", ""))
            print(_fmt(results))
            sys.exit(EXIT_OK if all(r["success"] for r in results) else EXIT_FAIL)

    if args.status:
        res = run_check_with_retry(check_http_status, (args.status, timeout),
                                   retries=retries, delay=retry_delay)
        print(_fmt([res]))
        sys.exit(EXIT_OK if res["success"] else EXIT_FAIL)

    if args.cert:
        res = run_check_with_retry(check_ssl_certificate, (args.cert, 443, timeout),
                                   retries=retries, delay=retry_delay)
        print(_fmt([res]))
        sys.exit(EXIT_OK if res["success"] else EXIT_FAIL)

    if args.quick is not None:
        if len(args.quick) == 1:
            # User passed a single arg — try to parse it as host:port
            from netcheck.utils.range_expanders import parse_target_string
            _h, _p = parse_target_string(args.quick[0])
            if _p is not None:
                run_quick_test(_h, _p, timeout, args.jobs, fmt, args.output,
                               retries, retry_delay, verbose=verbose, show_filter=args.show)
                return
            else:
                print("Error: -q/--quick requires <host> <port>, or <host:port>.", file=sys.stderr)
                sys.exit(EXIT_BAD_ARGS)
        elif len(args.quick) == 2:
            host, port_str = args.quick
            run_quick_test(host, port_str, timeout, args.jobs, fmt, args.output,
                           retries, retry_delay, verbose=verbose, show_filter=args.show)
            return
        else:
            print("Error: -q/--quick accepts 1 (host:port) or 2 (<host> <port>) arguments.", file=sys.stderr)
            sys.exit(EXIT_BAD_ARGS)

    # Batch modes
    from netcheck.cli.batch import (
        parse_batch_content,
        parse_batch_file,
        parse_csv_content,
        parse_csv_file,
        run_batch_targets,
    )

    if args.csv:
        if args.input_file:
            targets = parse_csv_file(args.input_file)
        elif not sys.stdin.isatty():
            targets = parse_csv_content(sys.stdin.read())
        else:
            print("Error: No CSV input file or stdin stream provided", file=sys.stderr)
            sys.exit(EXIT_BAD_ARGS)
        run_batch_targets(targets, timeout, args.jobs, fmt, args.combined,
                          retries, retry_delay, verbose=verbose)
        return

    if args.input_file:
        targets = parse_batch_file(args.input_file)
        run_batch_targets(targets, timeout, args.jobs, fmt, args.combined,
                          retries, retry_delay, verbose=verbose)
        return

    if not sys.stdin.isatty():
        targets = parse_batch_content(sys.stdin.read())
        run_batch_targets(targets, timeout, args.jobs, fmt, args.combined,
                          retries, retry_delay, verbose=verbose)
        return

    print_help()
    sys.exit(EXIT_BAD_ARGS)


def main() -> None:
    """Top-level entry point with Ctrl+C and pipeline signal handling."""
    try:
        _main_impl()
    except KeyboardInterrupt:
        sys.stderr.write("\nInterrupted.\n")
        sys.stderr.flush()
        sys.exit(EXIT_INTERRUPT)
    except BrokenPipeError:
        # Pipe was closed (e.g. | head). Exit silently.
        sys.exit(EXIT_OK)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"netcheck: unexpected error: {exc}\n")
        sys.stderr.flush()
        sys.exit(EXIT_ERROR)
