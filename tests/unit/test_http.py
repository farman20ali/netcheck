"""
Unit tests for netcheck.modules.http
"""
import urllib.request
import urllib.error
import pytest
from unittest.mock import patch, MagicMock
from netcheck.modules.http import check_http_status


class TestHTTPStatus:
    @patch("urllib.request.urlopen")
    def test_http_status_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.geturl.return_value = "http://example.com"
        mock_resp.info.return_value = {"Content-Length": "100"}
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        res = check_http_status("http://example.com")
        assert res["success"] is True
        assert res["metadata"]["status_code"] == 200

    @patch("urllib.request.urlopen")
    def test_http_status_failure(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "http://example.com", 404, "Not Found", {}, None
        )
        res = check_http_status("http://example.com")
        assert res["success"] is False
        assert res["metadata"]["status_code"] == 404

    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_http_custom_request(self, mock_request_class, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.geturl.return_value = "http://example.com"
        mock_resp.info.return_value = {"Content-Length": "10"}
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        check_http_status(
            "http://example.com",
            method="POST",
            headers={"X-Custom-Header": "Test"},
            auth=("user", "pass")
        )
        mock_request_class.assert_called_once()
        args, kwargs = mock_request_class.call_args
        assert kwargs["method"] == "POST"
        headers = kwargs["headers"]
        assert headers["X-Custom-Header"] == "Test"
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
