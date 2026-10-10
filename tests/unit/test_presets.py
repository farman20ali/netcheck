"""Tests for netcheck.data.presets."""
import pytest

from netcheck.data.presets import PRESETS, PRESET_DESCRIPTIONS, get_preset, list_presets


class TestPresetData:
    def test_presets_not_empty(self):
        assert len(PRESETS) > 0

    def test_all_presets_have_entries(self):
        for name, entries in PRESETS.items():
            assert len(entries) > 0, f"Preset {name!r} has no entries"

    def test_all_entries_have_colon(self):
        for name, entries in PRESETS.items():
            for entry in entries:
                assert ":" in entry, f"Entry {entry!r} in {name!r} has no port"

    def test_all_ports_are_valid_integers(self):
        for name, entries in PRESETS.items():
            for entry in entries:
                host, port_str = entry.rsplit(":", 1)
                port = int(port_str)
                assert 1 <= port <= 65535, f"Invalid port {port} in {name!r}"

    def test_descriptions_cover_all_presets(self):
        for name in PRESETS:
            assert name in PRESET_DESCRIPTIONS, f"No description for {name!r}"


class TestListPresets:
    def test_returns_dict(self):
        result = list_presets()
        assert isinstance(result, dict)

    def test_keys_match_presets(self):
        assert set(list_presets().keys()) == set(PRESETS.keys())

    def test_values_are_strings(self):
        for k, v in list_presets().items():
            assert isinstance(v, str), f"Description for {k!r} is not str"


class TestGetPreset:
    @pytest.mark.parametrize("name", list(PRESETS.keys()))
    def test_known_preset_returns_list(self, name):
        result = get_preset(name)
        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.parametrize("name", list(PRESETS.keys()))
    def test_entries_are_tuples(self, name):
        result = get_preset(name)
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2

    @pytest.mark.parametrize("name", list(PRESETS.keys()))
    def test_ports_in_range(self, name):
        result = get_preset(name)
        for host, port in result:
            assert 1 <= port <= 65535

    @pytest.mark.parametrize("name", list(PRESETS.keys()))
    def test_hosts_are_strings(self, name):
        result = get_preset(name)
        for host, port in result:
            assert isinstance(host, str)
            assert len(host) > 0

    def test_unknown_preset_returns_none(self):
        assert get_preset("nonexistent_preset_xyz") is None

    def test_aws_contains_ec2(self):
        aws = get_preset("aws")
        hosts = [h for h, p in aws]
        assert any("amazonaws" in h for h in hosts)

    def test_cloudflare_contains_1_1_1_1(self):
        cf = get_preset("cloudflare")
        hosts = [h for h, p in cf]
        assert "1.1.1.1" in hosts

    def test_github_port_443(self):
        gh = get_preset("github")
        ports = [p for h, p in gh]
        assert all(p == 443 for p in ports)
