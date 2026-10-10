"""
netcheck/utils/formatters.py — backward-compatibility shim.

All logic has moved into netcheck/utils/formatters/ (the package).
This module re-exports everything so existing imports like:
    from netcheck.utils.formatters import format_json
continue to work without change.

DO NOT add new logic here.
"""
from netcheck.utils.formatters import (  # noqa: F401
    _detect_result_type,
    format_csv,
    format_json,
    format_text,
    format_xml,
    get_colors,
    pad_right,
    strip_ansi,
)
