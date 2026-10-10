"""
Shared argument parser factories for NetCheck CLI.

All subcommand parsers are built here, keeping main.py and subcommands.py
free of argparse boilerplate. Environment defaults are injected at construction.
"""
import argparse
import sys


class NetCheckArgumentParser(argparse.ArgumentParser):
    """Custom parser that shows the full help (with examples) on any argument error."""

    def error(self, message: str) -> None:
        from netcheck.cli.exitcodes import EXIT_BAD_ARGS
        print(f"Error: {message}\n", file=sys.stderr)
        # Import lazily to avoid circular dependency with main.py
        from netcheck.cli.main import print_help
        print_help()
        sys.exit(EXIT_BAD_ARGS)


def make_base_parser(
    prog: str,
    env_timeout: float = 5.0,
    env_jobs: int = 10,
    env_no_color: bool = False,
) -> argparse.ArgumentParser:
    """Return a base parser pre-loaded with flags shared by every subcommand."""
    parser = argparse.ArgumentParser(prog=prog, add_help=True)
    parser.add_argument("-t", "--timeout", type=float, default=env_timeout,
                        help="Connection timeout in seconds (default: %(default)s)")
    parser.add_argument("-f", "--format", default="text",
                        choices=["text", "json", "csv", "xml"],
                        help="Output format (default: %(default)s)")
    parser.add_argument("--json", action="store_true",
                        help="Output in JSON format (alias for -f json)")
    parser.add_argument("--retry", type=int, default=1,
                        help="Retry failed checks N times (default: %(default)s)")
    parser.add_argument("--retry-delay", type=float, default=1.0,
                        help="Delay between retries in seconds (default: %(default)s)")
    parser.add_argument("-V", "--verbose", action="store_true",
                        help="Verbose real-time output")
    parser.add_argument("-w", "--watch", action="store_true",
                        help="Watch/loop mode — repeat check until Ctrl+C")
    parser.add_argument("-i", "--interval", type=float, default=2.0,
                        help="Watch mode refresh interval in seconds (default: %(default)s)")
    parser.add_argument("--no-color", action="store_true", default=env_no_color,
                        help="Disable ANSI color output")
    parser.add_argument("--alert", default="",
                        help="Comma-separated alert channels (e.g. email,slack,webhook,desktop)")
    parser.add_argument("--alert-cooldown", type=float, default=60.0,
                        help="Per-direction cooldown between repeated alerts in seconds (default: %(default)s)")
    parser.add_argument(
        "--alert-on",
        default="any",
        choices=["any", "down", "up"],
        help=(
            "When to fire alerts: "
            "'any'=on every state change (default), "
            "'down'=only when target goes DOWN, "
            "'up'=only on recovery to UP"
        ),
    )
    return parser


def make_legacy_parser(
    env_timeout: float = 5.0,
    env_jobs: int = 10,
    env_no_color: bool = False,
) -> NetCheckArgumentParser:
    """Return the legacy top-level parser (flags mode, not subcommand mode)."""
    parser = NetCheckArgumentParser(add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("-v", "--version", action="store_true")
    parser.add_argument("-q", "--quick", nargs="*")
    parser.add_argument("-d", "--dns")
    parser.add_argument("-p", "--ping")
    parser.add_argument("-s", "--status")
    parser.add_argument("--cert")
    parser.add_argument("-ip", "--my-ip", action="store_true")
    parser.add_argument("--public", action="store_true")
    parser.add_argument("--mcp", action="store_true")
    parser.add_argument("--csv", action="store_true")
    parser.add_argument("-t", "--timeout", type=float, default=env_timeout)
    parser.add_argument("-j", "--jobs", type=int, default=env_jobs)
    parser.add_argument("-f", "--format", default="text",
                        choices=["text", "json", "csv", "xml"])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("-c", "--combined", action="store_true")
    parser.add_argument("-o", "--output")
    parser.add_argument("--retry", type=int, default=1)
    parser.add_argument("--retry-delay", type=float, default=1.0)
    parser.add_argument("-V", "--verbose", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--no-color", action="store_true", default=env_no_color)
    parser.add_argument("--show", default="all",
                        choices=["all", "success", "fail"])
    parser.add_argument("--alert", default="")
    parser.add_argument("--alert-cooldown", type=float, default=60.0)
    parser.add_argument("--alert-on", default="any",
                        choices=["any", "down", "up"])
    parser.add_argument("input_file", nargs="?")
    return parser
