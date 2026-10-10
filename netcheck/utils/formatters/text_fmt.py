"""
Human-readable text formatter for all NetCheck check types.

Each check type has a dedicated private function.
format_text() dispatches to these, then falls back to the bulk-tabular formatter.
"""
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from netcheck.utils.formatters.base import detect_result_type, get_colors, pad_right

# ---------------------------------------------------------------------------
# Per-type formatters
# ---------------------------------------------------------------------------

def _fmt_interfaces(res: Dict[str, Any], c: dict) -> str:
    meta = res.get("metadata", {})
    lines = []
    lines.append("Network Interface Information")
    lines.append("━" * 40)
    lines.append("")

    if not meta.get("all_interfaces_shown", False):
        lines.append(f"📡 {c['bold']}Active Network Interfaces (UP only):{c['reset']}")
        lines.append("   Use '--my-ip --all' to show all interfaces")
    else:
        lines.append(f"📡 {c['bold']}All Network Interfaces:{c['reset']}")
    lines.append("")

    for name in sorted(meta.get("interfaces", {}).keys()):
        iface = meta["interfaces"][name]
        lines.append(f"Interface: {c['bold']}{name}{c['reset']}")
        if iface.get("ipv4"):
            lines.append(f"  IPv4: {', '.join(iface['ipv4'])}")
        if iface.get("ipv6"):
            lines.append(f"  IPv6: {', '.join(iface['ipv6'])}")
        state = iface.get("status", "DOWN")
        if state == "UP":
            status_str = f"{c['green']}✅ UP{c['reset']}"
        else:
            status_str = f"{c['yellow']}⚠️  {state}{c['reset']}"
        lines.append(f"  Status: {status_str}")
        lines.append("")

    gw_ip = meta.get("gateway_ip")
    gw_dev = meta.get("gateway_dev")
    if gw_ip:
        lines.append(f"🌐 {c['bold']}Default Gateway:{c['reset']} {gw_ip}")
        if gw_dev:
            lines.append(f"   Via Interface: {gw_dev}")
        lines.append("")

    public_ip = meta.get("public_ip")
    lines.append(f"🌍 {c['bold']}Public IP Address:{c['reset']}")
    if public_ip and public_ip != "Unknown":
        lines.append(f"  {public_ip}")
    elif meta.get("public_ip_checked", False):
        lines.append("  Unable to determine (no internet or curl/wget not available)")
    else:
        lines.append("  Not checked (use --public to retrieve)")
    lines.append("")

    if "SNAP" in os.environ and len(meta.get("interfaces", {})) == 1 and "default" in meta.get("interfaces", {}):
        lines.append(f"⚠️  {c['yellow']}Running inside strict snap confinement. Complete interface list could not be read.{c['reset']}")
        lines.append("   To resolve this, please run the following command to connect the plug:")
        lines.append(f"   {c['bold']}sudo snap connect netcheck:network-observe{c['reset']}")
        lines.append("")

    lines.append("━" * 40)
    return "\n".join(lines)


def _fmt_ports(res: Dict[str, Any], c: dict) -> str:
    meta = res.get("metadata", {})
    lines = []
    lines.append("Local Listening Ports & Services")
    lines.append("━" * 40)
    lines.append("")

    listening_ports = meta.get("listening_ports", [])
    if listening_ports:
        lines.append(f"🔓 {c['bold']}Active Listening Sockets:{c['reset']}")
        lines.append("  Proto  Local Address                  Port   Process/Service (PID)")
        lines.append("  " + "─" * 64)
        for p in sorted(listening_ports, key=lambda x: x.get("port", 0)):
            proto = p.get("proto", "TCP")
            addr = p.get("address", "*")
            port = p.get("port", 0)
            proc = p.get("process", "Unknown")
            pid = p.get("pid", "")
            pid_str = f" ({pid})" if pid else ""
            proc_details = f"{proc}{pid_str}"
            lines.append(f"  {proto:<5}  {pad_right(addr, 30)} {port:<6} {proc_details}")
        lines.append("")
    else:
        lines.append("No active listening ports found or failed to retrieve.")
        lines.append("")
        if "SNAP" in os.environ:
            lines.append(f"⚠️  {c['yellow']}Running inside strict snap confinement.{c['reset']}")
            lines.append("   To query local listening ports, you must connect the plugs:")
            lines.append(f"   {c['bold']}sudo snap connect netcheck:network-observe{c['reset']}")
            lines.append(f"   {c['bold']}sudo snap connect netcheck:system-observe{c['reset']}")
            lines.append("")

    lines.append("━" * 40)
    return "\n".join(lines)


def _fmt_dns(res: Dict[str, Any], c: dict) -> str:
    meta = res.get("metadata", {})
    target = res.get("target", "")
    lines = []
    lines.append(f"DNS Lookup for: {target}")
    lines.append("━" * 40)
    lines.append(f"Hostname: {meta.get('resolved_host')}")
    lines.append("")
    lines.append("IP Addresses:")
    for ip in meta.get("ips", []):
        if ":" in ip:
            lines.append(f"  {ip} (IPv6)")
        else:
            lines.append(f"  {ip}")
    lines.append("")

    aliases = meta.get("aliases", [])
    if aliases:
        lines.append("Aliases:")
        for alias in aliases:
            lines.append(f"  {alias}")
        lines.append("")

    rev = meta.get("reverse_dns")
    if rev:
        lines.append("Reverse DNS:")
        lines.append(f"  {rev}")
        lines.append("")

    lines.append("━" * 40)
    return "\n".join(lines)


def _fmt_http(res: Dict[str, Any], c: dict, verbose: bool) -> str:
    meta = res.get("metadata", {})
    target = res.get("target", "")
    latency = res.get("latency_ms")
    lines = []
    lines.append(f"HTTP Status Check for: {target}")
    lines.append("━" * 40)
    lines.append("Sending HTTP request...")
    lines.append("")

    status_code = meta.get("status_code")
    size = meta.get("size_bytes")
    redirect_url = meta.get("redirect_url")
    headers = meta.get("headers", {})

    if size is None:
        size_human = "Unknown"
    elif size > 1048576:
        size_human = f"{size / 1048576:.2f} MB"
    elif size > 1024:
        size_human = f"{size / 1024:.2f} KB"
    else:
        size_human = f"{size} bytes"

    STATUS_DESC = {
        200: "OK", 201: "Created", 202: "Accepted", 204: "No Content",
        301: "Moved Permanently", 302: "Found (Temporary Redirect)", 303: "See Other",
        304: "Not Modified", 307: "Temporary Redirect", 308: "Permanent Redirect",
        400: "Bad Request", 401: "Unauthorized", 403: "Forbidden", 404: "Not Found",
        405: "Method Not Allowed", 408: "Request Timeout", 429: "Too Many Requests",
        500: "Internal Server Error", 501: "Not Implemented",
        502: "Bad Gateway", 503: "Service Unavailable", 504: "Gateway Timeout",
    }
    code_desc = STATUS_DESC.get(status_code, "Unknown Status") if status_code else "Unknown"

    if status_code and 200 <= status_code < 300:
        status_icon = f"{c['green']}✅ SUCCESS{c['reset']}"
    elif status_code and 300 <= status_code < 400:
        status_icon = f"{c['yellow']}↪ REDIRECT{c['reset']}"
    else:
        status_icon = f"{c['red']}❌ FAILED{c['reset']}"

    url_to_show = target if len(target) <= 38 else target[:35] + "..."
    lines.append("┌─────────────────────────────────────────────┐")
    lines.append(f"│ URL: {pad_right(url_to_show, 38)} │")
    lines.append("├─────────────────────────────────────────────┤")
    lines.append(f"│ Status: {pad_right(status_icon, 35)} │")
    lines.append(f"│ Code: {pad_right(f'{status_code} {code_desc}', 37)} │")
    lines.append(f"│ Response Time: {pad_right(f'{latency}ms' if latency is not None else 'N/A', 28)} │")
    lines.append(f"│ Content Size: {pad_right(size_human, 29)} │")
    if redirect_url:
        redir = redirect_url if len(redirect_url) <= 27 else redirect_url[:24] + "..."
        lines.append(f"│ Redirected To: {pad_right(redir, 27)} │")
    lines.append("└─────────────────────────────────────────────┘")
    lines.append("")

    if verbose and headers:
        lines.append("Response Headers:")
        lines.append("─" * 45)
        for k, v in sorted(headers.items()):
            lines.append(f"{k.title()}: {v}")
        lines.append("─" * 45)
        lines.append("")

    lines.append("━" * 40)
    return "\n".join(lines)


def _fmt_ssl(res: Dict[str, Any], c: dict, verbose: bool) -> str:
    meta = res.get("metadata", {})
    target = res.get("target", "")
    success = res.get("success", False)
    error = res.get("error", "")
    lines = []
    lines.append(f"SSL/TLS Certificate Check for: {target}")
    lines.append("━" * 40)
    lines.append(f"Connecting to {target}...")
    lines.append("")

    expired = meta.get("expired", False)
    days_until_expiry = meta.get("days_until_expiry")
    subject = meta.get("subject", {})
    issuer = meta.get("issuer", {})
    valid_from = meta.get("valid_from")
    valid_until = meta.get("valid_until")
    sans = meta.get("sans", [])
    verification_error = meta.get("verification_error") or error

    if verification_error:
        status_icon = f"{c['red']}❌ VERIFICATION FAILED{c['reset']}"
    elif expired:
        status_icon = f"{c['red']}❌ EXPIRED{c['reset']}"
    elif not success:
        status_icon = f"{c['red']}❌ FAILED{c['reset']}"
    elif days_until_expiry is not None and days_until_expiry < 30:
        status_icon = f"{c['yellow']}⚠️  EXPIRING SOON{c['reset']}"
    else:
        status_icon = f"{c['green']}✅ VALID{c['reset']}"

    subject_cn = subject.get("commonName", "")
    if len(subject_cn) > 29:
        subject_cn = subject_cn[:26] + "..."
    issuer_o = issuer.get("organizationName", "")
    if len(issuer_o) > 31:
        issuer_o = issuer_o[:28] + "..."
    host_to_show = target if len(target) <= 37 else target[:34] + "..."

    lines.append("┌─────────────────────────────────────────────┐")
    lines.append(f"│ Host: {pad_right(host_to_show, 37)} │")
    lines.append("├─────────────────────────────────────────────┤")
    lines.append(f"│ Status: {pad_right(status_icon, 35)} │")
    if verification_error:
        err_to_show = str(verification_error)
        if len(err_to_show) > 36:
            err_to_show = err_to_show[:33] + "..."
        lines.append(f"│ Error: {pad_right(err_to_show, 36)} │")
    lines.append("├─────────────────────────────────────────────┤")
    lines.append("│ Certificate Details:                        │")
    lines.append("├─────────────────────────────────────────────┤")
    lines.append(f"│ Subject: CN = {pad_right(subject_cn, 29)} │")
    lines.append(f"│ Issuer: O = {pad_right(issuer_o, 31)} │")
    lines.append("├─────────────────────────────────────────────┤")
    lines.append(f"│ Valid From: {pad_right(valid_from if valid_from else 'N/A', 31)} │")
    lines.append(f"│ Valid Until: {pad_right(valid_until if valid_until else 'N/A', 30)} │")
    dexp_str = str(days_until_expiry) if days_until_expiry is not None else "N/A"
    lines.append(f"│ Days Until Expiry: {pad_right(dexp_str, 24)} │")
    cipher = meta.get("cipher")
    tls_version = meta.get("tls_version")
    fingerprint = meta.get("fingerprint")
    if tls_version or cipher or fingerprint:
        lines.append("├─────────────────────────────────────────────┤")
        lines.append("│ Connection Security Details:                 │")
        lines.append("├─────────────────────────────────────────────┤")
        if tls_version:
            lines.append(f"│ TLS Version: {pad_right(tls_version, 30)} │")
        if cipher:
            lines.append(f"│ Cipher Suite: {pad_right(cipher, 29)} │")
        if fingerprint:
            fp_short = f"{fingerprint[:16]}...{fingerprint[-16:]}"
            lines.append(f"│ SHA-256 FP: {pad_right(fp_short, 31)} │")
    lines.append("└─────────────────────────────────────────────┘")
    lines.append("")

    if verbose and sans:
        lines.append("Subject Alternative Names (SANs):")
        lines.append("─" * 45)
        lines.append("\n".join(f"  {san}" for san in sans))
        lines.append("─" * 45)
        lines.append("")

    lines.append("━" * 40)
    return "\n".join(lines)


def _fmt_ping(res: Dict[str, Any], c: dict) -> str:
    meta = res.get("metadata", {})
    target = res.get("target", "")
    success = res.get("success", False)
    lines = []
    lines.append(f"ICMP Ping Test for: {target}")
    lines.append("━" * 40)
    lines.append(f"Target: {meta.get('host', target)}")
    lines.append("")
    packets_sent = meta.get("packets_sent", 4)
    lines.append(f"Sending {packets_sent} ICMP packets...")
    lines.append("")
    ping_output = meta.get("ping_output", "")
    if ping_output:
        lines.append(ping_output)
    else:
        lines.append(f"No ping output captured. Success: {success}")
    lines.append("")
    if success:
        lines.append(f"{c['green']}✅ Ping successful{c['reset']}")
    else:
        lines.append(f"{c['red']}❌ Ping failed (host unreachable or no response){c['reset']}")
    lines.append("━" * 40)
    return "\n".join(lines)


def _fmt_tcp(res: Dict[str, Any], c: dict) -> str:
    meta = res.get("metadata", {})
    target = res.get("target", "")
    success = res.get("success", False)
    error = res.get("error", "")
    latency = res.get("latency_ms")
    lines = []
    lines.append(f"TCP Connection Test for: {target}")
    lines.append("━" * 40)
    lines.append(f"Connecting to {target}...")
    lines.append("")

    status_icon = f"{c['green']}✅ SUCCESS{c['reset']}" if success else f"{c['red']}❌ FAILED{c['reset']}"
    service_name = meta.get("service", "")
    ip_addr = meta.get("ip") or "Unknown"
    host_to_show = target if len(target) <= 37 else target[:34] + "..."

    lines.append("┌─────────────────────────────────────────────┐")
    lines.append(f"│ Host: {pad_right(host_to_show, 37)} │")
    lines.append(f"│ Port: {pad_right(str(meta.get('port', '')), 37)} │")
    if service_name:
        lines.append(f"│ Service: {pad_right(service_name, 34)} │")
    lines.append("├─────────────────────────────────────────────┤")
    lines.append(f"│ Status: {pad_right(status_icon, 35)} │")
    lines.append(f"│ IP Address: {pad_right(ip_addr, 31)} │")
    lines.append(f"│ Latency: {pad_right(f'{latency}ms' if latency is not None else 'N/A', 34)} │")
    if error:
        err_str = str(error) if len(str(error)) <= 35 else str(error)[:32] + "..."
        lines.append(f"│ Reason: {pad_right(err_str, 35)} │")
    lines.append("└─────────────────────────────────────────────┘")
    lines.append("")
    lines.append("━" * 40)
    return "\n".join(lines)


def _fmt_traceroute(res: Dict[str, Any], c: dict) -> str:
    meta = res.get("metadata", {})
    target = res.get("target", "")
    lines = []
    lines.append(f"Traceroute to: {target}")
    lines.append("━" * 40)
    lines.append(f"{'Hop':3} {'IP Address':15} {'Hostname/Details':30} {'Latency'}")
    lines.append("─" * 40)
    for h in meta.get("hops", []):
        hop_num = h.get("hop")
        ip = h.get("ip", "*")
        name = h.get("name", "*")
        latency_ms = f"{h.get('latency_ms')} ms" if h.get("latency_ms") is not None else "*"
        name_str = name if name != ip else ""
        lines.append(f"{hop_num:<3} {pad_right(ip, 15)} {pad_right(name_str, 30)} {latency_ms}")
    lines.append("━" * 40)
    return "\n".join(lines)


def _fmt_scan(res: Dict[str, Any], c: dict) -> str:
    meta = res.get("metadata", {})
    target = res.get("target", "")
    lines = []
    lines.append(f"Port Scan for: {target}")
    lines.append("━" * 40)
    lines.append(f"Scan complete. Resolved IPs: {', '.join(meta.get('ips', []))}")
    lines.append("")
    lines.append(f"📡 {c['bold']}Open Ports:{c['reset']}")
    lines.append("─" * 40)
    open_ports = meta.get("open_ports", [])
    if not open_ports:
        lines.append("  No open ports found.")
    else:
        for p in open_ports:
            service = p.get("service")
            service_str = f"({service})" if service else ""
            lat = f"{p.get('latency_ms')} ms" if p.get("latency_ms") is not None else ""
            lines.append(f"  Port {p.get('port'):<5} - OPEN {service_str:<15} {lat}")
    lines.append("━" * 40)
    return "\n".join(lines)


def _fmt_whois(res: Dict[str, Any], c: dict) -> str:
    meta = res.get("metadata", {})
    target = res.get("target", "")
    lines = []
    lines.append(f"Registration/WHOIS Lookup for: {target}")
    lines.append("━" * 40)
    lines.append(f"Type: {meta.get('type', 'UNKNOWN')}")
    lines.append(f"Source: {meta.get('rdap_source', 'N/A')}")
    if meta.get("registrar"):
        lines.append(f"Registrar/Owner: {meta.get('registrar')}")
    if meta.get("creation_date"):
        lines.append(f"Creation Date: {meta.get('creation_date')}")
    if meta.get("raw_whois"):
        lines.append("")
        lines.append("Raw WHOIS Data (Snippet):")
        lines.append("─" * 40)
        snippet = "\n".join(meta.get("raw_whois", "").splitlines()[:20])
        lines.append(snippet)
        if len(meta.get("raw_whois", "").splitlines()) > 20:
            lines.append("...")
    lines.append("━" * 40)
    return "\n".join(lines)


def _fmt_udp(res: Dict[str, Any], c: dict) -> str:
    meta = res.get("metadata", {})
    target = res.get("target", "")
    success = res.get("success", False)
    error = res.get("error", "")
    latency = res.get("latency_ms")
    lines = []
    lines.append(f"UDP Connectivity Test for: {target}")
    lines.append("━" * 40)
    lines.append(f"Sending UDP probe to {target}...")
    lines.append("")

    status_icon = f"{c['green']}✅ OPEN/FILTERED{c['reset']}" if success else f"{c['red']}❌ CLOSED{c['reset']}"
    service_name = meta.get("service", "")
    ip_addr = meta.get("ip") or "Unknown"
    host_to_show = target if len(target) <= 37 else target[:34] + "..."

    lines.append("┌─────────────────────────────────────────────┐")
    lines.append(f"│ Host: {pad_right(host_to_show, 37)} │")
    lines.append(f"│ Port: {pad_right(str(meta.get('port', '')), 37)} │")
    if service_name:
        lines.append(f"│ Service: {pad_right(service_name, 34)} │")
    lines.append("├─────────────────────────────────────────────┤")
    lines.append(f"│ Status: {pad_right(status_icon, 35)} │")
    lines.append(f"│ IP Address: {pad_right(ip_addr, 31)} │")
    lines.append(f"│ Latency: {pad_right(f'{latency}ms' if latency is not None else 'N/A', 34)} │")
    if error:
        err_str = str(error) if len(str(error)) <= 35 else str(error)[:32] + "..."
        lines.append(f"│ Reason: {pad_right(err_str, 35)} │")
    lines.append("└─────────────────────────────────────────────┘")
    lines.append("")
    lines.append("━" * 40)
    return "\n".join(lines)


def _fmt_mtr(res: Dict[str, Any], c: dict) -> str:
    meta = res.get("metadata", {})
    target = res.get("target", "")
    lines = []
    lines.append(f"MTR Route & Latency report for: {target}")
    lines.append("━" * 80)
    lines.append(f"{'Hop':3} {'IP Address':15} {'Loss%':5} {'Sent':4} {'Recv':4} {'Min':6} {'Avg':6} {'Max':6} {'Hostname'}")
    lines.append("─" * 80)
    for h in meta.get("hops", []):
        hop_num = h.get("hop")
        ip = h.get("ip", "*")
        loss = f"{h.get('loss_pct', 0.0):.1f}%"
        sent = h.get("sent", 0)
        recv = h.get("recv", 0)
        min_ms = f"{h.get('min_ms', 0.0):.1f}" if h.get("min_ms") is not None else "*"
        avg_ms = f"{h.get('avg_ms', 0.0):.1f}" if h.get("avg_ms") is not None else "*"
        max_ms = f"{h.get('max_ms', 0.0):.1f}" if h.get("max_ms") is not None else "*"
        name = h.get("name", "*")
        name_str = name if name != ip else ""
        lines.append(
            f"{hop_num:<3} {pad_right(ip, 15)} {pad_right(loss, 5)} {sent:<4} {recv:<4} "
            f"{pad_right(min_ms, 6)} {pad_right(avg_ms, 6)} {pad_right(max_ms, 6)} {name_str}"
        )
    lines.append("━" * 80)
    return "\n".join(lines)



def _fmt_fallback_single(res: Dict[str, Any], c: dict) -> str:
    """Generic box for any unknown single check type."""
    target = res.get("target", "")
    status = res.get("status", "")
    success = res.get("success", False)
    error = res.get("error", "")
    latency = res.get("latency_ms")
    meta = res.get("metadata", {})

    status_icon = f"{c['green']}✅ SUCCESS{c['reset']}" if success else f"{c['red']}❌ FAILED{c['reset']}"
    if status == "REDIRECT":
        status_icon = f"{c['yellow']}↪ REDIRECT{c['reset']}"

    target_to_show = target if len(target) <= 35 else target[:32] + "..."
    lines = []
    lines.append("┌─────────────────────────────────────────────┐")
    lines.append(f"│ Target: {pad_right(target_to_show, 35)} │")
    lines.append("├─────────────────────────────────────────────┤")
    lines.append(f"│ Status: {pad_right(status_icon, 35)} │")
    if latency is not None:
        lines.append(f"│ Latency: {pad_right(f'{latency}ms', 34)} │")
    if error:
        err_str = str(error) if len(str(error)) <= 35 else str(error)[:32] + "..."
        lines.append(f"│ Reason: {pad_right(err_str, 35)} │")
    for k, v in meta.items():
        val_str = str(v) if len(str(v)) <= 32 else str(v)[:29] + "..."
        lines.append(f"│ {k.capitalize()}: {pad_right(val_str, 45 - len(k) - 2)} │")
    lines.append("└─────────────────────────────────────────────┘")
    return "\n".join(lines)


def _fmt_bulk(results: List[Dict[str, Any]], c: dict) -> str:
    """Tabular summary for multi-target results."""
    lines = []
    lines.append("=" * 80)
    lines.append(f"Network Check Results - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 80)
    lines.append(f"{'Status':12} {'Target':30} {'Latency':10} {'Details'}")
    lines.append("-" * 80)

    successes = 0
    failures = 0

    for r in results:
        target = r.get("target", "")
        status = r.get("status", "")
        success = r.get("success", False)
        latency = f"{r.get('latency_ms', '')}ms" if r.get("latency_ms") is not None else "N/A"
        details = r.get("error", "") or ""

        if success:
            successes += 1
            status_str = f"{c['green']}✅ SUCCESS{c['reset']}"
        else:
            failures += 1
            status_str = f"{c['red']}❌ FAILED{c['reset']}"

        if status == "REDIRECT":
            status_str = f"{c['yellow']}↪  REDIRECT{c['reset']}"
        elif status in ("OPEN_OR_FILTERED",):
            status_str = f"{c['green']}✅ OPEN/FLTRD{c['reset']}"
            if not success:
                status_str = f"{c['red']}❌ CLOSED{c['reset']}"

        meta = r.get("metadata", {})
        if "status_code" in meta:
            details = f"HTTP {meta['status_code']}" + (f" -> {meta['redirect_url']}" if meta.get("redirect_url") else "")
        elif "days_until_expiry" in meta:
            details = f"SSL expires in {meta['days_until_expiry']} days"
        elif "port" in meta and "valid_until" not in meta:
            service_str = f" ({meta['service']})" if meta.get("service") else ""
            details = f"TCP port {meta['port']}{service_str}" + (f" - IP: {meta['ip']}" if meta.get("ip") else "")
        elif "ips" in meta:
            details = f"IPs: {', '.join(meta['ips'][:3])}"

        lines.append(f"{pad_right(status_str, 12)} {pad_right(target, 30)} {pad_right(latency, 10)} {details}")

    lines.append("=" * 80)
    lines.append("Check Complete!")
    latencies = [r["latency_ms"] for r in results if r.get("success", False) and r.get("latency_ms") is not None]
    avg_latency = f"{sum(latencies)/len(latencies):.2f}ms" if latencies else "N/A"
    lines.append(f"Total: {len(results)}  |  Successful: {successes}  |  Failed: {failures}  |  Avg Latency: {avg_latency}")
    lines.append("=" * 80)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_SINGLE_DISPATCH = {
    "interfaces": lambda res, c, v: _fmt_interfaces(res, c),
    "ports":      lambda res, c, v: _fmt_ports(res, c),
    "dns":        lambda res, c, v: _fmt_dns(res, c),
    "http":       lambda res, c, v: _fmt_http(res, c, v),
    "ssl":        lambda res, c, v: _fmt_ssl(res, c, v),
    "ping":       lambda res, c, v: _fmt_ping(res, c),
    "tcp":        lambda res, c, v: _fmt_tcp(res, c),
    "traceroute": lambda res, c, v: _fmt_traceroute(res, c),
    "scan":       lambda res, c, v: _fmt_scan(res, c),
    "whois":      lambda res, c, v: _fmt_whois(res, c),
    "udp":        lambda res, c, v: _fmt_udp(res, c),
    "mtr":        lambda res, c, v: _fmt_mtr(res, c),
}


def format_text(
    results: List[Dict[str, Any]],
    verbose: bool = False,
    use_color: Optional[bool] = None,
) -> str:
    """Format a list of check results to a human-readable terminal string."""
    if use_color is None:
        use_color = sys.stdout.isatty()
    c = get_colors(use_color)

    if len(results) == 1:
        res = results[0]
        res_type = detect_result_type(res)
        fmt_fn = _SINGLE_DISPATCH.get(res_type)
        if fmt_fn:
            return fmt_fn(res, c, verbose)
        return _fmt_fallback_single(res, c)

    return _fmt_bulk(results, c)
