"""
Unit tests for json_fmt
"""
import json
from netcheck.utils.formatters import format_json


def test_json_interfaces_format(interfaces_result):
    out = json.loads(format_json([interfaces_result]))
    assert out["type"] == "interfaces"
    assert out["primary_ip"] == "192.168.1.5"


def test_json_dns_format(dns_result):
    out = json.loads(format_json([dns_result]))
    assert out["type"] == "dns"
    assert out["target"] == "google.com"
    assert out["resolved_host"] == "google.com"


def test_json_http_format(http_result):
    out = json.loads(format_json([http_result]))
    assert out["type"] == "http"
    assert out["status_code"] == 200


def test_json_ssl_format(ssl_result):
    out = json.loads(format_json([ssl_result]))
    assert out["type"] == "ssl"
    assert out["days_until_expiry"] == 200


def test_json_ping_format(ping_result):
    out = json.loads(format_json([ping_result]))
    assert out["type"] == "ping"
    assert out["packet_loss_pct"] == 0.0


def test_json_ports_format(ports_result):
    out = json.loads(format_json([ports_result]))
    assert out["type"] == "ports"
    assert len(out["listening_ports"]) == 2


def test_json_scan_format(scan_result):
    out = json.loads(format_json([scan_result]))
    assert out["type"] == "scan"
    assert out["open_ports"][0]["port"] == 80


def test_json_traceroute_format(traceroute_result):
    out = json.loads(format_json([traceroute_result]))
    assert out["type"] == "traceroute"
    assert len(out["hops"]) == 2


def test_json_whois_format(whois_result):
    out = json.loads(format_json([whois_result]))
    assert out["check_type"] == "whois"
    assert out["registrar"] == "MarkMonitor Inc."
