"""
tests/unit/test_config.py
~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for netcheck.utils.config.NetCheckConfig
"""

from __future__ import annotations

import os
import platform
import stat
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from netcheck.utils.config import (
    NetCheckConfig,
    _deep_merge,
    _yaml_dump,
    _yaml_load,
    _coerce_yaml_scalar,
)


# ---------------------------------------------------------------------------
# _yaml_load / _yaml_dump round-trip
# ---------------------------------------------------------------------------

class TestYamlHelpers:
    def test_load_simple_key_value(self):
        text = "timeout: 5\nmax_workers: 10"
        data = _yaml_load(text)
        assert data["timeout"] == 5
        assert data["max_workers"] == 10

    def test_load_nested(self):
        text = "smtp:\n  host: mail.example.com\n  port: 587"
        data = _yaml_load(text)
        assert data["smtp"]["host"] == "mail.example.com"
        assert data["smtp"]["port"] == 587

    def test_load_boolean_true(self):
        data = _yaml_load("use_tls: true")
        assert data["use_tls"] is True

    def test_load_boolean_false(self):
        data = _yaml_load("enabled: false")
        assert data["enabled"] is False

    def test_load_null(self):
        data = _yaml_load("token: ~")
        assert data["token"] is None

    def test_load_quoted_string(self):
        data = _yaml_load('name: "hello world"')
        assert data["name"] == "hello world"

    def test_load_comments_ignored(self):
        text = "# This is a comment\ntimeout: 3"
        data = _yaml_load(text)
        assert data["timeout"] == 3

    def test_dump_and_reload_roundtrip(self):
        original = {"timeout": 5, "smtp": {"host": "mail.test", "port": 587}}
        dumped = _yaml_dump(original)
        loaded = _yaml_load(dumped)
        assert loaded["timeout"] == 5
        assert loaded["smtp"]["host"] == "mail.test"

    def test_dump_bool_as_lowercase(self):
        dumped = _yaml_dump({"enabled": True})
        assert "true" in dumped

    def test_coerce_int(self):
        assert _coerce_yaml_scalar("42") == 42

    def test_coerce_float(self):
        assert _coerce_yaml_scalar("3.14") == pytest.approx(3.14)

    def test_coerce_string_passthrough(self):
        assert _coerce_yaml_scalar("hello") == "hello"


# ---------------------------------------------------------------------------
# _deep_merge
# ---------------------------------------------------------------------------

class TestDeepMerge:
    def test_merge_flat(self):
        base: dict[str, Any] = {"a": 1, "b": 2}
        _deep_merge(base, {"b": 99, "c": 3})
        assert base == {"a": 1, "b": 99, "c": 3}

    def test_merge_nested(self):
        base = {"smtp": {"host": "old.com", "port": 25}}
        _deep_merge(base, {"smtp": {"port": 587}})
        assert base["smtp"]["host"] == "old.com"
        assert base["smtp"]["port"] == 587

    def test_merge_does_not_affect_separate_dict(self):
        import copy
        base = {"a": {"x": 1}}
        orig = copy.deepcopy(base)
        _deep_merge(base, {"b": 2})
        assert orig == {"a": {"x": 1}}


# ---------------------------------------------------------------------------
# NetCheckConfig.path()
# ---------------------------------------------------------------------------

class TestNetCheckConfigPath:
    def test_path_returns_path_object(self):
        p = NetCheckConfig.path()
        assert isinstance(p, Path)

    def test_path_ends_with_config_yaml(self):
        p = NetCheckConfig.path()
        assert p.name == "config.yaml"

    def test_path_contains_netcheck(self):
        p = NetCheckConfig.path()
        assert "netcheck" in str(p)

    def test_path_uses_appdata_on_windows(self):
        with patch("platform.system", return_value="Windows"):
            with patch.dict(os.environ, {"APPDATA": "C:\\Users\\Test\\AppData\\Roaming"}):
                p = NetCheckConfig.path()
                assert "netcheck" in str(p)

    def test_path_uses_xdg_config_home_on_linux(self):
        with patch("platform.system", return_value="Linux"):
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/tmp/xdg"}, clear=False):
                p = NetCheckConfig.path()
                assert p.as_posix().startswith("/tmp/xdg")



# ---------------------------------------------------------------------------
# NetCheckConfig.load()
# ---------------------------------------------------------------------------

class TestNetCheckConfigLoad:
    def test_load_returns_dict(self):
        cfg = NetCheckConfig.load()
        assert isinstance(cfg, dict)

    def test_load_has_timeout_key(self):
        cfg = NetCheckConfig.load()
        assert "timeout" in cfg

    def test_load_has_max_workers_key(self):
        cfg = NetCheckConfig.load()
        assert "max_workers" in cfg

    def test_load_defaults_when_no_file(self):
        with patch.object(NetCheckConfig, "path", return_value=Path("/nonexistent/path/config.yaml")):
            cfg = NetCheckConfig.load()
            assert cfg["timeout"] == 5
            assert cfg["max_workers"] == 10

    def test_env_override_timeout(self):
        with patch.dict(os.environ, {"NETCHECK_TIMEOUT": "42"}):
            cfg = NetCheckConfig.load()
            assert cfg["timeout"] == 42

    def test_env_override_max_workers(self):
        with patch.dict(os.environ, {"NETCHECK_MAX_WORKERS": "20"}):
            cfg = NetCheckConfig.load()
            assert cfg["max_workers"] == 20

    def test_env_override_smtp_host(self):
        with patch.dict(os.environ, {"NETCHECK_SMTP_HOST": "mail.test.com"}):
            cfg = NetCheckConfig.load()
            assert cfg["smtp"]["host"] == "mail.test.com"

    def test_env_override_slack_webhook(self):
        with patch.dict(os.environ, {"NETCHECK_SLACK_WEBHOOK": "https://hooks.slack.com/x"}):
            cfg = NetCheckConfig.load()
            assert cfg["slack"]["webhook_url"] == "https://hooks.slack.com/x"

    def test_load_merges_nested_keys(self):
        yaml_content = "smtp:\n  host: custom.smtp.com"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write(yaml_content)
            tmp = Path(f.name)
        try:
            with patch.object(NetCheckConfig, "path", return_value=tmp):
                cfg = NetCheckConfig.load()
            # Custom value overrides default
            assert cfg["smtp"]["host"] == "custom.smtp.com"
            # Sibling keys from defaults still present
            assert "port" in cfg["smtp"]
        finally:
            tmp.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# NetCheckConfig.save()
# ---------------------------------------------------------------------------

class TestNetCheckConfigSave:
    def test_save_writes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "netcheck" / "config.yaml"
            with patch.object(NetCheckConfig, "path", return_value=config_path):
                NetCheckConfig.save({"timeout": 7})
            assert config_path.exists()

    def test_save_writes_correct_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "netcheck" / "config.yaml"
            with patch.object(NetCheckConfig, "path", return_value=config_path):
                NetCheckConfig.save({"timeout": 7, "max_workers": 5})
            content = config_path.read_text()
            assert "timeout" in content
            assert "7" in content

    @pytest.mark.skipif(platform.system() == "Windows", reason="chmod not enforced on Windows")
    def test_save_sets_chmod_600(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "netcheck" / "config.yaml"
            with patch.object(NetCheckConfig, "path", return_value=config_path):
                NetCheckConfig.save({"timeout": 5})
            mode = stat.S_IMODE(os.stat(config_path).st_mode)
            assert mode == 0o600


# ---------------------------------------------------------------------------
# NetCheckConfig.show() — masking
# ---------------------------------------------------------------------------

class TestNetCheckConfigShow:
    def test_show_returns_string(self):
        result = NetCheckConfig.show()
        assert isinstance(result, str)

    def test_show_masks_webhook_token(self):
        data = {"webhook": {"url": "http://example.com", "token": "secret123"}}
        with patch.object(NetCheckConfig, "load", return_value=data):
            result = NetCheckConfig.show()
        assert "secret123" not in result
        assert "***" in result

    def test_show_masks_slack_webhook(self):
        data = {"slack": {"webhook_url": "https://hooks.slack.com/abc"}}
        with patch.object(NetCheckConfig, "load", return_value=data):
            result = NetCheckConfig.show()
        assert "https://hooks.slack.com/abc" not in result

    def test_show_does_not_modify_original(self):
        data = {"webhook": {"token": "mysecret"}}
        import copy
        original = copy.deepcopy(data)
        with patch.object(NetCheckConfig, "load", return_value=data):
            NetCheckConfig.show()
        # Original data dict should be unchanged
        assert data["webhook"]["token"] == "mysecret"

    def test_show_displays_keyring_status(self):
        data = {"timeout": 5}
        with patch("netcheck.utils.config._keyring_get", return_value="test@example.com") as mock_get, \
             patch.object(NetCheckConfig, "load", return_value=data):
            result = NetCheckConfig.show()
        assert "=== OS Keyring Status ===" in result
        assert "SMTP Username/Sender" in result
        assert "te...@example.com" in result  # masked representation of test@example.com

    def test_get_smtp_user_keyring_priority(self):
        # Keyring has priority over config.yaml
        cfg_data = {"smtp": {"user": "config@example.com"}}
        with patch("netcheck.utils.config._keyring_get", return_value="keyring@example.com") as mock_get, \
             patch.object(NetCheckConfig, "load", return_value=cfg_data):
            user = NetCheckConfig.get_smtp_user()
        assert user == "keyring@example.com"

    def test_get_smtp_to_config_fallback(self):
        # Keyring returns None, fall back to config.yaml
        cfg_data = {"smtp": {"to": "fallback@example.com"}}
        with patch("netcheck.utils.config._keyring_get", return_value=None) as mock_get, \
             patch.object(NetCheckConfig, "load", return_value=cfg_data):
            to = NetCheckConfig.get_smtp_to()
        assert to == "fallback@example.com"

    def test_purge_clears_secrets_and_deletes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "netcheck" / "config.yaml"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text("timeout: 5")

            with patch("builtins.input", return_value="y"), \
                 patch("netcheck.utils.config._keyring_delete") as mock_delete, \
                 patch.object(NetCheckConfig, "path", return_value=config_path):
                NetCheckConfig.purge()

            # Keyring delete called for all known services
            assert mock_delete.call_count == 5
            # Config file deleted
            assert not config_path.exists()
