"""
netcheck.utils.prometheus
~~~~~~~~~~~~~~~~~~~~~~~~~

Prometheus metrics exporter for netcheck.

Exposes an HTTP endpoint (default: http://0.0.0.0:9090/metrics) that
serves metrics in the Prometheus text exposition format (no external
dependencies — stdlib only).

Metrics exposed:
  netcheck_check_total{target, check_type}           Counter
  netcheck_check_failures_total{target, check_type}  Counter
  netcheck_latency_seconds{target, check_type}       Gauge (last value)
  netcheck_up{target}                                Gauge (1=UP, 0=DOWN)
  netcheck_uptime_ratio{target}                      Gauge (0.0–1.0)
  netcheck_scrape_count                              Counter (of scrapes)

Usage::

    from netcheck.utils.prometheus import MetricsRegistry, MetricsServer

    registry = MetricsRegistry()

    # Record a check result:
    registry.record("google.com:443", "tcp", success=True, latency_ms=12.5)

    # Serve /metrics on port 9090:
    server = MetricsServer(registry, port=9090)
    server.start()          # background thread
    ...
    server.stop()
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Metric storage
# ---------------------------------------------------------------------------

class _TargetMetric:
    __slots__ = (
        "total",
        "failures",
        "last_latency_ms",
        "last_success",
        "check_type",
    )

    def __init__(self, check_type: str) -> None:
        self.total = 0
        self.failures = 0
        self.last_latency_ms: Optional[float] = None
        self.last_success: Optional[bool] = None
        self.check_type = check_type


class MetricsRegistry:
    """
    Thread-safe registry of check metrics.

    One instance per process. Thread-safe via a single lock.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Key: (target, check_type)
        self._metrics: Dict[Tuple[str, str], _TargetMetric] = {}
        self._scrape_count = 0

    def record(
        self,
        target: str,
        check_type: str,
        success: bool,
        latency_ms: Optional[float] = None,
    ) -> None:
        """Record the result of a single check."""
        key = (target, check_type)
        with self._lock:
            if key not in self._metrics:
                self._metrics[key] = _TargetMetric(check_type)
            m = self._metrics[key]
            m.total += 1
            if not success:
                m.failures += 1
            if latency_ms is not None:
                m.last_latency_ms = latency_ms
            m.last_success = success

    def render(self) -> str:
        """Render all metrics in Prometheus text exposition format."""
        lines: list[str] = []
        with self._lock:
            self._scrape_count += 1

            # -- netcheck_scrape_count
            lines += [
                "# HELP netcheck_scrape_count Total number of /metrics scrapes.",
                "# TYPE netcheck_scrape_count counter",
                f"netcheck_scrape_count {self._scrape_count}",
            ]

            # -- netcheck_check_total
            lines += [
                "",
                "# HELP netcheck_check_total Total number of checks performed.",
                "# TYPE netcheck_check_total counter",
            ]
            for (target, check_type), m in self._metrics.items():
                label = _label(target=target, check_type=check_type)
                lines.append(f"netcheck_check_total{label} {m.total}")

            # -- netcheck_check_failures_total
            lines += [
                "",
                "# HELP netcheck_check_failures_total Total number of failed checks.",
                "# TYPE netcheck_check_failures_total counter",
            ]
            for (target, check_type), m in self._metrics.items():
                label = _label(target=target, check_type=check_type)
                lines.append(f"netcheck_check_failures_total{label} {m.failures}")

            # -- netcheck_latency_seconds
            lines += [
                "",
                "# HELP netcheck_latency_seconds Last observed check latency in seconds.",
                "# TYPE netcheck_latency_seconds gauge",
            ]
            for (target, check_type), m in self._metrics.items():
                if m.last_latency_ms is not None:
                    label = _label(target=target, check_type=check_type)
                    latency_s = m.last_latency_ms / 1000.0
                    lines.append(f"netcheck_latency_seconds{label} {latency_s:.6f}")

            # -- netcheck_up
            lines += [
                "",
                "# HELP netcheck_up 1 if the last check was successful, 0 otherwise.",
                "# TYPE netcheck_up gauge",
            ]
            # Aggregate per target (any check_type)
            target_up: Dict[str, int] = {}
            for (target, _check_type), m in self._metrics.items():
                if m.last_success is not None:
                    target_up[target] = 1 if m.last_success else 0
            for target, up_val in target_up.items():
                label = _label(target=target)
                lines.append(f"netcheck_up{label} {up_val}")

            # -- netcheck_uptime_ratio
            lines += [
                "",
                "# HELP netcheck_uptime_ratio Fraction of successful checks (0.0–1.0).",
                "# TYPE netcheck_uptime_ratio gauge",
            ]
            for (target, check_type), m in self._metrics.items():
                if m.total > 0:
                    ratio = (m.total - m.failures) / m.total
                    label = _label(target=target, check_type=check_type)
                    lines.append(f"netcheck_uptime_ratio{label} {ratio:.4f}")

        lines.append("")  # trailing newline
        return "\n".join(lines)

    def snapshot(self) -> Dict[Tuple[str, str], dict]:
        """Return a dict snapshot for testing/inspection."""
        with self._lock:
            return {
                key: {
                    "total": m.total,
                    "failures": m.failures,
                    "last_latency_ms": m.last_latency_ms,
                    "last_success": m.last_success,
                    "check_type": m.check_type,
                }
                for key, m in self._metrics.items()
            }

    def reset(self) -> None:
        """Clear all recorded metrics (useful in tests)."""
        with self._lock:
            self._metrics.clear()
            self._scrape_count = 0


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------

class MetricsServer:
    """
    Minimal HTTP server that serves /metrics in Prometheus format.

    Runs in a background daemon thread. Stops cleanly on stop().
    """

    def __init__(
        self,
        registry: MetricsRegistry,
        host: str = "0.0.0.0",
        port: int = 9090,
    ) -> None:
        self.registry = registry
        self.host = host
        self.port = port
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the metrics HTTP server in a background daemon thread."""
        registry = self.registry

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path in ("/metrics", "/metrics/"):
                    body = registry.render().encode("utf-8")
                    self.send_response(200)
                    self.send_header(
                        "Content-Type",
                        "text/plain; version=0.0.4; charset=utf-8",
                    )
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"Not Found. Use /metrics\n")

            def log_message(self, fmt: str, *args: object) -> None:
                pass  # suppress access log

        self._server = HTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="netcheck-metrics",
        )
        self._thread.start()

    def stop(self) -> None:
        """Shut down the metrics HTTP server."""
        if self._server:
            self._server.shutdown()
            self._server = None
        self._thread = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def url(self) -> str:
        return f"http://{self.host}:{self.port}/metrics"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _label(**kwargs: str) -> str:
    """Render Prometheus label set: {key="val",...}"""
    parts = [f'{k}="{_escape(v)}"' for k, v in kwargs.items()]
    return "{" + ",".join(parts) + "}"


def _escape(val: str) -> str:
    """Escape label value for Prometheus text format."""
    return val.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
