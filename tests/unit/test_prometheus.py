"""
tests/unit/test_prometheus.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for netcheck.utils.prometheus.MetricsRegistry and MetricsServer
"""

from __future__ import annotations

import time
import urllib.request

import pytest

from netcheck.utils.prometheus import MetricsRegistry, MetricsServer, _label, _escape


# ===========================================================================
# MetricsRegistry
# ===========================================================================

class TestMetricsRegistry:
    @pytest.fixture(autouse=True)
    def registry(self):
        r = MetricsRegistry()
        yield r
        r.reset()

    # ── record() ──────────────────────────────────────────────────────────

    def test_record_success_increments_total(self, registry):
        registry.record("google.com:443", "tcp", success=True)
        snap = registry.snapshot()
        assert snap[("google.com:443", "tcp")]["total"] == 1

    def test_record_failure_increments_failures(self, registry):
        registry.record("google.com:443", "tcp", success=False)
        snap = registry.snapshot()
        assert snap[("google.com:443", "tcp")]["failures"] == 1

    def test_record_success_does_not_increment_failures(self, registry):
        registry.record("google.com:443", "tcp", success=True)
        snap = registry.snapshot()
        assert snap[("google.com:443", "tcp")]["failures"] == 0

    def test_record_multiple_calls_accumulate(self, registry):
        for _ in range(5):
            registry.record("h:80", "tcp", success=True)
        registry.record("h:80", "tcp", success=False)
        snap = registry.snapshot()
        assert snap[("h:80", "tcp")]["total"] == 6
        assert snap[("h:80", "tcp")]["failures"] == 1

    def test_record_stores_latency(self, registry):
        registry.record("h:443", "tcp", success=True, latency_ms=42.0)
        snap = registry.snapshot()
        assert snap[("h:443", "tcp")]["last_latency_ms"] == pytest.approx(42.0)

    def test_record_last_latency_overwrites(self, registry):
        registry.record("h:443", "tcp", success=True, latency_ms=10.0)
        registry.record("h:443", "tcp", success=True, latency_ms=20.0)
        snap = registry.snapshot()
        assert snap[("h:443", "tcp")]["last_latency_ms"] == pytest.approx(20.0)

    def test_record_no_latency_stores_none(self, registry):
        registry.record("h:443", "tcp", success=True)
        snap = registry.snapshot()
        assert snap[("h:443", "tcp")]["last_latency_ms"] is None

    def test_different_targets_are_separate(self, registry):
        registry.record("a:80", "tcp", success=True)
        registry.record("b:80", "tcp", success=False)
        snap = registry.snapshot()
        assert snap[("a:80", "tcp")]["failures"] == 0
        assert snap[("b:80", "tcp")]["failures"] == 1

    def test_different_check_types_are_separate(self, registry):
        registry.record("h:443", "tcp", success=True)
        registry.record("h:443", "ssl", success=False)
        snap = registry.snapshot()
        assert snap[("h:443", "tcp")]["failures"] == 0
        assert snap[("h:443", "ssl")]["failures"] == 1

    # ── render() ──────────────────────────────────────────────────────────

    def test_render_returns_string(self, registry):
        assert isinstance(registry.render(), str)

    def test_render_contains_required_metric_names(self, registry):
        registry.record("h:80", "tcp", success=True, latency_ms=5.0)
        text = registry.render()
        for name in (
            "netcheck_check_total",
            "netcheck_check_failures_total",
            "netcheck_latency_seconds",
            "netcheck_up",
            "netcheck_uptime_ratio",
            "netcheck_scrape_count",
        ):
            assert name in text, f"Missing metric: {name}"

    def test_render_contains_help_lines(self, registry):
        text = registry.render()
        assert "# HELP" in text
        assert "# TYPE" in text

    def test_render_up_gauge_1_on_success(self, registry):
        registry.record("h:80", "tcp", success=True)
        text = registry.render()
        assert 'netcheck_up{target="h:80"} 1' in text

    def test_render_up_gauge_0_on_failure(self, registry):
        registry.record("h:80", "tcp", success=False)
        text = registry.render()
        assert 'netcheck_up{target="h:80"} 0' in text

    def test_render_latency_seconds_is_ms_divided_by_1000(self, registry):
        registry.record("h:443", "tcp", success=True, latency_ms=500.0)
        text = registry.render()
        assert "0.500000" in text

    def test_render_scrape_count_increments(self, registry):
        registry.render()
        registry.render()
        text = registry.render()
        assert "netcheck_scrape_count 3" in text

    def test_render_uptime_ratio_100_percent(self, registry):
        registry.record("h:80", "tcp", success=True)
        registry.record("h:80", "tcp", success=True)
        text = registry.render()
        assert "netcheck_uptime_ratio" in text
        assert "1.0000" in text

    def test_render_uptime_ratio_50_percent(self, registry):
        registry.record("h:80", "tcp", success=True)
        registry.record("h:80", "tcp", success=False)
        text = registry.render()
        assert "0.5000" in text

    def test_render_no_latency_line_when_none(self, registry):
        """latency metric should only appear if latency was recorded."""
        registry.record("h:80", "tcp", success=True)  # no latency_ms
        text = registry.render()
        # latency lines only appear for entries with last_latency_ms
        latency_lines = [
            ln for ln in text.splitlines() if ln.startswith("netcheck_latency_seconds{")
        ]
        assert len(latency_lines) == 0

    # ── reset() ───────────────────────────────────────────────────────────

    def test_reset_clears_all(self, registry):
        registry.record("h:80", "tcp", success=True)
        registry.reset()
        assert registry.snapshot() == {}

    def test_reset_clears_scrape_count(self, registry):
        registry.render()
        registry.reset()
        text = registry.render()
        assert "netcheck_scrape_count 1" in text  # first scrape after reset


# ===========================================================================
# Label helpers
# ===========================================================================

class TestLabelHelpers:
    def test_label_single_kv(self):
        assert _label(target="h:80") == '{target="h:80"}'

    def test_label_multiple_kv(self):
        result = _label(target="h:80", check_type="tcp")
        assert 'target="h:80"' in result
        assert 'check_type="tcp"' in result

    def test_escape_quotes(self):
        assert _escape('"hello"') == '\\"hello\\"'

    def test_escape_backslash(self):
        assert _escape("a\\b") == "a\\\\b"

    def test_escape_newline(self):
        assert _escape("a\nb") == "a\\nb"


# ===========================================================================
# MetricsServer
# ===========================================================================

class TestMetricsServer:
    def test_server_starts_and_is_running(self):
        registry = MetricsRegistry()
        server = MetricsServer(registry, host="127.0.0.1", port=19090)
        try:
            server.start()
            assert server.is_running
        finally:
            server.stop()

    def test_server_is_not_running_after_stop(self):
        registry = MetricsRegistry()
        server = MetricsServer(registry, host="127.0.0.1", port=19091)
        server.start()
        server.stop()
        assert not server.is_running

    def test_server_serves_metrics_endpoint(self):
        registry = MetricsRegistry()
        registry.record("test:80", "tcp", success=True, latency_ms=1.0)
        server = MetricsServer(registry, host="127.0.0.1", port=19092)
        try:
            server.start()
            time.sleep(0.1)  # let the thread start
            with urllib.request.urlopen("http://127.0.0.1:19092/metrics", timeout=3) as resp:
                body = resp.read().decode("utf-8")
            assert "netcheck_check_total" in body
            assert 'target="test:80"' in body
        finally:
            server.stop()

    def test_server_404_on_unknown_path(self):
        registry = MetricsRegistry()
        server = MetricsServer(registry, host="127.0.0.1", port=19093)
        try:
            server.start()
            time.sleep(0.1)
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen("http://127.0.0.1:19093/unknown", timeout=3)
            assert exc_info.value.code == 404
        finally:
            server.stop()

    def test_server_url_property(self):
        registry = MetricsRegistry()
        server = MetricsServer(registry, host="0.0.0.0", port=9090)
        assert server.url() == "http://0.0.0.0:9090/metrics"
