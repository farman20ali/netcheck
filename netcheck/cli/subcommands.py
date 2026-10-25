"""
Subcommand dispatcher for NetCheck CLI.

Each subcommand (tcp, dns, http, ssl, ping, interfaces, ports,
traceroute, scan, whois, mcp) is handled by a dedicated private
helper, keeping routing logic clean.
"""
import argparse
import sys
from typing import List, Tuple

from netcheck.cli.args import make_base_parser
from netcheck.cli.executor import run_check_with_retry
from netcheck.cli.exitcodes import EXIT_BAD_ARGS, EXIT_ERROR, EXIT_FAIL, EXIT_INTERRUPT, EXIT_OK
from netcheck.modules.dns import dns_lookup
from netcheck.modules.http import check_http_status
from netcheck.modules.interfaces import get_network_interfaces
from netcheck.modules.ping import ping_host
from netcheck.modules.ssl import check_ssl_certificate

# Module-level imports for the check functions used most frequently
from netcheck.utils.formatters import format_csv, format_json, format_text, format_xml
from netcheck.utils.range_expanders import expand_ip_range, expand_port_range

_alert_manager = None
_metrics_registry = None

def _get_alert_manager(flap_threshold: int = 2, cooldown: float = 300.0):
    global _alert_manager
    if _alert_manager is None:
        from netcheck.utils.alert_state import AlertStateManager
        _alert_manager = AlertStateManager(flap_threshold=flap_threshold, cooldown_seconds=cooldown)
    return _alert_manager

def _record_results_and_check_alerts(results: List[dict], check_type: str, args) -> None:
    if _metrics_registry is not None:
        for r in results:
            target = r.get("target") or "unknown"
            success = r.get("success", False)
            latency = r.get("latency_ms")
            _metrics_registry.record(target, check_type, success, latency)

    alert_channels_str = getattr(args, "alert", "")
    if not alert_channels_str:
        try:
            from netcheck.utils.config import NetCheckConfig
            cfg = NetCheckConfig.load()
            enabled = []
            alerts_section = cfg.get("alerts", {}) or cfg
            for ch in ["email", "slack", "webhook", "desktop"]:
                if alerts_section.get(ch, {}).get("enabled"):
                    enabled.append(ch)
            if enabled:
                alert_channels_str = ",".join(enabled)
        except Exception:
            pass

    if alert_channels_str:
        channels = [c.strip() for c in alert_channels_str.split(",") if c.strip()]
        if channels:
            try:
                from netcheck.utils.alerting import AlertDispatcher
                from netcheck.utils.config import NetCheckConfig

                cfg = NetCheckConfig.load()
                cooldown = getattr(args, "alert_cooldown", 60.0)
                alert_on = getattr(args, "alert_on", "any")

                alerts_section = cfg.get("alerts", {}) or cfg
                flap_threshold = alerts_section.get("flap_threshold", 2)
                if not isinstance(flap_threshold, int):
                    flap_threshold = 2

                manager = _get_alert_manager(flap_threshold, cooldown)
                dispatcher = AlertDispatcher(cfg)

                for r in results:
                    target = r.get("target") or "unknown"
                    success = r.get("success", False)
                    error_msg = r.get("error")

                    event = manager.update(target, success, error_msg, alert_on=alert_on)
                    if event:
                        icon = "✅" if event.new_state == "UP" else "❌"
                        alert_msg = (
                            f"[alert] {icon} {target} is {event.new_state} "
                            f"({event.old_state} → {event.new_state})"
                        )
                        print(f"\n{alert_msg}", file=sys.stderr)
                        try:
                            from netcheck.cli.watch import add_watch_log
                            add_watch_log(alert_msg)
                        except ImportError:
                            pass
                        dispatcher.dispatch(event, channels=channels)
            except Exception as exc:
                print(f"[netcheck] Alert dispatch error: {exc}", file=sys.stderr)



# ---------------------------------------------------------------------------
# Output helper
# ---------------------------------------------------------------------------

def _fmt_output(results, fmt: str, verbose: bool = False, use_color=None) -> str:
    if fmt == "json":
        return format_json(results)
    elif fmt == "csv":
        return format_csv(results)
    elif fmt == "xml":
        return format_xml(results)
    return format_text(results, verbose=verbose, use_color=use_color)


# ---------------------------------------------------------------------------
# Per-subcommand argument builders
# ---------------------------------------------------------------------------

def _build_tcp_parser(base: argparse.ArgumentParser, env_jobs: int) -> None:
    base.add_argument("host")
    base.add_argument("port")
    base.add_argument("-j", "--jobs", type=int, default=env_jobs)
    base.add_argument("-o", "--output")
    base.add_argument("--show", default="all", choices=["all", "success", "fail"])


def _build_dns_parser(base: argparse.ArgumentParser) -> None:
    base.add_argument("host")


def _build_http_parser(base: argparse.ArgumentParser) -> None:
    base.add_argument("url")
    base.add_argument("--method", "-X", default="GET",
                      choices=["GET", "HEAD", "POST", "PUT", "DELETE", "PATCH"])
    base.add_argument("--header", "-H", action="append", dest="headers")
    base.add_argument("--auth")


def _build_ssl_parser(base: argparse.ArgumentParser) -> None:
    base.add_argument("host")
    base.add_argument("port", type=int, nargs="?", default=443)


def _build_ping_parser(base: argparse.ArgumentParser) -> None:
    base.add_argument("host")
    base.add_argument("-c", "--count", type=int, default=4)


def _build_interfaces_parser(base: argparse.ArgumentParser) -> None:
    base.add_argument("--all", action="store_true")
    base.add_argument("--public", action="store_true")


def _build_traceroute_parser(base: argparse.ArgumentParser) -> None:
    base.add_argument("host")
    base.add_argument("-m", "--max-hops", type=int, default=30)


def _build_scan_parser(base: argparse.ArgumentParser, env_jobs: int) -> None:
    base.add_argument("host")
    base.add_argument("-p", "--ports",
                      help="Comma-separated ports or range, e.g. 80-100")
    base.add_argument("-j", "--jobs", type=int, default=env_jobs)


def _build_whois_parser(base: argparse.ArgumentParser) -> None:
    base.add_argument("target")


# ---------------------------------------------------------------------------
# Per-subcommand execution helpers
# ---------------------------------------------------------------------------

def _run_tcp(args, env_jobs: int) -> bool:
    """Run TCP check with optional range expansion and output filtering."""
    hosts = expand_ip_range(args.host)
    ports = expand_port_range(args.port)
    targets = [(h, p) for h in hosts for p in ports]

    if not targets:
        print("Error: No valid host or port specified", file=sys.stderr)
        return False

    from netcheck.cli.executor import execute_concurrent_checks
    results = execute_concurrent_checks(
        targets, args.timeout, getattr(args, "jobs", env_jobs),
        args.retry, args.retry_delay, verbose=args.verbose,
    )

    show_filter = getattr(args, "show", "all")
    if show_filter == "success":
        display = [r for r in results if r["success"]]
    elif show_filter == "fail":
        display = [r for r in results if not r["success"]]
    else:
        display = results

    use_color = None if not args.no_color else False
    fmt = "json" if args.json else args.format

    if display:
        print(_fmt_output(display, fmt, verbose=args.verbose, use_color=use_color))
    else:
        label = "successful" if show_filter == "success" else "failed"
        print(f"No {label} results to display.")

    output_file = getattr(args, "output", None)
    if output_file:
        try:
            with open(output_file, "w") as fh:
                fh.write(_fmt_output(display, fmt, verbose=args.verbose, use_color=False))
            print(f"Results saved to: {output_file} ({len(display)} items)")
        except Exception as exc:
            print(f"Error saving results: {exc}", file=sys.stderr)

    _record_results_and_check_alerts(results, "tcp", args)
    return all(r["success"] for r in results)


def _run_dns(args) -> bool:
    use_color = None if not args.no_color else False
    fmt = "json" if args.json else args.format
    res = run_check_with_retry(dns_lookup, (args.host, args.timeout),
                               retries=args.retry, delay=args.retry_delay)
    print(_fmt_output([res], fmt, verbose=args.verbose, use_color=use_color))
    _record_results_and_check_alerts([res], "dns", args)
    return res["success"]


def _run_http(args) -> bool:
    use_color = None if not args.no_color else False
    fmt = "json" if args.json else args.format
    custom_headers = {}
    if args.headers:
        for hdr in args.headers:
            if ":" in hdr:
                k, v = hdr.split(":", 1)
                custom_headers[k.strip()] = v.strip()
    auth_tuple = None
    if args.auth and ":" in args.auth:
        user, pw = args.auth.split(":", 1)
        auth_tuple = (user, pw)
    res = run_check_with_retry(
        check_http_status,
        (args.url, args.timeout),
        kwargs={"method": args.method, "headers": custom_headers or None, "auth": auth_tuple},
        retries=args.retry,
        delay=args.retry_delay,
    )
    print(_fmt_output([res], fmt, verbose=args.verbose, use_color=use_color))
    _record_results_and_check_alerts([res], "http", args)
    return res["success"]


def _run_ssl(args) -> bool:
    use_color = None if not args.no_color else False
    fmt = "json" if args.json else args.format
    res = run_check_with_retry(check_ssl_certificate, (args.host, args.port, args.timeout),
                               retries=args.retry, delay=args.retry_delay)
    print(_fmt_output([res], fmt, verbose=args.verbose, use_color=use_color))
    _record_results_and_check_alerts([res], "ssl", args)
    return res["success"]


def _run_ping(args) -> bool:
    use_color = None if not args.no_color else False
    fmt = "json" if args.json else args.format
    res = run_check_with_retry(ping_host, (args.host, args.count, args.timeout),
                               retries=args.retry, delay=args.retry_delay)
    print(_fmt_output([res], fmt, verbose=args.verbose, use_color=use_color))
    _record_results_and_check_alerts([res], "ping", args)
    return res["success"]


def _run_interfaces(args) -> bool:
    use_color = None if not args.no_color else False
    fmt = "json" if args.json else args.format
    res = get_network_interfaces(all_interfaces=args.all, include_public=args.public)
    print(_fmt_output([res], fmt, verbose=args.verbose, use_color=use_color))
    _record_results_and_check_alerts([res], "interfaces", args)
    return res["success"]


def _run_ports(args) -> bool:
    use_color = None if not args.no_color else False
    fmt = "json" if args.json else args.format
    from netcheck.modules.interfaces import check_listening_ports
    res = check_listening_ports()
    print(_fmt_output([res], fmt, verbose=args.verbose, use_color=use_color))
    _record_results_and_check_alerts([res], "ports", args)
    return res["success"]


def _run_traceroute(args) -> bool:
    use_color = None if not args.no_color else False
    fmt = "json" if args.json else args.format
    from netcheck.modules.traceroute import traceroute as run_traceroute
    res = run_traceroute(args.host, max_hops=args.max_hops, timeout=args.timeout)
    print(_fmt_output([res], fmt, verbose=args.verbose, use_color=use_color))
    _record_results_and_check_alerts([res], "traceroute", args)
    return res["success"]


def _run_scan(args) -> bool:
    use_color = None if not args.no_color else False
    fmt = "json" if args.json else args.format
    from netcheck.modules.port_scanner import scan_ports
    port_list = None
    if args.ports:
        try:
            if "-" in args.ports:
                start_p, end_p = map(int, args.ports.split("-"))
                port_list = list(range(start_p, end_p + 1))
            else:
                port_list = [int(p.strip()) for p in args.ports.split(",")]
        except ValueError:
            print("Error: Invalid ports format. Use e.g. 80,443 or 80-100", file=sys.stderr)
            sys.exit(EXIT_BAD_ARGS)
    res = scan_ports(args.host, ports=port_list, timeout=args.timeout,
                     max_workers=getattr(args, "jobs", 20))
    print(_fmt_output([res], fmt, verbose=args.verbose, use_color=use_color))
    _record_results_and_check_alerts([res], "scan", args)
    return res["success"]


def _run_whois(args) -> bool:
    use_color = None if not args.no_color else False
    fmt = "json" if args.json else args.format
    from netcheck.modules.whois import lookup_registration
    res = lookup_registration(args.target)
    print(_fmt_output([res], fmt, verbose=args.verbose, use_color=use_color))
    _record_results_and_check_alerts([res], "whois", args)
    return res["success"]


def _build_serve_parser(base: argparse.ArgumentParser) -> None:
    base.add_argument("hosts_file")
    base.add_argument("--metrics", action="store_true", help="Enable Prometheus metrics endpoint")
    base.add_argument("-p", "--port", type=int, default=9090, help="Port for metrics (default: 9090)")


def _run_serve(args, env_jobs: int) -> bool:
    import time

    from netcheck.cli.batch import parse_batch_file, parse_csv_file
    from netcheck.cli.executor import execute_concurrent_checks
    from netcheck.utils.range_expanders import expand_ip_range, expand_port_range

    filepath = args.hosts_file
    if filepath.lower().endswith(".csv"):
        targets = parse_csv_file(filepath)
    else:
        targets = parse_batch_file(filepath)

    expanded: List[Tuple[str, int]] = []
    for host, p_str in targets:
        ports = expand_port_range(p_str)
        hosts = expand_ip_range(host)
        for h in hosts:
            for p in ports:
                expanded.append((h, p))

    if not expanded:
        print("Error: No valid targets found to serve", file=sys.stderr)
        return False

    server = None
    if args.metrics:
        from netcheck.utils.prometheus import MetricsRegistry, MetricsServer
        global _metrics_registry
        _metrics_registry = MetricsRegistry()
        server = MetricsServer(_metrics_registry, host="0.0.0.0", port=args.port)
        server.start()
        print(f"📡 Prometheus metrics exporter listening on {server.url()}")

    print(f"Monitoring {len(expanded)} targets in serve loop every {args.interval}s...")
    try:
        while True:
            results = execute_concurrent_checks(
                expanded, args.timeout, getattr(args, "jobs", env_jobs),
                args.retry, args.retry_delay, verbose=args.verbose
            )
            _record_results_and_check_alerts(results, "tcp", args)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopping serve mode...")
    finally:
        if server:
            server.stop()
    return True



def _run_udp(args) -> bool:
    """Run a UDP probe check."""
    from netcheck.modules.udp import check_udp
    use_color = None if not args.no_color else False
    fmt = "json" if args.json else args.format

    result = check_udp(args.host, args.port, timeout=args.timeout)
    results = [result]
    _record_results_and_check_alerts(results, "udp", args)
    print(_fmt_output(results, fmt, verbose=args.verbose, use_color=use_color))
    return result["success"]


def _run_mtr(args) -> bool:
    """Run an MTR-style hop-by-hop latency check."""
    from netcheck.modules.mtr import mtr
    use_color = None if not args.no_color else False
    fmt = "json" if args.json else args.format

    result = mtr(
        args.host,
        count=args.count,
        max_hops=args.max_hops,
        timeout=args.timeout,
    )
    results = [result]
    _record_results_and_check_alerts(results, "mtr", args)
    print(_fmt_output(results, fmt, verbose=args.verbose, use_color=use_color))
    return result["success"]


def _run_mcp(sub_args: List[str]) -> None:
    """Handle: netcheck mcp [install|status]"""
    if not sub_args or sub_args[0] == "start":
        from netcheck.mcp.server import start_mcp_server
        start_mcp_server()
    elif sub_args[0] == "install":
        from netcheck.mcp.commands import cmd_mcp_install
        cmd_mcp_install()
    elif sub_args[0] == "status":
        from netcheck.mcp.commands import cmd_mcp_status
        cmd_mcp_status()
    else:
        print(f"Unknown mcp subcommand: {sub_args[0]}", file=sys.stderr)
        print("Usage: netcheck mcp [install|status]", file=sys.stderr)
        sys.exit(EXIT_BAD_ARGS)


def _run_config(sub_args: List[str]) -> None:
    """Handle: netcheck config [init|edit|show|path|set-password|clear-password]"""
    from netcheck.utils.config import NetCheckConfig

    action = sub_args[0] if sub_args else "show"

    if action == "init":
        NetCheckConfig.init_wizard()
    elif action == "edit":
        import os
        import subprocess
        editor = os.environ.get("EDITOR", "notepad" if sys.platform == "win32" else "nano")
        subprocess.run([editor, str(NetCheckConfig.path())])
    elif action == "show":
        print(NetCheckConfig.show())
    elif action == "path":
        print(NetCheckConfig.path())
    elif action == "set-password":
        service = sub_args[1] if len(sub_args) > 1 else "email"
        NetCheckConfig.set_password(service)
    elif action == "clear-password":
        service = sub_args[1] if len(sub_args) > 1 else "email"
        NetCheckConfig.clear_password(service)
    elif action in ("purge", "remove", "reset"):
        NetCheckConfig.purge()
    elif action == "test-alert":
        channel = sub_args[1] if len(sub_args) > 1 else "email"
        from datetime import datetime, timezone

        from netcheck.utils.alert_state import AlertEvent
        from netcheck.utils.alerting import AlertDispatcher

        print(f"Sending test alert to channel '{channel}'...")
        event = AlertEvent(
            target="netcheck-test-target",
            old_state="UNKNOWN",
            new_state="UP",
            timestamp=datetime.now(timezone.utc),
            consecutive=1,
            last_error="Test event from NetCheck CLI config test-alert command",
        )

        cfg = NetCheckConfig.load()
        dispatcher = AlertDispatcher(cfg)
        results = dispatcher.dispatch(event, channels=[channel])

        for ch, success in results.items():
            status = "✅ SUCCESS" if success else "❌ FAILED"
            print(f"Channel '{ch}' dispatch status: {status}")
    else:
        print(f"Unknown config subcommand: {action}", file=sys.stderr)
        print(
            "Usage: netcheck config [init|edit|show|path|set-password <svc>|clear-password <svc>|purge|test-alert <channel>]",
            file=sys.stderr,
        )
        sys.exit(EXIT_BAD_ARGS)


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

SUBCOMMANDS = frozenset({
    "tcp", "dns", "http", "ssl", "ping",
    "interfaces", "ports", "traceroute", "scan", "whois", "mcp", "config", "serve",
    "udp", "mtr",
})


def handle_subcommands(
    subcommand: str,
    sub_args: List[str],
    env_timeout: float = 5.0,
    env_jobs: int = 10,
    env_no_color: bool = False,
) -> None:
    """
    Parse sub_args for the given subcommand, execute once or in watch loop.
    Calls sys.exit() with the correct exit code.
    """
    # MCP and config don't follow the watch/format pattern
    if subcommand == "mcp":
        _run_mcp(sub_args)
        return
    if subcommand == "config":
        _run_config(sub_args)
        return

    base = make_base_parser(
        f"netcheck {subcommand}",
        env_timeout=env_timeout,
        env_jobs=env_jobs,
        env_no_color=env_no_color,
    )

    # Attach subcommand-specific positional/optional args
    if subcommand == "tcp":
        _build_tcp_parser(base, env_jobs)
    elif subcommand == "dns":
        _build_dns_parser(base)
    elif subcommand == "http":
        _build_http_parser(base)
    elif subcommand == "ssl":
        _build_ssl_parser(base)
    elif subcommand == "ping":
        _build_ping_parser(base)
    elif subcommand == "interfaces":
        _build_interfaces_parser(base)
    elif subcommand == "ports":
        pass  # no extra args
    elif subcommand == "traceroute":
        _build_traceroute_parser(base)
    elif subcommand == "scan":
        _build_scan_parser(base, env_jobs)
    elif subcommand == "whois":
        _build_whois_parser(base)
    elif subcommand == "serve":
        _build_serve_parser(base)
    elif subcommand == "udp":
        base.add_argument("host")
        base.add_argument("port", type=int)
    elif subcommand == "mtr":
        base.add_argument("host")
        base.add_argument("-c", "--count", type=int, default=3)
        base.add_argument("-m", "--max-hops", type=int, default=30)
    else:
        base.print_help()
        sys.exit(EXIT_BAD_ARGS)

    args = base.parse_args(sub_args)

    # Map subcommand name → execute_fn
    _dispatch = {
        "tcp":        lambda: _run_tcp(args, env_jobs),
        "dns":        lambda: _run_dns(args),
        "http":       lambda: _run_http(args),
        "ssl":        lambda: _run_ssl(args),
        "ping":       lambda: _run_ping(args),
        "interfaces": lambda: _run_interfaces(args),
        "ports":      lambda: _run_ports(args),
        "traceroute": lambda: _run_traceroute(args),
        "scan":       lambda: _run_scan(args),
        "whois":      lambda: _run_whois(args),
        "serve":      lambda: _run_serve(args, env_jobs),
        "udp":        lambda: _run_udp(args),
        "mtr":        lambda: _run_mtr(args),
    }
    execute_fn = _dispatch[subcommand]

    if args.watch:
        from netcheck.cli.watch import run_watch_loop
        run_watch_loop(execute_fn, args.interval)
    else:
        try:
            success = execute_fn()
            sys.exit(EXIT_OK if success else EXIT_FAIL)
        except KeyboardInterrupt:
            from netcheck.utils.threads import cleanup_thread_queues
            cleanup_thread_queues()
            sys.stderr.write("\nInterrupted.\n")
            sys.stderr.flush()
            sys.exit(EXIT_INTERRUPT)
        except Exception as exc:
            print(f"Unexpected error: {exc}", file=sys.stderr)
            sys.exit(EXIT_ERROR)
