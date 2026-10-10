"""
Unit tests for csv_fmt
"""
import csv
import io
from netcheck.utils.formatters import format_csv


def test_csv_interfaces_format(interfaces_result):
    csv_out = format_csv([interfaces_result])
    rows = list(csv.reader(io.StringIO(csv_out)))
    assert rows[0] == ["Interface", "IPv4", "IPv6", "Status", "Default_Gateway", "Public_IP"]
    assert rows[1][0] == "eth0"


def test_csv_dns_format(dns_result):
    csv_out = format_csv([dns_result])
    rows = list(csv.reader(io.StringIO(csv_out)))
    assert rows[0] == ["Target", "Resolved_Host", "IP", "Reverse_DNS", "Success", "Latency_MS", "Error"]
    assert rows[1][1] == "google.com"


def test_csv_http_format(http_result):
    csv_out = format_csv([http_result])
    rows = list(csv.reader(io.StringIO(csv_out)))
    assert rows[0] == ["Target", "Status_Code", "Redirect_URL", "Size_Bytes", "Success", "Latency_MS", "Error"]
    assert rows[1][1] == "200"


def test_csv_ssl_format(ssl_result):
    csv_out = format_csv([ssl_result])
    rows = list(csv.reader(io.StringIO(csv_out)))
    assert rows[0] == ["Target", "Subject_CN", "Issuer_O", "Valid_From", "Valid_Until", "Days_Until_Expiry", "Expired", "Success", "Latency_MS", "Error"]
    assert rows[1][1] == "google.com"
    assert rows[1][2] == "Google Trust Services"


def test_csv_ping_format(ping_result):
    csv_out = format_csv([ping_result])
    rows = list(csv.reader(io.StringIO(csv_out)))
    assert rows[0] == ["Target", "Host", "Packets_Sent", "Packets_Received", "Packet_Loss_Pct", "Min_RTT_MS", "Avg_RTT_MS", "Max_RTT_MS", "Success", "Latency_MS", "Error"]
    assert rows[1][4] == "0.0"


def test_csv_ports_format(ports_result):
    csv_out = format_csv([ports_result])
    rows = list(csv.reader(io.StringIO(csv_out)))
    assert rows[0] == ["Proto", "Address", "Port", "Process", "PID"]
    assert rows[1][3] == "sshd"


def test_csv_scan_format(scan_result):
    csv_out = format_csv([scan_result])
    rows = list(csv.reader(io.StringIO(csv_out)))
    assert rows[0] == ["Target", "Port", "Status", "Service", "Latency_MS"]
    open_row = next(r for r in rows[1:] if r[2] == "OPEN")
    assert open_row[1] == "80"
    assert open_row[3] == "http"


def test_csv_traceroute_format(traceroute_result):
    csv_out = format_csv([traceroute_result])
    rows = list(csv.reader(io.StringIO(csv_out)))
    assert rows[0] == ["Target", "Hop", "IP", "Hostname", "Latency_MS"]
    assert rows[1][2] == "192.168.1.1"


def test_csv_whois_format(whois_result):
    csv_out = format_csv([whois_result])
    rows = list(csv.reader(io.StringIO(csv_out)))
    assert rows[0] == ["Target", "Type", "Source", "Registrar", "Creation_Date", "Success", "Error"]
    assert rows[1][3] == "MarkMonitor Inc."
