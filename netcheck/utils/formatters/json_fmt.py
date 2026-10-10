"""
JSON formatter for all NetCheck check types.

format_json() is the sole public API. It dispatches to per-type
formatting functions rather than using heuristics inline.
"""
import json
from datetime import datetime
from typing import Any, Dict, List

from netcheck.utils.formatters.base import detect_result_type


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _fmt_interfaces(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    return json.dumps({"check_date": _now(), "type": "interfaces", **meta}, indent=2)


def _fmt_dns(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    return json.dumps({
        "check_date": _now(), "type": "dns",
        "target": res.get("target"),
        "success": res.get("success", False),
        "error": res.get("error"),
        "latency_ms": res.get("latency_ms"),
        **meta,
    }, indent=2)


def _fmt_http(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    return json.dumps({
        "check_date": _now(), "type": "http",
        "target": res.get("target"),
        "success": res.get("success", False),
        "error": res.get("error"),
        "latency_ms": res.get("latency_ms"),
        **meta,
    }, indent=2)


def _fmt_ssl(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    return json.dumps({
        "check_date": _now(), "type": "ssl",
        "target": res.get("target"),
        "success": res.get("success", False),
        "error": res.get("error"),
        "latency_ms": res.get("latency_ms"),
        **meta,
    }, indent=2)


def _fmt_ping(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    return json.dumps({
        "check_date": _now(), "type": "ping",
        "target": res.get("target"),
        "success": res.get("success", False),
        "error": res.get("error"),
        "latency_ms": res.get("latency_ms"),
        **meta,
    }, indent=2)


def _fmt_ports(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    return json.dumps({
        "check_date": _now(), "type": "ports",
        "success": res.get("success", False),
        "error": res.get("error"),
        "listening_ports": meta.get("listening_ports", []),
    }, indent=2)


def _fmt_scan(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    return json.dumps({
        "check_date": _now(), "type": "scan",
        "target": res.get("target"),
        "success": res.get("success", False),
        "error": res.get("error"),
        "ips": meta.get("ips", []),
        "open_ports": meta.get("open_ports", []),
        "closed_ports": meta.get("closed_ports", []),
    }, indent=2)


def _fmt_traceroute(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    return json.dumps({
        "check_date": _now(), "type": "traceroute",
        "target": res.get("target"),
        "success": res.get("success", False),
        "error": res.get("error"),
        "hops": meta.get("hops", []),
    }, indent=2)


def _fmt_whois(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    return json.dumps({
        "check_date": _now(), "check_type": "whois",
        "target": res.get("target"),
        "success": res.get("success", False),
        "error": res.get("error"),
        "rdap_type": meta.get("type", ""),
        "rdap_source": meta.get("rdap_source", ""),
        "registrar": meta.get("registrar", ""),
        "creation_date": meta.get("creation_date", ""),
    }, indent=2)


def _fmt_ping_batch(results: List[Dict[str, Any]]) -> str:
    ping_results = []
    for r in results:
        meta = r.get("metadata", {})
        ping_results.append({
            "target": r.get("target"),
            "success": r.get("success", False),
            "error": r.get("error"),
            "latency_ms": r.get("latency_ms"),
            "packets_sent": meta.get("packets_sent"),
            "packets_received": meta.get("packets_received"),
            "packet_loss_pct": meta.get("packet_loss_pct"),
            "min_rtt_ms": meta.get("min_rtt_ms"),
            "avg_rtt_ms": meta.get("avg_rtt_ms"),
            "max_rtt_ms": meta.get("max_rtt_ms"),
        })
    return json.dumps({
        "check_date": _now(), "type": "ping",
        "count": len(ping_results), "results": ping_results,
    }, indent=2)


def _fmt_tcp_batch(results: List[Dict[str, Any]]) -> str:
    all_success = all(r.get("success", False) for r in results)
    all_fail = all(not r.get("success", False) for r in results)
    formatted = []
    for r in results:
        host = r.get("metadata", {}).get("host", r.get("target", "").split(":")[0])
        try:
            port = int(r.get("metadata", {}).get("port", r.get("target", "").split(":")[-1]))
        except ValueError:
            port = 0
        ts = _now()
        if r.get("success", False):
            formatted.append({"status": "success", "host": host, "port": port,
                               "method": r.get("metadata", {}).get("method", "socket"), "timestamp": ts})
        else:
            formatted.append({"status": "failed", "host": host, "port": port,
                               "reason": r.get("error", "timeout") or "timeout", "timestamp": ts})
    if all_success and results:
        data = {"check_date": _now(), "results": formatted}
    elif all_fail and results:
        data = {"check_date": _now(), "failures": formatted}
    else:
        data = {"check_date": _now(), "all_results": formatted}
    return json.dumps(data, indent=2)


_SINGLE_DISPATCH = {
    "interfaces": _fmt_interfaces,
    "dns": _fmt_dns,
    "http": _fmt_http,
    "ssl": _fmt_ssl,
    "ping": _fmt_ping,
    "ports": _fmt_ports,
    "scan": _fmt_scan,
    "traceroute": _fmt_traceroute,
    "whois": _fmt_whois,
}


def format_json(results: List[Dict[str, Any]]) -> str:
    """Format a list of check results to JSON string."""
    if not results:
        return json.dumps({}, indent=2)

    if len(results) == 1:
        res = results[0]
        res_type = detect_result_type(res)
        fmt_fn = _SINGLE_DISPATCH.get(res_type)
        if fmt_fn:
            return fmt_fn(res)

    # Multi-result: ping batch or TCP batch
    if results and all(detect_result_type(r) == "ping" for r in results):
        return _fmt_ping_batch(results)

    return _fmt_tcp_batch(results)
