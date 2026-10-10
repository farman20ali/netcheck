"""
Unit tests for netcheck.cli.batch
"""
from netcheck.cli.batch import parse_csv_content, parse_batch_content


def test_parse_csv_content_valid():
    content = "host,port\ngoogle.com,80\n1.1.1.1,443"
    targets = parse_csv_content(content)
    assert targets == [("google.com", "80"), ("1.1.1.1", "443")]


def test_parse_batch_content_mixed():
    content = """
    # comment
    google.com:80
    http://example.com/path
    [fe80::1]:443
    """
    targets = parse_batch_content(content)
    assert ("google.com", "80") in targets
    assert ("example.com", "80") in targets or ("example.com", "443") in targets
    assert ("fe80::1", "443") in targets
