"""
Shared formatting helpers used across all formatters.

Utilities: ANSI strip/pad, color map, result-type detection.
"""
import re
import sys
from typing import Any, Dict, Optional


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from a string for accurate visible length calculation."""
    return re.sub(r'\033\[[0-9;]*m', '', text)


def pad_right(text: str, width: int) -> str:
    """Right-pad a string to `width` visible characters, ignoring ANSI escapes."""
    visible_len = len(strip_ansi(text))
    padding = max(0, width - visible_len)
    return text + (" " * padding)


def get_colors(use_color: Optional[bool] = None) -> Dict[str, str]:
    """
    Return ANSI color codes when output is a TTY (or use_color=True).

    Pass use_color=False to always disable colors (e.g. when writing to a file).
    Pass use_color=None to auto-detect based on sys.stdout.isatty().
    """
    if use_color is None:
        use_color = sys.stdout.isatty()
    if use_color:
        return {
            "green":  "\033[92m",
            "red":    "\033[91m",
            "yellow": "\033[93m",
            "blue":   "\033[94m",
            "cyan":   "\033[96m",
            "bold":   "\033[1m",
            "reset":  "\033[0m",
        }
    return {k: "" for k in ("green", "red", "yellow", "blue", "cyan", "bold", "reset")}


def detect_result_type(res: Dict[str, Any]) -> str:
    """
    Return the canonical check type of a result dict.

    Checks the `type` field first; falls back to metadata-key heuristics
    for results that were built before explicit `type` tagging existed.
    """
    t = res.get("type")
    if t:
        return t

    meta = res.get("metadata", {})
    target = res.get("target")

    if target == "interfaces" or "interfaces" in meta:
        return "interfaces"
    if "resolved_host" in meta:
        return "dns"
    if "status_code" in meta and "valid_until" not in meta:
        return "http"
    if "valid_until" in meta:
        return "ssl"
    if "packets_sent" in meta:
        return "ping"
    if target == "ports" or "listening_ports" in meta:
        return "ports"
    if "open_ports" in meta:
        return "scan"
    if "hops" in meta:
        return "traceroute"
    if "rdap_source" in meta:
        return "whois"
    if "port" in meta and "valid_until" not in meta and "status_code" not in meta:
        return "tcp"

    return "tcp"
