"""
netcheck.utils.formatters package.

Public API — all format_* functions are importable directly from here.
"""
from netcheck.utils.formatters.base import (
    detect_result_type as _detect_result_type,
)
from netcheck.utils.formatters.base import (
    get_colors,
    pad_right,
    strip_ansi,
)
from netcheck.utils.formatters.csv_fmt import format_csv
from netcheck.utils.formatters.json_fmt import format_json
from netcheck.utils.formatters.text_fmt import format_text
from netcheck.utils.formatters.xml_fmt import format_xml

# Legacy alias used internally (keep until all callers are updated)
_detect_result_type = _detect_result_type

__all__ = [
    "format_json",
    "format_csv",
    "format_xml",
    "format_text",
    "get_colors",
    "pad_right",
    "strip_ansi",
    "_detect_result_type",
]
