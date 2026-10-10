"""
Unit tests for netcheck.modules.whois
"""
import pytest
from unittest.mock import patch
from netcheck.modules.whois import lookup_registration


class TestWhoisRdapSuccess:
    @patch("netcheck.modules.whois.get_rdap_info")
    def test_whois_rdap_success(self, mock_rdap):
        mock_rdap.return_value = {
            "entities": [
                {
                    "roles": ["registrar"],
                    "vcardArray": [
                        "vcard",
                        [
                            ["version", {}, "text", "4.0"],
                            ["fn", {}, "text", "GoDaddy.com, LLC"]
                        ]
                    ]
                }
            ],
            "events": [
                {"eventAction": "registration", "eventDate": "1999-10-11T11:00:00Z"}
            ]
        }

        res = lookup_registration("google.com")
        assert res["success"] is True
        assert res["metadata"]["registrar"] == "GoDaddy.com, LLC"
        assert res["metadata"]["creation_date"] == "1999-10-11T11:00:00Z"
