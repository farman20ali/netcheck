"""
netcheck.utils.alert_state
~~~~~~~~~~~~~~~~~~~~~~~~~~

State machine for tracking UP/DOWN transitions of monitored targets.

State flow:
  UNKNOWN → UP (first success)
  UNKNOWN → DOWN (first failure)
  UP → DOWN (after flap_threshold consecutive failures)
  DOWN → UP (after flap_threshold consecutive successes)

Flap detection: state only changes after `flap_threshold` consecutive
transitions to prevent alert storms from transient errors.

Cooldown: once an alert fires, no further alert fires for that target
for `cooldown_seconds`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AlertEvent:
    """Describes a state transition that should trigger an alert."""
    target: str          # "host:port" or "https://..."
    old_state: str       # UNKNOWN / UP / DOWN
    new_state: str       # UP / DOWN
    timestamp: datetime
    consecutive: int     # how many checks caused this transition
    last_error: Optional[str] = None


@dataclass
class TargetState:
    """Internal per-target state tracked by AlertStateManager."""
    current: str = "UNKNOWN"  # UNKNOWN / UP / DOWN
    consecutive_up: int = 0
    consecutive_down: int = 0
    last_alert_time: Optional[datetime] = None        # legacy – kept for compat
    last_down_alert_time: Optional[datetime] = None   # cooldown for DOWN events
    last_up_alert_time: Optional[datetime] = None     # cooldown for UP events
    last_error: Optional[str] = None
    first_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_check_time: Optional[datetime] = None
    total_checks: int = 0
    total_failures: int = 0


# ---------------------------------------------------------------------------
# State manager
# ---------------------------------------------------------------------------

class AlertStateManager:
    """
    Tracks UP/DOWN state for multiple targets and emits AlertEvents on
    state transitions, with flap detection and cooldown support.

    Usage::

        mgr = AlertStateManager(flap_threshold=2, cooldown_seconds=300)
        event = mgr.update("google.com:443", success=True)
        if event:
            send_alert(event)
    """

    def __init__(
        self,
        flap_threshold: int = 2,
        cooldown_seconds: float = 300.0,
    ) -> None:
        if flap_threshold < 1:
            raise ValueError("flap_threshold must be >= 1")
        self.flap_threshold = flap_threshold
        self.cooldown_seconds = cooldown_seconds
        self._states: Dict[str, TargetState] = {}

    # ── Public API ─────────────────────────────────────────────────────────

    def update(
        self,
        target: str,
        success: bool,
        error: Optional[str] = None,
        alert_on: str = "any",
    ) -> Optional[AlertEvent]:
        """
        Record a check result for *target*.

        Parameters
        ----------
        target:
            Identifier string (e.g. "host:port").
        success:
            Whether the check passed.
        error:
            Optional error message on failure.
        alert_on:
            When to emit AlertEvents:

            * ``"any"``  (default) – fire on every state transition
              (DOWN and UP / recovery).
            * ``"down"`` – fire only when transitioning to DOWN.
            * ``"up"``   – fire only when transitioning to UP (recovery).

        Returns an AlertEvent if a state transition occurred AND the
        per-direction cooldown has elapsed, otherwise returns None.
        """
        now = datetime.now(timezone.utc)
        state = self._states.setdefault(target, TargetState())
        state.total_checks += 1
        state.last_check_time = now

        if not success:
            state.total_failures += 1
            state.last_error = error

        # Update consecutive counters
        if success:
            state.consecutive_up += 1
            state.consecutive_down = 0
        else:
            state.consecutive_down += 1
            state.consecutive_up = 0

        # Initial transition establishing baseline state
        if state.current == "UNKNOWN":
            state.current = "UP" if success else "DOWN"
            return None

        # Determine desired new state
        desired = self._desired_state(state)
        if desired == state.current:
            return None  # no transition

        # ── Per-direction cooldown check ───────────────────────────────────
        # We track UP and DOWN cooldowns SEPARATELY so that a DOWN→UP→DOWN
        # sequence always fires all three events, not just the first one.
        if desired == "DOWN":
            last_t = state.last_down_alert_time
        else:  # desired == "UP"
            last_t = state.last_up_alert_time

        if last_t is not None:
            elapsed = (now - last_t).total_seconds()
            if elapsed < self.cooldown_seconds:
                return None  # in cooldown for this direction — suppress

        # ── alert_on filter ────────────────────────────────────────────────
        if alert_on == "down" and desired != "DOWN":
            # Transition happened but user only wants DOWN alerts — record
            # state change silently and reset the UP cooldown clock.
            state.current = desired
            state.last_up_alert_time = now
            return None
        if alert_on == "up" and desired != "UP":
            state.current = desired
            state.last_down_alert_time = now
            return None

        # ── Emit event ─────────────────────────────────────────────────────
        event = AlertEvent(
            target=target,
            old_state=state.current,
            new_state=desired,
            timestamp=now,
            consecutive=(
                state.consecutive_up if desired == "UP" else state.consecutive_down
            ),
            last_error=state.last_error if desired == "DOWN" else None,
        )
        state.current = desired

        # Update the correct directional cooldown clock
        if desired == "DOWN":
            state.last_down_alert_time = now
        else:
            state.last_up_alert_time = now
        # Keep legacy field in sync
        state.last_alert_time = now

        return event

    def get_state(self, target: str) -> Optional[str]:
        """Return current state string for *target*, or None if unseen."""
        s = self._states.get(target)
        return s.current if s else None

    def get_all_states(self) -> Dict[str, str]:
        """Return a mapping of target → state for all known targets."""
        return {t: s.current for t, s in self._states.items()}

    def get_stats(self, target: str) -> Optional[dict]:
        """Return availability stats for *target*."""
        s = self._states.get(target)
        if not s or s.total_checks == 0:
            return None
        uptime_pct = (
            (s.total_checks - s.total_failures) / s.total_checks * 100.0
        )
        return {
            "target": target,
            "state": s.current,
            "total_checks": s.total_checks,
            "total_failures": s.total_failures,
            "uptime_pct": round(uptime_pct, 2),
            "last_error": s.last_error,
            "first_seen": s.first_seen.isoformat(),
            "last_check": s.last_check_time.isoformat() if s.last_check_time else None,
        }

    def reset(self, target: str) -> None:
        """Remove state for *target*."""
        self._states.pop(target, None)

    def reset_all(self) -> None:
        """Clear all tracked states."""
        self._states.clear()

    # ── Private ────────────────────────────────────────────────────────────

    def _desired_state(self, state: TargetState) -> str:
        if state.consecutive_up >= self.flap_threshold:
            return "UP"
        if state.consecutive_down >= self.flap_threshold:
            return "DOWN"
        return state.current  # not enough consecutive — stay put
