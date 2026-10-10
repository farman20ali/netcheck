"""
netcheck.data.presets
~~~~~~~~~~~~~~~~~~~~~

Built-in preset host lists for common cloud providers and services.

Usage::

    from netcheck.data.presets import PRESETS, list_presets, get_preset

    targets = get_preset("aws")   # List[Tuple[str, int]]
    for host, port in targets:
        print(host, port)

CLI::

    netcheck preset aws        # Expand to batch TCP check of AWS endpoints
    netcheck preset gcp        # GCP endpoints
    netcheck preset k8s        # Kubernetes registry endpoints
    netcheck preset cloudflare # Cloudflare DNS servers
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Preset definitions
# Each value is a list of "host:port" strings (or just "host" for port 443)
# ---------------------------------------------------------------------------

PRESETS: Dict[str, List[str]] = {
    "aws": [
        "ec2.amazonaws.com:443",
        "s3.amazonaws.com:443",
        "rds.amazonaws.com:3306",
        "sqs.amazonaws.com:443",
        "sns.amazonaws.com:443",
        "dynamodb.amazonaws.com:443",
        "lambda.amazonaws.com:443",
        "iam.amazonaws.com:443",
        "sts.amazonaws.com:443",
    ],
    "gcp": [
        "storage.googleapis.com:443",
        "compute.googleapis.com:443",
        "bigquery.googleapis.com:443",
        "cloudfunctions.googleapis.com:443",
        "pubsub.googleapis.com:443",
        "spanner.googleapis.com:443",
    ],
    "azure": [
        "management.azure.com:443",
        "login.microsoftonline.com:443",
        "blob.core.windows.net:443",
        "servicebus.windows.net:443",
        "database.windows.net:1433",
    ],
    "k8s": [
        "k8s.io:443",
        "registry.k8s.io:443",
        "storage.googleapis.com:443",
        "dl.k8s.io:443",
    ],
    "cloudflare": [
        "1.1.1.1:53",
        "1.0.0.1:53",
        "1.1.1.1:443",
        "cloudflare.com:443",
    ],
    "google-dns": [
        "8.8.8.8:53",
        "8.8.4.4:53",
    ],
    "github": [
        "github.com:443",
        "api.github.com:443",
        "raw.githubusercontent.com:443",
        "objects.githubusercontent.com:443",
        "github.githubassets.com:443",
    ],
    "docker": [
        "hub.docker.com:443",
        "registry-1.docker.io:443",
        "auth.docker.io:443",
        "index.docker.io:443",
        "production.cloudflare.docker.com:443",
    ],
    "monitoring": [
        "grafana.com:443",
        "prometheus.io:443",
        "alertmanager.io:443",
    ],
    "ci": [
        "github.com:443",
        "api.github.com:443",
        "pypi.org:443",
        "files.pythonhosted.org:443",
        "npmjs.com:443",
    ],
}

# Human-readable descriptions for each preset
PRESET_DESCRIPTIONS: Dict[str, str] = {
    "aws":         "Amazon Web Services core endpoints",
    "gcp":         "Google Cloud Platform core endpoints",
    "azure":       "Microsoft Azure core endpoints",
    "k8s":         "Kubernetes registry and distribution endpoints",
    "cloudflare":  "Cloudflare DNS resolvers (1.1.1.1 / 1.0.0.1)",
    "google-dns":  "Google DNS resolvers (8.8.8.8 / 8.8.4.4)",
    "github":      "GitHub API and content delivery endpoints",
    "docker":      "Docker Hub registry endpoints",
    "monitoring":  "Grafana + Prometheus infrastructure endpoints",
    "ci":          "Common CI/CD dependencies (PyPI, npm, GitHub)",
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def list_presets() -> Dict[str, str]:
    """Return {preset_name: description} for all defined presets."""
    return {name: PRESET_DESCRIPTIONS.get(name, "") for name in PRESETS}


def get_preset(name: str) -> Optional[List[Tuple[str, int]]]:
    """
    Return list of (host, port) tuples for the named preset.

    Returns None if the preset name is not found.
    """
    entries = PRESETS.get(name)
    if entries is None:
        return None

    result: List[Tuple[str, int]] = []
    for entry in entries:
        if ":" in entry:
            host, port_str = entry.rsplit(":", 1)
            try:
                result.append((host, int(port_str)))
            except ValueError:
                pass
        else:
            result.append((entry, 443))
    return result
