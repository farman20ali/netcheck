"""
CSV formatter for all NetCheck check types.
"""
import csv
import io
from datetime import datetime
from typing import Any, Dict, List

from netcheck.utils.formatters.base import detect_result_type


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _writer(output: io.StringIO) -> csv.writer:
    return csv.writer(output)


def _fmt_interfaces(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    output = io.StringIO()
    w = _writer(output)
    w.writerow(["Interface", "IPv4", "IPv6", "Status", "Default_Gateway", "Public_IP"])
    gw = meta.get("gateway_ip", "")
    pub = meta.get("public_ip", "")
    for name, iface in sorted(meta.get("interfaces", {}).items()):
        w.writerow([name, ", ".join(iface.get("ipv4", [])),
                    ", ".join(iface.get("ipv6", [])), iface.get("status", ""), gw, pub])
    return output.getvalue()


def _fmt_dns(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    output = io.StringIO()
    w = _writer(output)
    w.writerow(["Target", "Resolved_Host", "IP", "Reverse_DNS", "Success", "Latency_MS", "Error"])
    ips = meta.get("ips", [])
    rev = meta.get("reverse_dns", "") or ""
    success = "SUCCESS" if res.get("success", False) else "FAILED"
    lat = res.get("latency_ms") if res.get("latency_ms") is not None else "N/A"
    err = res.get("error", "") or ""
    if ips:
        for ip in ips:
            w.writerow([res.get("target"), meta.get("resolved_host"), ip, rev, success, lat, err])
    else:
        w.writerow([res.get("target"), meta.get("resolved_host"), "", rev, success, lat, err])
    return output.getvalue()


def _fmt_http(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    output = io.StringIO()
    w = _writer(output)
    w.writerow(["Target", "Status_Code", "Redirect_URL", "Size_Bytes", "Success", "Latency_MS", "Error"])
    w.writerow([
        res.get("target"),
        meta.get("status_code") if meta.get("status_code") is not None else "N/A",
        meta.get("redirect_url") or "",
        meta.get("size_bytes", 0),
        "SUCCESS" if res.get("success", False) else "FAILED",
        res.get("latency_ms") if res.get("latency_ms") is not None else "N/A",
        res.get("error") or "",
    ])
    return output.getvalue()


def _fmt_ssl(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    output = io.StringIO()
    w = _writer(output)
    w.writerow(["Target", "Subject_CN", "Issuer_O", "Valid_From", "Valid_Until",
                "Days_Until_Expiry", "Expired", "Success", "Latency_MS", "Error"])
    w.writerow([
        res.get("target"),
        meta.get("subject", {}).get("commonName", ""),
        meta.get("issuer", {}).get("organizationName", ""),
        meta.get("valid_from") or "",
        meta.get("valid_until") or "",
        meta.get("days_until_expiry") if meta.get("days_until_expiry") is not None else "N/A",
        "True" if meta.get("expired", False) else "False",
        "SUCCESS" if res.get("success", False) else "FAILED",
        res.get("latency_ms") if res.get("latency_ms") is not None else "N/A",
        res.get("error") or "",
    ])
    return output.getvalue()


def _fmt_ping(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    output = io.StringIO()
    w = _writer(output)
    w.writerow(["Target", "Host", "Packets_Sent", "Packets_Received", "Packet_Loss_Pct",
                "Min_RTT_MS", "Avg_RTT_MS", "Max_RTT_MS", "Success", "Latency_MS", "Error"])
    w.writerow([
        res.get("target"), meta.get("host", ""),
        meta.get("packets_sent", 0), meta.get("packets_received", 0),
        meta.get("packet_loss_pct", 0.0),
        meta.get("min_rtt_ms") if meta.get("min_rtt_ms") is not None else "N/A",
        meta.get("avg_rtt_ms") if meta.get("avg_rtt_ms") is not None else "N/A",
        meta.get("max_rtt_ms") if meta.get("max_rtt_ms") is not None else "N/A",
        "SUCCESS" if res.get("success", False) else "FAILED",
        res.get("latency_ms") if res.get("latency_ms") is not None else "N/A",
        res.get("error") or "",
    ])
    return output.getvalue()


def _fmt_ports(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    output = io.StringIO()
    w = _writer(output)
    w.writerow(["Proto", "Address", "Port", "Process", "PID"])
    for p in meta.get("listening_ports", []):
        w.writerow([p.get("proto", "TCP"), p.get("address", "*"),
                    p.get("port", ""), p.get("process", ""), p.get("pid", "")])
    return output.getvalue()


def _fmt_scan(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    output = io.StringIO()
    w = _writer(output)
    w.writerow(["Target", "Port", "Status", "Service", "Latency_MS"])
    for p in meta.get("open_ports", []):
        w.writerow([res.get("target"), p.get("port", ""), "OPEN",
                    p.get("service", ""),
                    p.get("latency_ms") if p.get("latency_ms") is not None else "N/A"])
    for p in meta.get("closed_ports", []):
        w.writerow([res.get("target"), p.get("port", ""), "CLOSED", p.get("service", ""), "N/A"])
    return output.getvalue()


def _fmt_traceroute(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    output = io.StringIO()
    w = _writer(output)
    w.writerow(["Target", "Hop", "IP", "Hostname", "Latency_MS"])
    for h in meta.get("hops", []):
        w.writerow([res.get("target"), h.get("hop", ""), h.get("ip", "*"),
                    h.get("name", "*"),
                    h.get("latency_ms") if h.get("latency_ms") is not None else "*"])
    return output.getvalue()


def _fmt_whois(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    output = io.StringIO()
    w = _writer(output)
    w.writerow(["Target", "Type", "Source", "Registrar", "Creation_Date", "Success", "Error"])
    w.writerow([
        res.get("target"), meta.get("type", ""), meta.get("rdap_source", ""),
        meta.get("registrar", ""), meta.get("creation_date", ""),
        "SUCCESS" if res.get("success", False) else "FAILED",
        res.get("error") or "",
    ])
    return output.getvalue()


def _fmt_tcp_batch(results: List[Dict[str, Any]]) -> str:
    output = io.StringIO()
    w = _writer(output)
    all_success = all(r.get("success", False) for r in results)
    all_fail = all(not r.get("success", False) for r in results)
    ts = _now()
    if all_success and results:
        w.writerow(["Status", "Host", "Port", "Method", "Timestamp"])
        for r in results:
            host = r.get("metadata", {}).get("host", r.get("target", "").split(":")[0])
            port = r.get("metadata", {}).get("port", r.get("target", "").split(":")[-1])
            w.writerow(["SUCCESS", host, port, r.get("metadata", {}).get("method", "socket"), ts])
    elif all_fail and results:
        w.writerow(["Status", "Host", "Port", "Reason", "Timestamp"])
        for r in results:
            host = r.get("metadata", {}).get("host", r.get("target", "").split(":")[0])
            port = r.get("metadata", {}).get("port", r.get("target", "").split(":")[-1])
            w.writerow(["FAILED", host, port, r.get("error", "timeout") or "timeout", ts])
    else:
        w.writerow(["Status", "Host", "Port", "Method/Reason", "Timestamp"])
        for r in results:
            host = r.get("metadata", {}).get("host", r.get("target", "").split(":")[0])
            port = r.get("metadata", {}).get("port", r.get("target", "").split(":")[-1])
            status = "SUCCESS" if r.get("success", False) else "FAILED"
            mr = (r.get("metadata", {}).get("method", "socket") if r.get("success", False)
                  else (r.get("error", "timeout") or "timeout"))
            w.writerow([status, host, port, mr, ts])
    return output.getvalue()


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


def format_csv(results: List[Dict[str, Any]]) -> str:
    """Format a list of check results to CSV string."""
    if not results:
        return ""
    if len(results) == 1:
        res = results[0]
        res_type = detect_result_type(res)
        fmt_fn = _SINGLE_DISPATCH.get(res_type)
        if fmt_fn:
            return fmt_fn(res)
    return _fmt_tcp_batch(results)
