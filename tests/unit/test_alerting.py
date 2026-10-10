"""
tests/unit/test_alerting.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for:
  - netcheck.utils.alert_state.AlertStateManager
  - netcheck.utils.alerting.AlertDispatcher (send channels)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from netcheck.utils.alert_state import AlertEvent, AlertStateManager, TargetState


# ===========================================================================
# AlertStateManager
# ===========================================================================

class TestAlertStateManagerBasic:
    def test_new_target_state_is_unknown(self):
        mgr = AlertStateManager(flap_threshold=1)
        assert mgr.get_state("example.com:443") is None

    def test_first_success_transitions_to_up(self):
        mgr = AlertStateManager(flap_threshold=1)
        event = mgr.update("example.com:443", success=True)
        assert event is None
        assert mgr.get_state("example.com:443") == "UP"

    def test_first_failure_transitions_to_down(self):
        mgr = AlertStateManager(flap_threshold=1)
        event = mgr.update("example.com:443", success=False)
        assert event is None
        assert mgr.get_state("example.com:443") == "DOWN"

    def test_up_to_down_transition(self):
        mgr = AlertStateManager(flap_threshold=1)
        mgr.update("h:80", success=True)
        event = mgr.update("h:80", success=False)
        assert event is not None
        assert event.old_state == "UP"
        assert event.new_state == "DOWN"

    def test_down_to_up_transition(self):
        mgr = AlertStateManager(flap_threshold=1)
        mgr.update("h:80", success=False)
        event = mgr.update("h:80", success=True)
        assert event is not None
        assert event.new_state == "UP"

    def test_no_event_on_repeated_success(self):
        mgr = AlertStateManager(flap_threshold=1)
        mgr.update("h:80", success=True)
        event = mgr.update("h:80", success=True)
        assert event is None

    def test_no_event_on_repeated_failure(self):
        mgr = AlertStateManager(flap_threshold=1)
        mgr.update("h:80", success=False)
        event = mgr.update("h:80", success=False)
        assert event is None

    def test_error_message_in_down_event(self):
        mgr = AlertStateManager(flap_threshold=1)
        mgr.update("h:80", success=True)
        event = mgr.update("h:80", success=False, error="Connection refused")
        assert event is not None
        assert event.last_error == "Connection refused"

    def test_up_event_has_no_error(self):
        mgr = AlertStateManager(flap_threshold=1)
        mgr.update("h:80", success=False)
        event = mgr.update("h:80", success=True)
        assert event is not None
        assert event.last_error is None


class TestAlertStateManagerFlapDetection:
    def test_flap_threshold_2_requires_2_failures(self):
        mgr = AlertStateManager(flap_threshold=2)
        mgr.update("h:80", success=True)  # → UP
        e1 = mgr.update("h:80", success=False)  # 1 failure → no transition
        assert e1 is None
        e2 = mgr.update("h:80", success=False)  # 2 failures → DOWN
        assert e2 is not None
        assert e2.new_state == "DOWN"

    def test_flap_threshold_3_requires_3_successes(self):
        mgr = AlertStateManager(flap_threshold=3)
        mgr.update("h:80", success=False)  # → DOWN
        mgr.update("h:80", success=True)
        mgr.update("h:80", success=True)
        e = mgr.update("h:80", success=True)  # 3rd success → UP
        assert e is not None
        assert e.new_state == "UP"

    def test_reset_consecutive_on_reversal(self):
        """A failure interrupts a success streak — threshold resets."""
        mgr = AlertStateManager(flap_threshold=3)
        mgr.update("h:80", success=False)  # DOWN
        mgr.update("h:80", success=True)
        mgr.update("h:80", success=False)  # break the streak
        mgr.update("h:80", success=True)
        mgr.update("h:80", success=True)
        e = mgr.update("h:80", success=True)  # 3 consecutive now → UP
        assert e is not None
        assert e.new_state == "UP"

    def test_invalid_flap_threshold_raises(self):
        with pytest.raises(ValueError):
            AlertStateManager(flap_threshold=0)

    def test_consecutive_count_in_event(self):
        mgr = AlertStateManager(flap_threshold=2)
        mgr.update("h:80", success=True)
        mgr.update("h:80", success=False)
        e = mgr.update("h:80", success=False)
        assert e is not None
        assert e.consecutive == 2


class TestAlertStateManagerCooldown:
    def test_cooldown_suppresses_repeated_alert(self):
        mgr = AlertStateManager(flap_threshold=1, cooldown_seconds=300)
        mgr.update("h:80", success=True)    # UP
        mgr.update("h:80", success=False)   # DOWN → alert fires
        mgr.update("h:80", success=True)    # UP but in cooldown → None
        e = mgr.update("h:80", success=False)  # back DOWN but in cooldown
        assert e is None

    def test_cooldown_zero_always_fires(self):
        mgr = AlertStateManager(flap_threshold=1, cooldown_seconds=0)
        mgr.update("h:80", success=True)
        mgr.update("h:80", success=False)   # DOWN
        e = mgr.update("h:80", success=True)   # UP immediately
        assert e is not None

    def test_directional_cooldown(self):
        mgr = AlertStateManager(flap_threshold=1, cooldown_seconds=300)
        mgr.update("h:80", success=True)    # Baseline: UP

        # DOWN event: should fire
        e1 = mgr.update("h:80", success=False)
        assert e1 is not None
        assert e1.new_state == "DOWN"

        # UP recovery event: should fire (even though it's within 300s of DOWN)
        e2 = mgr.update("h:80", success=True)
        assert e2 is not None
        assert e2.new_state == "UP"

        # Second DOWN event: should be suppressed by DOWN cooldown (within 300s)
        e3 = mgr.update("h:80", success=False)
        assert e3 is None

    def test_alert_on_filter(self):
        mgr = AlertStateManager(flap_threshold=1)
        mgr.update("h:80", success=True)    # Baseline: UP

        # With alert_on="up", DOWN transition is ignored
        e1 = mgr.update("h:80", success=False, alert_on="up")
        assert e1 is None
        assert mgr.get_state("h:80") == "DOWN"

        # Now transition back UP: with alert_on="up", this should fire
        e2 = mgr.update("h:80", success=True, alert_on="up")
        assert e2 is not None
        assert e2.new_state == "UP"


class TestAlertStateManagerStats:
    def test_get_all_states(self):
        mgr = AlertStateManager(flap_threshold=1)
        mgr.update("a:80", success=True)
        mgr.update("b:443", success=False)
        states = mgr.get_all_states()
        assert states["a:80"] == "UP"
        assert states["b:443"] == "DOWN"

    def test_get_stats_uptime_100(self):
        mgr = AlertStateManager(flap_threshold=1)
        mgr.update("h:80", success=True)
        mgr.update("h:80", success=True)
        stats = mgr.get_stats("h:80")
        assert stats is not None
        assert stats["total_checks"] == 2
        assert stats["total_failures"] == 0
        assert stats["uptime_pct"] == pytest.approx(100.0)

    def test_get_stats_uptime_50(self):
        mgr = AlertStateManager(flap_threshold=1)
        mgr.update("h:80", success=True)
        mgr.update("h:80", success=False)
        stats = mgr.get_stats("h:80")
        assert stats is not None
        assert stats["uptime_pct"] == pytest.approx(50.0)

    def test_get_stats_returns_none_for_unknown(self):
        mgr = AlertStateManager()
        assert mgr.get_stats("never.seen:80") is None

    def test_reset_removes_target(self):
        mgr = AlertStateManager(flap_threshold=1)
        mgr.update("h:80", success=True)
        mgr.reset("h:80")
        assert mgr.get_state("h:80") is None

    def test_reset_all(self):
        mgr = AlertStateManager(flap_threshold=1)
        mgr.update("a:80", success=True)
        mgr.update("b:80", success=False)
        mgr.reset_all()
        assert mgr.get_all_states() == {}


# ===========================================================================
# AlertEvent dataclass
# ===========================================================================

class TestAlertEvent:
    def test_event_fields(self):
        now = datetime.now(timezone.utc)
        event = AlertEvent(
            target="host:443",
            old_state="UP",
            new_state="DOWN",
            timestamp=now,
            consecutive=2,
            last_error="timeout",
        )
        assert event.target == "host:443"
        assert event.old_state == "UP"
        assert event.new_state == "DOWN"
        assert event.consecutive == 2
        assert event.last_error == "timeout"

    def test_event_last_error_optional(self):
        now = datetime.now(timezone.utc)
        event = AlertEvent(
            target="h:80",
            old_state="UNKNOWN",
            new_state="UP",
            timestamp=now,
            consecutive=1,
        )
        assert event.last_error is None


# ===========================================================================
# AlertDispatcher (channel dispatch)
# ===========================================================================

class TestAlertDispatcher:
    @pytest.fixture(autouse=True)
    def mock_keyring_env(self):
        with patch("netcheck.utils.config.NetCheckConfig.get_slack_webhook", return_value=""), \
             patch("netcheck.utils.config.NetCheckConfig.get_webhook_token", return_value=""), \
             patch("netcheck.utils.config.NetCheckConfig.get_smtp_user", return_value=""), \
             patch("netcheck.utils.config.NetCheckConfig.get_smtp_to", return_value=""):
            yield

    def _make_event(self) -> AlertEvent:
        return AlertEvent(
            target="example.com:443",
            old_state="UP",
            new_state="DOWN",
            timestamp=datetime.now(timezone.utc),
            consecutive=2,
            last_error="Connection refused",
        )

    def test_dispatch_returns_dict(self):
        from netcheck.utils.alerting import AlertDispatcher
        dispatcher = AlertDispatcher({})
        event = self._make_event()
        result = dispatcher.dispatch(event)
        assert isinstance(result, dict)

    def test_dispatch_no_channels_configured(self):
        from netcheck.utils.alerting import AlertDispatcher
        dispatcher = AlertDispatcher({})
        result = dispatcher.dispatch(self._make_event())
        # email/slack/webhook not configured — only desktop attempt
        assert "email" not in result
        assert "slack" not in result
        assert "webhook" not in result

    def test_dispatch_calls_slack_when_configured(self):
        from netcheck.utils.alerting import AlertDispatcher, send_slack_alert
        cfg = {"slack": {"webhook_url": "https://hooks.slack.com/test"}}
        dispatcher = AlertDispatcher(cfg)
        with patch("netcheck.utils.alerting.send_slack_alert", return_value=True) as mock_slack:
            result = dispatcher.dispatch(self._make_event())
        mock_slack.assert_called_once()
        assert result.get("slack") is True

    def test_dispatch_calls_webhook_when_configured(self):
        from netcheck.utils.alerting import AlertDispatcher
        cfg = {"webhook": {"url": "https://webhook.example.com/notify", "token": "tok"}}
        dispatcher = AlertDispatcher(cfg)
        with patch("netcheck.utils.alerting.send_webhook_alert", return_value=True) as mock_wh:
            result = dispatcher.dispatch(self._make_event())
        mock_wh.assert_called_once()
        assert result.get("webhook") is True

    def test_send_slack_alert_posts_json(self):
        from netcheck.utils.alerting import send_slack_alert
        with patch("netcheck.utils.alerting._post_json", return_value=True) as mock_post:
            result = send_slack_alert(self._make_event(), "https://hooks.slack.com/abc")
        mock_post.assert_called_once()
        payload = mock_post.call_args[0][1]
        assert "text" in payload
        assert "DOWN" in payload["text"]

    def test_send_webhook_alert_includes_token(self):
        from netcheck.utils.alerting import send_webhook_alert
        with patch("netcheck.utils.alerting._post_json", return_value=True) as mock_post:
            send_webhook_alert(self._make_event(), "https://wh.example.com", token="mytoken")
        headers = mock_post.call_args[1].get("headers", {})
        assert headers.get("Authorization") == "Bearer mytoken"

    def test_send_slack_alert_empty_url_returns_false(self):
        from netcheck.utils.alerting import send_slack_alert
        result = send_slack_alert(self._make_event(), "")
        assert result is False

    def test_send_webhook_alert_empty_url_returns_false(self):
        from netcheck.utils.alerting import send_webhook_alert
        result = send_webhook_alert(self._make_event(), "")
        assert result is False

    def test_send_email_alert_no_host_returns_false(self):
        from netcheck.utils.alerting import send_email_alert
        result = send_email_alert(self._make_event(), {"host": "", "user": "u", "to": "t"})
        assert result is False
