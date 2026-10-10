"""
XML formatter for all NetCheck check types.
"""
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List

from netcheck.utils.formatters.base import detect_result_type

_XML_DECL = '<?xml version="1.0" encoding="UTF-8"?>\n'


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _to_xml_str(root: ET.Element) -> str:
    return _XML_DECL + ET.tostring(root, encoding="utf-8").decode("utf-8")


def _fmt_interfaces(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    root = ET.Element("network_interfaces", date=_now())
    ET.SubElement(root, "primary_ip").text = meta.get("primary_ip", "")
    ET.SubElement(root, "gateway_ip").text = meta.get("gateway_ip", "")
    ET.SubElement(root, "gateway_dev").text = meta.get("gateway_dev", "")
    ET.SubElement(root, "public_ip").text = meta.get("public_ip", "")
    ifaces_elem = ET.SubElement(root, "interfaces")
    for name, iface in sorted(meta.get("interfaces", {}).items()):
        ie = ET.SubElement(ifaces_elem, "interface", name=name, status=iface.get("status", ""))
        ipv4_e = ET.SubElement(ie, "ipv4_addresses")
        for ip in iface.get("ipv4", []):
            ET.SubElement(ipv4_e, "ip").text = ip
        ipv6_e = ET.SubElement(ie, "ipv6_addresses")
        for ip in iface.get("ipv6", []):
            ET.SubElement(ipv6_e, "ip").text = ip
    return _to_xml_str(root)


def _fmt_dns(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    root = ET.Element("dns_lookup", date=_now(),
                      target=res.get("target", ""),
                      success=str(res.get("success", False)).lower())
    ET.SubElement(root, "resolved_host").text = meta.get("resolved_host", "")
    ips_e = ET.SubElement(root, "ip_addresses")
    for ip in meta.get("ips", []):
        ET.SubElement(ips_e, "ip").text = ip
    aliases_e = ET.SubElement(root, "aliases")
    for alias in meta.get("aliases", []):
        ET.SubElement(aliases_e, "alias").text = alias
    ET.SubElement(root, "reverse_dns").text = meta.get("reverse_dns", "") or ""
    if res.get("latency_ms") is not None:
        ET.SubElement(root, "latency_ms").text = str(res.get("latency_ms"))
    if res.get("error"):
        ET.SubElement(root, "error").text = res.get("error")
    return _to_xml_str(root)


def _fmt_http(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    root = ET.Element("http_check", date=_now(),
                      target=res.get("target", ""),
                      success=str(res.get("success", False)).lower())
    ET.SubElement(root, "status_code").text = str(meta.get("status_code") or "")
    ET.SubElement(root, "redirect_url").text = meta.get("redirect_url") or ""
    ET.SubElement(root, "size_bytes").text = str(meta.get("size_bytes", 0))
    if res.get("latency_ms") is not None:
        ET.SubElement(root, "latency_ms").text = str(res.get("latency_ms"))
    if res.get("error"):
        ET.SubElement(root, "error").text = res.get("error")
    headers_e = ET.SubElement(root, "headers")
    for k, v in sorted(meta.get("headers", {}).items()):
        ET.SubElement(headers_e, "header", name=k).text = str(v)
    return _to_xml_str(root)


def _fmt_ssl(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    root = ET.Element("ssl_check", date=_now(),
                      target=res.get("target", ""),
                      success=str(res.get("success", False)).lower())
    ET.SubElement(root, "subject_cn").text = meta.get("subject", {}).get("commonName", "")
    ET.SubElement(root, "issuer_o").text = meta.get("issuer", {}).get("organizationName", "")
    ET.SubElement(root, "valid_from").text = meta.get("valid_from") or ""
    ET.SubElement(root, "valid_until").text = meta.get("valid_until") or ""
    dexp = meta.get("days_until_expiry")
    ET.SubElement(root, "days_until_expiry").text = str(dexp) if dexp is not None else ""
    ET.SubElement(root, "expired").text = str(meta.get("expired", False)).lower()
    if res.get("latency_ms") is not None:
        ET.SubElement(root, "latency_ms").text = str(res.get("latency_ms"))
    if res.get("error"):
        ET.SubElement(root, "error").text = res.get("error")
    sans_e = ET.SubElement(root, "sans")
    for san in meta.get("sans", []):
        ET.SubElement(sans_e, "san").text = san
    return _to_xml_str(root)


def _fmt_ping(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    root = ET.Element("ping_check", date=_now(),
                      target=res.get("target", ""),
                      success=str(res.get("success", False)).lower())
    ET.SubElement(root, "host").text = meta.get("host", "")
    ET.SubElement(root, "packets_sent").text = str(meta.get("packets_sent", 0))
    ET.SubElement(root, "packets_received").text = str(meta.get("packets_received", 0))
    ET.SubElement(root, "packet_loss_pct").text = str(meta.get("packet_loss_pct", 0.0))
    ET.SubElement(root, "min_rtt_ms").text = str(meta.get("min_rtt_ms") or "")
    ET.SubElement(root, "avg_rtt_ms").text = str(meta.get("avg_rtt_ms") or "")
    ET.SubElement(root, "max_rtt_ms").text = str(meta.get("max_rtt_ms") or "")
    if res.get("latency_ms") is not None:
        ET.SubElement(root, "latency_ms").text = str(res.get("latency_ms"))
    if res.get("error"):
        ET.SubElement(root, "error").text = res.get("error")
    return _to_xml_str(root)


def _fmt_ports(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    root = ET.Element("listening_ports", date=_now(),
                      success=str(res.get("success", False)).lower())
    for p in meta.get("listening_ports", []):
        ET.SubElement(root, "port",
                      proto=str(p.get("proto", "TCP")),
                      address=str(p.get("address", "*")),
                      port=str(p.get("port", "")),
                      process=str(p.get("process", "")),
                      pid=str(p.get("pid", "")))
    return _to_xml_str(root)


def _fmt_scan(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    root = ET.Element("port_scan", date=_now(),
                      target=str(res.get("target", "")),
                      success=str(res.get("success", False)).lower())
    ips_e = ET.SubElement(root, "resolved_ips")
    for ip in meta.get("ips", []):
        ET.SubElement(ips_e, "ip").text = ip
    open_e = ET.SubElement(root, "open_ports")
    for p in meta.get("open_ports", []):
        ET.SubElement(open_e, "port",
                      number=str(p.get("port", "")),
                      service=str(p.get("service", "")),
                      latency_ms=str(p.get("latency_ms", "")))
    return _to_xml_str(root)


def _fmt_traceroute(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    root = ET.Element("traceroute", date=_now(),
                      target=str(res.get("target", "")),
                      success=str(res.get("success", False)).lower())
    for h in meta.get("hops", []):
        ET.SubElement(root, "hop",
                      number=str(h.get("hop", "")),
                      ip=str(h.get("ip", "*")),
                      name=str(h.get("name", "*")),
                      latency_ms=str(h.get("latency_ms", "")))
    return _to_xml_str(root)


def _fmt_whois(res: Dict[str, Any]) -> str:
    meta = res.get("metadata", {})
    root = ET.Element("whois_lookup", date=_now(),
                      target=str(res.get("target", "")),
                      success=str(res.get("success", False)).lower())
    ET.SubElement(root, "type").text = meta.get("type", "")
    ET.SubElement(root, "rdap_source").text = meta.get("rdap_source", "")
    ET.SubElement(root, "registrar").text = meta.get("registrar", "") or ""
    ET.SubElement(root, "creation_date").text = meta.get("creation_date", "") or ""
    if res.get("error"):
        ET.SubElement(root, "error").text = res.get("error")
    return _to_xml_str(root)


def _fmt_tcp_batch(results: List[Dict[str, Any]]) -> str:
    ts = _now()
    root = ET.Element("connectivity_check", date=ts)
    all_success = all(r.get("success", False) for r in results)
    all_fail = all(not r.get("success", False) for r in results)
    if all_success and results:
        container = ET.SubElement(root, "successful_connections")
    elif all_fail and results:
        container = ET.SubElement(root, "failed_connections")
    else:
        container = ET.SubElement(root, "all_results")
    for r in results:
        host = r.get("metadata", {}).get("host", r.get("target", "").split(":")[0])
        port = str(r.get("metadata", {}).get("port", r.get("target", "").split(":")[-1]))
        if r.get("success", False):
            ET.SubElement(container, "connection", host=host, port=port,
                          method=r.get("metadata", {}).get("method", "socket"), timestamp=ts)
        else:
            ET.SubElement(container, "connection", host=host, port=port,
                          reason=r.get("error", "timeout") or "timeout", timestamp=ts)
    return _to_xml_str(root)


_SINGLE_DISPATCH = {
    "interfaces": _fmt_interfaces, "dns": _fmt_dns, "http": _fmt_http,
    "ssl": _fmt_ssl, "ping": _fmt_ping, "ports": _fmt_ports,
    "scan": _fmt_scan, "traceroute": _fmt_traceroute, "whois": _fmt_whois,
}


def format_xml(results: List[Dict[str, Any]]) -> str:
    """Format a list of check results to XML string."""
    if not results:
        return _XML_DECL + "<results/>"
    if len(results) == 1:
        res = results[0]
        res_type = detect_result_type(res)
        fmt_fn = _SINGLE_DISPATCH.get(res_type)
        if fmt_fn:
            return fmt_fn(res)
    return _fmt_tcp_batch(results)
