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


def test_json_udp_format():
    udp_result = {
        "type": "udp",
        "target": "8.8.8.8:53",
        "status": "OPEN",
        "latency_ms": 12.3,
        "success": True,
        "error": None,
        "metadata": {"port": 53, "service": "domain"},
    }
    out = json.loads(format_json([udp_result]))
    assert out["type"] == "udp"
    assert out["target"] == "8.8.8.8:53"
    assert out["status"] == "OPEN"
    assert out["service"] == "domain"


def test_json_mtr_format():
    mtr_result = {
        "type": "mtr",
        "target": "example.com",
        "status": "SUCCESS",
        "latency_ms": 25.4,
        "success": True,
        "error": None,
        "metadata": {
            "host": "example.com",
            "hops": [
                {"hop": 1, "ip": "192.168.1.1", "name": "router", "loss_pct": 0.0,
                 "sent": 3, "recv": 3, "min_ms": 1.0, "avg_ms": 1.2, "max_ms": 1.5}
            ],
        },
    }
    out = json.loads(format_json([mtr_result]))
    assert out["type"] == "mtr"
    assert out["target"] == "example.com"
    assert len(out["hops"]) == 1
    assert out["hops"][0]["ip"] == "192.168.1.1"
