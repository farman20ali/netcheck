"""
Unit tests for xml_fmt
"""
import xml.etree.ElementTree as ET
from netcheck.utils.formatters import format_xml


def test_xml_interfaces_format(interfaces_result):
    xml_out = format_xml([interfaces_result])
    root = ET.fromstring(xml_out)
    assert root.tag == "network_interfaces"
    assert root.find("primary_ip").text == "192.168.1.5"


def test_xml_dns_format(dns_result):
    xml_out = format_xml([dns_result])
    root = ET.fromstring(xml_out)
    assert root.tag == "dns_lookup"
    assert root.find("resolved_host").text == "google.com"


def test_xml_http_format(http_result):
    xml_out = format_xml([http_result])
    root = ET.fromstring(xml_out)
    assert root.tag == "http_check"
    assert root.find("status_code").text == "200"


def test_xml_ssl_format(ssl_result):
    xml_out = format_xml([ssl_result])
    root = ET.fromstring(xml_out)
    assert root.tag == "ssl_check"
    assert root.find("subject_cn").text == "google.com"


def test_xml_ping_format(ping_result):
    xml_out = format_xml([ping_result])
    root = ET.fromstring(xml_out)
    assert root.tag == "ping_check"
    assert root.find("packet_loss_pct").text == "0.0"


def test_xml_ports_format(ports_result):
    xml_out = format_xml([ports_result])
    root = ET.fromstring(xml_out)
    assert root.tag == "listening_ports"
    ports = root.findall("port")
    assert len(ports) == 2
    assert ports[0].attrib["process"] == "sshd"


def test_xml_scan_format(scan_result):
    xml_out = format_xml([scan_result])
    root = ET.fromstring(xml_out)
    assert root.tag == "port_scan"
    open_ports = root.find("open_ports")
    assert open_ports is not None
    assert open_ports.find("port").attrib["number"] == "80"


def test_xml_traceroute_format(traceroute_result):
    xml_out = format_xml([traceroute_result])
    root = ET.fromstring(xml_out)
    assert root.tag == "traceroute"
    hops = root.findall("hop")
    assert len(hops) == 2
    assert hops[0].attrib["ip"] == "192.168.1.1"


def test_xml_whois_format(whois_result):
    xml_out = format_xml([whois_result])
    root = ET.fromstring(xml_out)
    assert root.tag == "whois_lookup"
    assert root.find("registrar").text == "MarkMonitor Inc."
