"""
Unit tests for netcheck.modules.ssl
"""
import pytest
from unittest.mock import patch, MagicMock
from netcheck.modules.ssl import check_ssl_certificate


class TestSSLCertificate:
    @patch("socket.socket")
    @patch("netcheck.modules.ssl.dns_lookup")
    def test_ssl_cipher_extraction(self, mock_dns, mock_socket):
        mock_dns.return_value = {
            "success": True,
            "metadata": {"ips": ["93.184.216.34"]}
        }
        mock_sock_instance = MagicMock()
        mock_socket.return_value = mock_sock_instance

        mock_ssock = MagicMock()
        mock_ssock.getpeercert.return_value = {
            "subject": [[("commonName", "example.com")]],
            "issuer": [[("organizationName", "DigiCert")]],
            "notBefore": "Jan 01 00:00:00 2026 GMT",
            "notAfter": "Dec 31 23:59:59 2026 GMT",
        }
        mock_ssock.cipher.return_value = ("ECDHE-RSA-AES256-GCM-SHA384", "TLSv1.3", 256)
        mock_ssock.version.return_value = "TLSv1.3"

        with patch("ssl.create_default_context") as mock_create_context:
            mock_context = MagicMock()
            mock_context.wrap_socket.return_value.__enter__.return_value = mock_ssock
            mock_create_context.return_value = mock_context

            res = check_ssl_certificate("example.com")

        assert res["success"] is True
        assert res["metadata"]["cipher"] == "ECDHE-RSA-AES256-GCM-SHA384"
        assert res["metadata"]["tls_version"] == "TLSv1.3"
