"""
Unit tests for netcheck.utils.banners: pure-Python banner grabbing and service detection.
"""
from unittest.mock import patch

from netcheck.utils.banners import (
    _probe_http,
    _probe_mysql,
    _probe_read_greeting,
    _probe_redis,
    _probe_ssh,
    grab_banner,
)
from netcheck.utils.services import get_top_ports


def test_top_ports_retrieval():
    ports_10 = get_top_ports(10)
    assert len(ports_10) == 10
    assert 22 in ports_10 or 53 in ports_10

    ports_100 = get_top_ports(100)
    assert len(ports_100) == 100

    ports_500 = get_top_ports(500)
    assert len(ports_500) == 500

    # Cap at 1000
    ports_2000 = get_top_ports(2000)
    assert len(ports_2000) == 1000


@patch("socket.socket")
def test_probe_ssh(mock_sock_cls):
    mock_sock = mock_sock_cls.return_value.__enter__.return_value
    mock_sock.recv.return_value = b"SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.6\r\n"

    info = _probe_ssh("127.0.0.1", 22, timeout=1.0)
    assert info is not None
    assert info["detected_service"] == "ssh"
    assert info["version"] == "OpenSSH_8.9p1"
    assert "OpenSSH_8.9p1" in info["banner"]


@patch("socket.socket")
def test_probe_http(mock_sock_cls):
    mock_sock = mock_sock_cls.return_value
    mock_sock.recv.return_value = b"HTTP/1.1 200 OK\r\nServer: nginx/1.24.0\r\nContent-Type: text/html\r\n\r\n"

    info = _probe_http("127.0.0.1", 80, timeout=1.0, use_ssl=False)
    assert info is not None
    assert info["detected_service"] == "http"
    assert info["version"] == "nginx/1.24.0"
    assert "Server: nginx/1.24.0" in info["banner"]


@patch("socket.socket")
def test_probe_read_greeting_ftp(mock_sock_cls):
    mock_sock = mock_sock_cls.return_value.__enter__.return_value
    mock_sock.recv.return_value = b"220 (vsFTPd 3.0.5)\r\n"

    info = _probe_read_greeting("127.0.0.1", 21, timeout=1.0, service="ftp")
    assert info is not None
    assert info["detected_service"] == "ftp"
    assert "vsFTPd" in info["banner"]


@patch("socket.socket")
def test_probe_redis(mock_sock_cls):
    mock_sock = mock_sock_cls.return_value.__enter__.return_value
    mock_sock.recv.return_value = b"+PONG\r\n"

    info = _probe_redis("127.0.0.1", 6379, timeout=1.0)
    assert info is not None
    assert info["detected_service"] == "redis"
    assert "Redis" in info["banner"]


@patch("socket.socket")
def test_probe_mysql(mock_sock_cls):
    mock_sock = mock_sock_cls.return_value.__enter__.return_value
    # Packet: 3 bytes length, 1 byte seq, 1 byte protocol (10), version string null-terminated
    mock_sock.recv.return_value = b"\x4a\x00\x00\x00\x0a8.0.35\x00extra_salt_data"

    info = _probe_mysql("127.0.0.1", 3306, timeout=1.0)
    assert info is not None
    assert info["detected_service"] == "mysql"
    assert info["version"] == "8.0.35"


@patch("socket.socket")
def test_grab_banner_dispatcher(mock_sock_cls):
    mock_sock = mock_sock_cls.return_value.__enter__.return_value
    mock_sock.recv.return_value = b"SSH-2.0-OpenSSH_9.0\r\n"

    res = grab_banner("127.0.0.1", 22, timeout=1.0)
    assert res["detected_service"] == "ssh"
    assert res["version"] == "OpenSSH_9.0"
