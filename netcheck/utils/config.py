"""
netcheck.utils.config
~~~~~~~~~~~~~~~~~~~~~

Cross-platform configuration management for netcheck.

Config file locations:
  Linux/macOS: ~/.config/netcheck/config.yaml
  Windows:     %APPDATA%\\netcheck\\config.yaml

Priority (highest to lowest):
  1. Environment variables (NETCHECK_*)
  2. Config file (~/.config/netcheck/config.yaml)
  3. Built-in defaults

Passwords are NEVER stored in the config file.
They are always retrieved from the OS keychain via keyring.
"""

from __future__ import annotations

import abc
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Default configuration schema
# ---------------------------------------------------------------------------

_DEFAULTS: dict[str, Any] = {
    "timeout": 5,
    "max_workers": 10,
    "retry": {
        "max_attempts": 3,
        "delay": 1.0,
        "backoff": 2.0,
    },
    "smtp": {
        "host": "",
        "port": 587,
        "user": "",
        "to": "",
        "use_tls": True,
    },
    "slack": {
        "webhook_url": "",
    },
    "webhook": {
        "url": "",
        "token": "",
    },
    "prometheus": {
        "enabled": False,
        "port": 9090,
        "host": "0.0.0.0",
    },
    "alert": {
        "flap_threshold": 2,
        "cooldown_seconds": 300,
    },
}

# ---------------------------------------------------------------------------
# Environment variable → config key mappings
# ---------------------------------------------------------------------------

_ENV_MAP: dict[str, tuple[str, ...]] = {
    "NETCHECK_TIMEOUT": ("timeout",),
    "NETCHECK_MAX_WORKERS": ("max_workers",),
    "NETCHECK_SMTP_HOST": ("smtp", "host"),
    "NETCHECK_SMTP_PORT": ("smtp", "port"),
    "NETCHECK_SMTP_USER": ("smtp", "user"),
    "NETCHECK_SMTP_TO": ("smtp", "to"),
    "NETCHECK_SLACK_WEBHOOK": ("slack", "webhook_url"),
    "NETCHECK_WEBHOOK_URL": ("webhook", "url"),
    "NETCHECK_WEBHOOK_TOKEN": ("webhook", "token"),
    "NETCHECK_PROMETHEUS_PORT": ("prometheus", "port"),
}

# ---------------------------------------------------------------------------
# Keychain service name
# ---------------------------------------------------------------------------

_KEYCHAIN_SERVICE = "netcheck"


# ---------------------------------------------------------------------------
# NetCheckConfig
# ---------------------------------------------------------------------------

class NetCheckConfig:
    """Loads, validates, and saves the netcheck config file."""

    # ── Paths ──────────────────────────────────────────────────────────────

    @staticmethod
    def path() -> Path:
        """Return the OS-appropriate config file path."""
        if platform.system() == "Windows":
            appdata = os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")
            return Path(appdata) / "netcheck" / "config.yaml"
        # Linux / macOS
        xdg = os.environ.get("XDG_CONFIG_HOME", "")
        base = Path(xdg) if xdg else Path.home() / ".config"
        return base / "netcheck" / "config.yaml"

    # ── Load ───────────────────────────────────────────────────────────────

    @staticmethod
    def load() -> dict[str, Any]:
        """Load config with env-var overrides merged on top."""
        import copy

        # Load .netcheck.env into environment variables if it exists
        env_file = NetCheckConfig.path().parent / ".netcheck.env"
        if env_file.exists():
            try:
                for line in env_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        os.environ.setdefault(k.strip(), v.strip())
            except Exception as exc:
                print(
                    f"[netcheck] Warning: could not load .netcheck.env: {exc}",
                    file=sys.stderr,
                )

        cfg = copy.deepcopy(_DEFAULTS)
        config_path = NetCheckConfig.path()

        if config_path.exists():
            try:
                raw = _yaml_load(config_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    _deep_merge(cfg, raw)
            except Exception as exc:
                # Malformed config — warn but continue with defaults
                print(
                    f"[netcheck] Warning: could not parse config at {config_path}: {exc}",
                    file=sys.stderr,
                )

        # Apply environment variable overrides
        for env_key, path in _ENV_MAP.items():
            val = os.environ.get(env_key)
            if val is not None:
                _set_nested(cfg, path, _coerce(val))

        return cfg

    # ── Save ───────────────────────────────────────────────────────────────

    @staticmethod
    def save(data: dict[str, Any]) -> None:
        """Write config YAML. Sets chmod 600 on POSIX platforms."""
        config_path = NetCheckConfig.path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(_yaml_dump(data), encoding="utf-8")
        if platform.system() != "Windows":
            os.chmod(config_path, stat.S_IRUSR | stat.S_IWUSR)

    # ── Show ───────────────────────────────────────────────────────────────

    @staticmethod
    def show() -> str:
        """Return config as YAML string with sensitive fields masked, plus keyring status."""
        import copy

        cfg = NetCheckConfig.load()
        masked = copy.deepcopy(cfg)
        _mask_sensitive(masked)

        output = []
        output.append("=== Configuration File (yaml) ===")
        output.append(f"Path: {NetCheckConfig.path()}")
        output.append(_yaml_dump(masked))
        output.append("\n=== Secrets Backend ===")
        output.append(f"  Active: {_select_backend().name()}")
        output.append("\n=== OS Keyring Status ===")

        services = {
            "email": "SMTP Password",
            "smtp_user": "SMTP Username/Sender",
            "smtp_to": "SMTP Recipient",
            "slack": "Slack Webhook URL",
            "webhook": "Webhook Bearer Token",
        }
        for svc_key, label in services.items():
            val = _keyring_get(_KEYCHAIN_SERVICE, svc_key)
            if val:
                # Mask the value for display
                masked_val = "***"
                if "@" in val:
                    parts = val.split("@")
                    masked_val = parts[0][:2] + "..." + "@" + parts[1]
                elif val.startswith("https://"):
                    masked_val = val[:24] + "..."
                output.append(f"  {label:<22}: [SET] ({masked_val})")
            else:
                output.append(f"  {label:<22}: [NOT SET]")

        return "\n".join(output)

    # ── Init wizard ────────────────────────────────────────────────────────

    @staticmethod
    def init_wizard() -> None:
        """Interactive prompt-based setup wizard."""
        print("NetCheck Configuration Wizard")
        print("=" * 40)
        cfg: dict[str, Any] = {}

        timeout = _prompt("Default timeout (seconds)", default="5")
        cfg["timeout"] = int(timeout)

        workers = _prompt("Max concurrent workers", default="10")
        cfg["max_workers"] = int(workers)

        use_smtp = _prompt("Configure SMTP alerts? [y/N]", default="n").lower()
        if use_smtp == "y":
            host = _prompt("SMTP host", default="smtp.gmail.com")
            port_str = _prompt("SMTP port", default="587")
            try:
                port = int(port_str)
            except ValueError:
                port = 587

            secure_emails = _prompt("Store SMTP emails securely in OS keyring? [Y/n]", default="y").lower()
            if secure_emails == "y":
                user = _prompt("SMTP username (e.g. sender@gmail.com)")
                to = _prompt("Alert recipient email")
                if user:
                    _keyring_set(_KEYCHAIN_SERVICE, "smtp_user", user)
                if to:
                    _keyring_set(_KEYCHAIN_SERVICE, "smtp_to", to)
                cfg["smtp"] = {
                    "host": host,
                    "port": port,
                    "use_tls": True,
                }
                print("✅ SMTP username and recipient stored securely in OS keyring.")
            else:
                user = _prompt("SMTP username (e.g. sender@gmail.com)")
                to = _prompt("Alert recipient email")
                cfg["smtp"] = {
                    "host": host,
                    "port": port,
                    "user": user,
                    "to": to,
                    "use_tls": True,
                }

        use_slack = _prompt("Configure Slack alerts? [y/N]", default="n").lower()
        if use_slack == "y":
            slack_url = _prompt("Slack webhook URL")
            if slack_url:
                _keyring_set(_KEYCHAIN_SERVICE, "slack", slack_url)
                print("✅ Slack webhook URL stored securely in OS keychain.")
            cfg["slack"] = {}  # no URL stored in config file

        NetCheckConfig.save(cfg)
        print(f"\n✅ Configuration saved to: {NetCheckConfig.path()}")

    # ── Keychain ───────────────────────────────────────────────────────────

    @staticmethod
    def set_password(service: str) -> None:
        """Prompt for a secret and store it in the OS keychain.

        Service-specific prompts:
          - email      → SMTP password
          - smtp_user  → SMTP username
          - smtp_to    → SMTP recipient email
          - slack      → Slack incoming webhook URL
          - webhook    → HTTP webhook bearer token
          - other      → generic password / secret
        """
        import getpass

        _labels = {
            "email":     "SMTP password",
            "smtp_user": "SMTP username (e.g. sender@gmail.com)",
            "smtp_to":   "SMTP recipient email address",
            "slack":     "Slack webhook URL (starts with https://hooks.slack.com/...)",
            "webhook":   "Webhook bearer token",
        }
        label = _labels.get(service, f"secret for '{service}'")
        secret = getpass.getpass(f"Enter {label}: ")
        if not secret.strip():
            print("Aborted — nothing stored.", file=sys.stderr)
            return
        _keyring_set(_KEYCHAIN_SERVICE, service, secret.strip())
        print(f"✅ Stored securely in OS keychain for service '{service}'.")

    @staticmethod
    def clear_password(service: str) -> None:
        """Remove password from OS keychain."""
        _keyring_delete(_KEYCHAIN_SERVICE, service)
        print(f"✅ Password removed from keychain for service '{service}'.")

    @staticmethod
    def get_password(service: str) -> Optional[str]:
        """Retrieve password for *service* from env var or OS keychain.

        Environment variable fallbacks (useful on headless Linux servers):
          - service ``"email"``   → ``NETCHECK_SMTP_PASSWORD``
        """
        # Environment variable takes priority (no keyring needed)
        _env_fallbacks: dict[str, str] = {
            "email": "NETCHECK_SMTP_PASSWORD",
        }
        env_var = _env_fallbacks.get(service)
        if env_var:
            env_val = os.environ.get(env_var, "")
            if env_val:
                return env_val
        return _keyring_get(_KEYCHAIN_SERVICE, service)

    @staticmethod
    def get_slack_webhook() -> str:
        """
        Return the Slack webhook URL.

        Priority:
          1. NETCHECK_SLACK_WEBHOOK environment variable
          2. OS keyring (stored via ``netcheck config set-password slack``)
          3. Empty string (alerts silently skipped)
        """
        env_val = os.environ.get("NETCHECK_SLACK_WEBHOOK", "")
        if env_val:
            return env_val
        return _keyring_get(_KEYCHAIN_SERVICE, "slack") or ""

    @staticmethod
    def get_webhook_token() -> str:
        """
        Return the generic webhook bearer token from keyring.

        Priority:
          1. NETCHECK_WEBHOOK_TOKEN environment variable
          2. OS keyring (stored via ``netcheck config set-password webhook``)
          3. Empty string
        """
        env_val = os.environ.get("NETCHECK_WEBHOOK_TOKEN", "")
        if env_val:
            return env_val
        return _keyring_get(_KEYCHAIN_SERVICE, "webhook") or ""

    @staticmethod
    def get_smtp_user() -> str:
        """
        Return the SMTP username.

        Priority:
          1. NETCHECK_SMTP_USER environment variable
          2. OS keyring (stored via ``netcheck config set-password smtp_user``)
          3. Value in config.yaml
        """
        env_val = os.environ.get("NETCHECK_SMTP_USER", "")
        if env_val:
            return env_val
        keyring_val = _keyring_get(_KEYCHAIN_SERVICE, "smtp_user")
        if keyring_val:
            return keyring_val
        cfg = NetCheckConfig.load()
        return cfg.get("smtp", {}).get("user", "")

    @staticmethod
    def get_smtp_to() -> str:
        """
        Return the SMTP recipient email address.

        Priority:
          1. NETCHECK_SMTP_TO environment variable
          2. OS keyring (stored via ``netcheck config set-password smtp_to``)
          3. Value in config.yaml
        """
        env_val = os.environ.get("NETCHECK_SMTP_TO", "")
        if env_val:
            return env_val
        keyring_val = _keyring_get(_KEYCHAIN_SERVICE, "smtp_to")
        if keyring_val:
            return keyring_val
        cfg = NetCheckConfig.load()
        return cfg.get("smtp", {}).get("to", "")

    @staticmethod
    def purge() -> None:
        """Permanently delete configuration file and all keyring secrets."""
        ans = input("Warning: This will permanently delete the config file and purge all stored secrets from the OS keyring. Continue? [y/N]: ").strip().lower()
        if ans != "y":
            print("Aborted.")
            return

        # 1. Clear keyring secrets
        services = ["email", "smtp_user", "smtp_to", "slack", "webhook"]
        for svc in services:
            try:
                _keyring_delete(_KEYCHAIN_SERVICE, svc)
            except Exception:
                pass
        print("✅ Cleared all NetCheck secrets from OS keyring.")

        # 2. Delete configuration file
        config_path = NetCheckConfig.path()
        if config_path.exists():
            try:
                config_path.unlink()
                print(f"✅ Deleted configuration file at: {config_path}")
            except Exception as exc:
                print(f"❌ Failed to delete configuration file: {exc}", file=sys.stderr)
        else:
            print("Configuration file already removed.")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, override: dict) -> None:
    """Recursively merge override into base in-place."""
    for key, val in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val


def _set_nested(cfg: dict, path: tuple, value: Any) -> None:
    """Set a nested dict key from a tuple path."""
    for key in path[:-1]:
        cfg = cfg.setdefault(key, {})
    cfg[path[-1]] = value


def _coerce(value: str) -> Any:
    """Try to coerce a string value to int or float."""
    for converter in (int, float):
        try:
            return converter(value)
        except ValueError:
            pass
    return value


def _mask_sensitive(cfg: dict, _mask: str = "***") -> None:
    """Mask known sensitive keys in-place."""
    sensitive_keys = {"password", "token", "webhook_url", "secret", "api_key"}
    for key in list(cfg.keys()):
        if key in sensitive_keys:
            cfg[key] = _mask
        elif isinstance(cfg[key], dict):
            _mask_sensitive(cfg[key], _mask)


def _prompt(label: str, default: str = "") -> str:
    """Simple interactive prompt with optional default."""
    suffix = f" [{default}]" if default else ""
    answer = input(f"{label}{suffix}: ").strip()
    return answer if answer else default


# ---------------------------------------------------------------------------
# Minimal YAML helpers (stdlib only — no PyYAML dependency)
# ---------------------------------------------------------------------------

def _yaml_load(text: str) -> Any:
    """
    Minimal YAML-compatible loader.
    Supports nested key: value and simple lists.
    Falls back to JSON if the text looks like JSON.
    """
    text = text.strip()
    if text.startswith("{") or text.startswith("["):
        return json.loads(text)
    return _parse_yaml_block(text.splitlines())


def _parse_yaml_block(lines: list[str], indent: int = 0) -> dict[str, Any]:
    """Recursive minimal YAML block parser."""
    result: dict[str, Any] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        current_indent = len(line) - len(stripped)

        if current_indent < indent:
            break
        if current_indent > indent:
            i += 1
            continue

        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        if ":" in stripped:
            raw_key, _, raw_val = stripped.partition(":")
            key = raw_key.strip()
            val = raw_val.strip()

            if not val:
                # Nested block: collect child lines
                child_lines: list[str] = []
                j = i + 1
                while j < len(lines):
                    cl = lines[j]
                    cs = cl.lstrip()
                    ci = len(cl) - len(cs)
                    if ci <= indent and cs and not cs.startswith("#"):
                        break
                    child_lines.append(cl)
                    j += 1
                result[key] = _parse_yaml_block(child_lines, indent + 2)
                i = j
                continue

            # Scalar value
            result[key] = _coerce_yaml_scalar(val)

        i += 1
    return result


def _coerce_yaml_scalar(val: str) -> Any:
    """Convert a YAML scalar string to a Python type."""
    if val.lower() in ("true", "yes"):
        return True
    if val.lower() in ("false", "no"):
        return False
    if val.lower() in ("null", "~", ""):
        return None
    # Strip quotes
    if (val.startswith('"') and val.endswith('"')) or (
        val.startswith("'") and val.endswith("'")
    ):
        return val[1:-1]
    for converter in (int, float):
        try:
            return converter(val)
        except ValueError:
            pass
    return val


def _yaml_dump(data: Any, indent: int = 0) -> str:
    """Minimal YAML dumper (no PyYAML dependency)."""
    lines: list[str] = []
    pad = "  " * indent

    if isinstance(data, dict):
        for key, val in data.items():
            if isinstance(val, dict):
                lines.append(f"{pad}{key}:")
                lines.append(_yaml_dump(val, indent + 1))
            elif isinstance(val, list):
                lines.append(f"{pad}{key}:")
                for item in val:
                    lines.append(f"{pad}  - {item}")
            elif isinstance(val, bool):
                lines.append(f"{pad}{key}: {'true' if val else 'false'}")
            elif val is None:
                lines.append(f"{pad}{key}: ~")
            elif isinstance(val, str) and (":" in val or "#" in val or not val):
                lines.append(f'{pad}{key}: "{val}"')
            else:
                lines.append(f"{pad}{key}: {val}")
    else:
        lines.append(f"{pad}{data}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Multi-backend secret store system (keyring/Keychain/secret-tool/.env)
# ---------------------------------------------------------------------------

class SecretBackend(abc.ABC):
    @abc.abstractmethod
    def name(self) -> str:
        """User-friendly name of the backend."""
        pass

    @abc.abstractmethod
    def available(self) -> bool:
        """Return True if this backend is supported and working on the current machine."""
        pass

    @abc.abstractmethod
    def get(self, username: str) -> Optional[str]:
        """Retrieve a secret."""
        pass

    @abc.abstractmethod
    def set(self, username: str, secret: str) -> None:
        """Store a secret."""
        pass

    @abc.abstractmethod
    def delete(self, username: str) -> None:
        """Delete a secret."""
        pass


class WindowsCredentialBackend(SecretBackend):
    def name(self) -> str:
        return "Windows Credential Manager (keyring)"

    def available(self) -> bool:
        if platform.system() != "Windows":
            return False
        try:
            import keyring
            backend = keyring.get_keyring()
            backend_name = type(backend).__name__.lower()
            if "fail" in backend_name or "null" in backend_name:
                return False
            return True
        except Exception:
            return False

    def get(self, username: str) -> Optional[str]:
        try:
            import keyring
            return keyring.get_password(_KEYCHAIN_SERVICE, username)
        except Exception as exc:
            print(f"[netcheck] Windows keyring read failed: {exc}", file=sys.stderr)
            return None

    def set(self, username: str, secret: str) -> None:
        try:
            import keyring
            keyring.set_password(_KEYCHAIN_SERVICE, username, secret)
        except Exception as exc:
            raise RuntimeError(f"Windows keyring write failed: {exc}") from exc

    def delete(self, username: str) -> None:
        try:
            import keyring
            try:
                keyring.delete_password(_KEYCHAIN_SERVICE, username)
            except keyring.errors.PasswordDeleteError:
                pass
        except Exception as exc:
            print(f"[netcheck] Windows keyring delete failed: {exc}", file=sys.stderr)


class MacOSKeychainBackend(SecretBackend):
    def name(self) -> str:
        return "macOS Keychain (security CLI)"

    def available(self) -> bool:
        return platform.system() == "Darwin" and os.path.exists("/usr/bin/security")

    def get(self, username: str) -> Optional[str]:
        try:
            res = subprocess.run(
                ["/usr/bin/security", "find-generic-password", "-s", _KEYCHAIN_SERVICE, "-a", username, "-w"],
                capture_output=True,
                text=True,
                check=False
            )
            if res.returncode == 0:
                return res.stdout.strip()
            return None
        except Exception as exc:
            print(f"[netcheck] macOS keychain read failed: {exc}", file=sys.stderr)
            return None

    def set(self, username: str, secret: str) -> None:
        try:
            res = subprocess.run(
                ["/usr/bin/security", "add-generic-password", "-U", "-s", _KEYCHAIN_SERVICE, "-a", username, "-w", secret],
                capture_output=True,
                text=True,
                check=False
            )
            if res.returncode != 0:
                raise RuntimeError(res.stderr.strip() or f"exit code {res.returncode}")
        except Exception as exc:
            raise RuntimeError(f"macOS keychain write failed: {exc}") from exc

    def delete(self, username: str) -> None:
        try:
            subprocess.run(
                ["/usr/bin/security", "delete-generic-password", "-s", _KEYCHAIN_SERVICE, "-a", username],
                capture_output=True,
                text=True,
                check=False
            )
        except Exception as exc:
            print(f"[netcheck] macOS keychain delete failed: {exc}", file=sys.stderr)


class LinuxSecretToolBackend(SecretBackend):
    def name(self) -> str:
        return "Linux Secret Service (secret-tool CLI)"

    def available(self) -> bool:
        if platform.system() != "Linux":
            return False
        if not shutil.which("secret-tool"):
            return False
        # Test if D-Bus session bus is working without connection errors
        try:
            res = subprocess.run(
                ["secret-tool", "lookup", "service", "netcheck_probe", "username", "probe"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if "fail" in res.stderr.lower() or "dbus" in res.stderr.lower() or "could not connect" in res.stderr.lower():
                return False
            return True
        except Exception:
            return False

    def get(self, username: str) -> Optional[str]:
        try:
            res = subprocess.run(
                ["secret-tool", "lookup", "service", _KEYCHAIN_SERVICE, "username", username],
                capture_output=True,
                text=True,
                timeout=5
            )
            if res.returncode == 0 and res.stdout:
                return res.stdout.strip()
            return None
        except Exception as exc:
            print(f"[netcheck] Linux secret-tool lookup failed: {exc}", file=sys.stderr)
            return None

    def set(self, username: str, secret: str) -> None:
        try:
            res = subprocess.run(
                ["secret-tool", "store", "--label", f"NetCheck {username}", "service", _KEYCHAIN_SERVICE, "username", username],
                input=secret,
                capture_output=True,
                text=True,
                timeout=5
            )
            if res.returncode != 0:
                raise RuntimeError(res.stderr.strip() or f"exit code {res.returncode}")
        except Exception as exc:
            raise RuntimeError(f"Linux secret-tool store failed: {exc}") from exc

    def delete(self, username: str) -> None:
        try:
            subprocess.run(
                ["secret-tool", "clear", "service", _KEYCHAIN_SERVICE, "username", username],
                capture_output=True,
                timeout=5
            )
        except Exception as exc:
            print(f"[netcheck] Linux secret-tool clear failed: {exc}", file=sys.stderr)


class EnvFileBackend(SecretBackend):
    def name(self) -> str:
        return "Environment File (.netcheck.env)"

    def available(self) -> bool:
        return True

    def _get_path(self) -> Path:
        return NetCheckConfig.path().parent / ".netcheck.env"

    def _load_env_dict(self) -> dict[str, str]:
        path = self._get_path()
        if not path.exists():
            return {}
        res = {}
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    res[k.strip()] = v.strip()
        except Exception as exc:
            print(f"[netcheck] Warning: failed to read .netcheck.env: {exc}", file=sys.stderr)
        return res

    def _save_env_dict(self, data: dict[str, str]) -> None:
        path = self._get_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# NetCheck secrets — DO NOT COMMIT THIS FILE",
            "# Auto-generated by NetCheck config manager",
            ""
        ]
        for k, v in data.items():
            lines.append(f"{k}={v}")
        try:
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            if platform.system() != "Windows":
                os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        except Exception as exc:
            raise RuntimeError(f"failed to write .netcheck.env: {exc}") from exc

    def _to_env_key(self, username: str) -> str:
        mapping = {
            "email": "NETCHECK_SMTP_PASSWORD",
            "smtp_user": "NETCHECK_SMTP_USER",
            "smtp_to": "NETCHECK_SMTP_TO",
            "slack": "NETCHECK_SLACK_WEBHOOK",
            "webhook": "NETCHECK_WEBHOOK_TOKEN"
        }
        return mapping.get(username, f"NETCHECK_{username.upper()}")

    def get(self, username: str) -> Optional[str]:
        env_key = self._to_env_key(username)
        if env_key in os.environ:
            return os.environ[env_key]
        data = self._load_env_dict()
        return data.get(env_key)

    def set(self, username: str, secret: str) -> None:
        env_key = self._to_env_key(username)
        data = self._load_env_dict()
        data[env_key] = secret
        self._save_env_dict(data)
        os.environ[env_key] = secret

    def delete(self, username: str) -> None:
        env_key = self._to_env_key(username)
        data = self._load_env_dict()
        if env_key in data:
            del data[env_key]
            self._save_env_dict(data)
        os.environ.pop(env_key, None)


class NullBackend(SecretBackend):
    def name(self) -> str:
        return "None (Secrets must be set via system environment variables)"

    def available(self) -> bool:
        return True

    def get(self, username: str) -> Optional[str]:
        _warn_no_backend()
        return None

    def set(self, username: str, secret: str) -> None:
        _warn_no_backend()
        raise RuntimeError(
            "No secret storage backend available. "
            "Please configure system environment variables, e.g. NETCHECK_SLACK_WEBHOOK."
        )

    def delete(self, username: str) -> None:
        _warn_no_backend()
        raise RuntimeError("No secret storage backend available.")


_no_backend_warned = False

def _warn_no_backend() -> None:
    global _no_backend_warned
    if _no_backend_warned:
        return
    _no_backend_warned = True
    print(
        "[netcheck] WARNING: No usable native keychain or writable env file backend.\n"
        "  Please export secrets to your environment, e.g.:\n"
        "    export NETCHECK_SMTP_PASSWORD=...\n"
        "    export NETCHECK_SLACK_WEBHOOK=...",
        file=sys.stderr
    )


_active_backend: Optional[SecretBackend] = None

def _select_backend() -> SecretBackend:
    global _active_backend
    if _active_backend is not None:
        return _active_backend

    backends: list[SecretBackend] = []
    if sys.platform == "win32":
        backends.append(WindowsCredentialBackend())
    elif sys.platform == "darwin":
        backends.append(MacOSKeychainBackend())
    else:
        backends.append(LinuxSecretToolBackend())

    backends.append(EnvFileBackend())
    backends.append(NullBackend())

    for b in backends:
        if b.available():
            _active_backend = b
            return b

    _active_backend = NullBackend()
    return _active_backend


# ── Compatibility entry points ─────────────────────────────────────────────

def _keyring_set(service: str, username: str, password: str) -> None:
    backend = _select_backend()
    backend.set(username, password)


def _keyring_get(service: str, username: str) -> Optional[str]:
    backend = _select_backend()
    return backend.get(username)


def _keyring_delete(service: str, username: str) -> None:
    backend = _select_backend()
    backend.delete(username)
