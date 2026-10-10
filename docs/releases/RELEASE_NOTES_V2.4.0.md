# Release Notes — NetCheck v2.4.0

**Release Date:** 2026-08-26
**Type:** Feature — Security, Alerting Intelligence & Watch Mode Reliability

---

## Overview

v2.4.0 is a security and reliability release focused on the watch-mode alerting engine.
It moves all sensitive credentials (SMTP passwords, Slack webhooks, Bearer tokens) to the OS
keychain (never written to disk), adds directional alert cooldowns, an `--alert-on` filter,
native desktop notifications on Windows/macOS/Linux, a `config purge` command for complete
credential wipe, a `config test-alert` command for instant channel verification, and a rolling
in-window alert log so history is never overwritten by the terminal refresh.

---

## What's New

### 1. OS Keychain Credential Storage

All sensitive alerting credentials are now stored in the OS credential manager
(Windows Credential Manager, macOS Keychain, or GNOME Keyring / KWallet on Linux) instead
of plain-text `config.yaml`.

```bash
# Store credentials securely
netcheck config set-password email      # SMTP app-password
netcheck config set-password smtp_user  # SMTP sender address
netcheck config set-password smtp_to    # Recipient address(es)
netcheck config set-password slack      # Slack incoming webhook URL
netcheck config set-password webhook    # Generic webhook bearer token

# Remove individual credential
netcheck config clear-password email
```

- The `config.yaml` file no longer stores any secret values.
- `netcheck config show` displays masked previews (e.g. `se...@gmail.com`) alongside stored
  YAML values so you can verify what is set without exposing secrets.
- Backward-compatible: if a keyring entry is absent, the tool falls back to the YAML value.

---

### 2. `config purge` — Full Secure Wipe

```bash
netcheck config purge
```

Deletes `config.yaml` **and** removes all five keyring secrets in a single atomic operation.
Useful before decommissioning a machine or rotating all credentials.

---

### 3. `config test-alert` — Instant Channel Verification

```bash
netcheck config test-alert email      # Fire a test SMTP email now
netcheck config test-alert slack      # Fire a test Slack message now
netcheck config test-alert desktop    # Trigger a test desktop notification
netcheck config test-alert webhook    # POST a test webhook payload
```

Sends a real alert through the specified channel immediately, without needing to spin up a
watch loop or toggle a service. Reports SUCCESS or FAILED with a full error trace.

---

### 4. Directional Alert Cooldowns

Cooldown timers are now tracked **independently** per direction (UP and DOWN), so recovering
and re-failing a service each generate their own alert after the cooldown expires.

```bash
# Alert every 5 minutes per direction at most
netcheck tcp api.example.com 443 -w --alert email --alert-cooldown 300
```

Previously, a single shared timer could suppress a recovery alert if a DOWN alert had just
fired. Now UP and DOWN timers are decoupled.

---

### 5. `--alert-on` Trigger Filter

```bash
# Only alert when a target goes DOWN (suppress recovery notifications)
netcheck tcp api.example.com 443 -w --alert slack --alert-on down

# Alert on any state change (default)
netcheck dns google.com -w --alert email --alert-on any

# Only alert when a target recovers (UP)
netcheck http https://api.example.com -w --alert desktop --alert-on up
```

| Value | Behaviour |
|-------|-----------|
| `any` (default) | Alert on every UP to DOWN transition |
| `down` | Alert only when state transitions to DOWN |
| `up` | Alert only when state transitions to UP (recovery) |

---

### 6. Native Desktop Notifications

`--alert desktop` now triggers a native OS notification on all platforms:

| Platform | Mechanism |
|----------|-----------|
| Windows 10/11 | WinRT Action Center toast via PowerShell; falls back to taskbar balloon tip |
| macOS | `osascript` notification |
| Linux | `notify-send` |
| Any (optional) | `plyer` library if installed |

```bash
netcheck tcp localhost 8000 -w --alert desktop --interval 2
```

---

### 7. Watch Mode Rolling Alert Log

The watch terminal window now displays a persistent **Recent Alerts & Logs** panel at the
bottom. Up to 8 entries are kept in a rolling buffer so that screen refreshes no longer erase
alert history.

```
RECENT WATCH ALERTS & LOGS:
[22:40:59] [alert] localhost:8000 is DOWN (UP to DOWN)
[22:41:02] [alert] Email sent to: user@example.com
```

---

### 8. Watch Loop Resilience

Subcommands (e.g. `traceroute`) that call `sys.exit()` internally no longer terminate the
watch loop. The `SystemExit` is caught and the loop continues on the next interval.

---

### 9. SMTP Reliability Fix

The SMTP dispatch was rewritten to match a proven reference implementation:

- Uses `smtp.send_message()` instead of `smtp.sendmail()` for robust MIME compliance.
- Calls `del msg["To"]` before each recipient to prevent header accumulation when sending
  to multiple addresses in a single session.
- Reuses a single SMTP connection across all recipients for efficiency.

---

## Breaking Changes

None. All existing CLI flags, subcommands, and config file formats remain backward-compatible.
Secrets previously stored in `config.yaml` are still read as a fallback if no keyring entry
exists.

---

## Files Added / Changed

| File | Change |
|------|--------|
| `netcheck/utils/alerting.py` | OS keychain credential getters; SMTP rewrite; desktop notification multi-backend engine; AlertDispatcher wired to watch log |
| `netcheck/utils/config.py` | `get_smtp_user()`, `get_smtp_to()`, `get_password('slack')`, `get_password('webhook')`; `purge()`; enhanced `show()` with masked keyring preview; init_wizard Gmail defaults |
| `netcheck/utils/alert_state.py` | Directional `last_down_alert_time` / `last_up_alert_time` per TargetState; `alert_on` filter in `AlertStateManager.should_alert()` |
| `netcheck/cli/watch.py` | Rolling `_watch_logs` buffer (max 8); `add_watch_log()`; SystemExit catch in watch loop |
| `netcheck/cli/args.py` | `--alert-on {any,down,up}` flag; `--alert-cooldown` default reduced to 60s |
| `netcheck/cli/main.py` | Legacy single-dash option normalisation (`-tcp`, `-udp`, `-mtr`, etc.) |
| `netcheck/cli/subcommands.py` | `config purge` action; `config test-alert <channel>` action; alert transitions piped to watch log |
| `tests/unit/test_alerting.py` | 6 new tests: directional cooldown, alert_on filter, keyring getter mocks |
| `tests/unit/test_config.py` | 8 new tests: purge(), show() keyring display, SMTP getters |
| `docs/releases/RELEASE_NOTES_V2.4.0.md` | New file |
| `CHANGELOG.md` | v2.4.0 entry added |

---

## Upgrade Guide

### Pip
```bash
pip install --upgrade netcheckx
```

### Snap (Linux)
```bash
sudo snap refresh netcheck
```

### Debian package
```bash
sudo dpkg -i netcheck_2.4.0_amd64.deb
```

### After upgrading — migrate credentials to keychain
```bash
netcheck config set-password email
netcheck config set-password smtp_user
netcheck config set-password smtp_to
netcheck config set-password slack
netcheck config set-password webhook
netcheck config show
netcheck config test-alert email
```

---

## Release Artefacts

| Artefact | Platform |
|----------|----------|
| `netcheckx-2.4.0-py3-none-any.whl` | PyPI / All platforms |
| `netcheckx-2.4.0.tar.gz` | Source distribution (PyPI) |
| `netcheck_2.4.0_amd64.deb` | Debian / Ubuntu |
| `netcheck_2.4.0_amd64.snap` | All Linux (Snap Store) |
| `netcheck-2.4.0-setup.exe` | Windows NSIS Installer |
| `netcheck-2.4.0.nupkg` | Windows Chocolatey |

---

## Full Changelog

See [CHANGELOG.md](../../CHANGELOG.md) for the complete history.
