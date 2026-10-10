"""
netcheck.utils.alerting
~~~~~~~~~~~~~~~~~~~~~~~

Alert dispatchers for netcheck.

Supported channels:
  - SMTP email (stdlib smtplib)
  - Slack incoming webhook
  - Generic HTTP webhook
  - Desktop notification (plyer, optional)

All dispatchers accept an AlertEvent and return a boolean success flag.
They NEVER raise — errors are caught and printed to stderr.

Usage::

    from netcheck.utils.alerting import AlertDispatcher
    from netcheck.utils.alert_state import AlertEvent
    from netcheck.utils.config import NetCheckConfig

    cfg = NetCheckConfig.load()
    dispatcher = AlertDispatcher(cfg)
    dispatcher.dispatch(event)
"""

from __future__ import annotations

import json
import smtplib
import sys
import traceback
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

from netcheck.utils.alert_state import AlertEvent

# ---------------------------------------------------------------------------
# Alert message formatting
# ---------------------------------------------------------------------------

def _format_subject(event: AlertEvent) -> str:
    icon = "✅" if event.new_state == "UP" else "❌"
    return f"{icon} NetCheck ALERT: {event.target} is {event.new_state}"


def _format_body_plain(event: AlertEvent) -> str:
    lines = [
        "NetCheck Alert",
        "=============",
        f"Target  : {event.target}",
        f"Status  : {event.old_state} → {event.new_state}",
        f"Time    : {event.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"Checks  : {event.consecutive} consecutive",
    ]
    if event.last_error:
        lines.append(f"Error   : {event.last_error}")
    return "\n".join(lines)


def _format_slack_payload(event: AlertEvent) -> dict[str, Any]:
    color = "good" if event.new_state == "UP" else "danger"
    icon = "✅" if event.new_state == "UP" else "❌"
    return {
        "text": f"{icon} *{event.target}* is *{event.new_state}*",
        "attachments": [
            {
                "color": color,
                "fields": [
                    {"title": "Target", "value": event.target, "short": True},
                    {
                        "title": "State Change",
                        "value": f"{event.old_state} → {event.new_state}",
                        "short": True,
                    },
                    {
                        "title": "Time",
                        "value": event.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
                        "short": True,
                    },
                    {
                        "title": "Consecutive Checks",
                        "value": str(event.consecutive),
                        "short": True,
                    },
                ]
                + (
                    [{"title": "Error", "value": event.last_error, "short": False}]
                    if event.last_error
                    else []
                ),
            }
        ],
    }


# ---------------------------------------------------------------------------
# Individual dispatchers
# ---------------------------------------------------------------------------

def send_email_alert(event: AlertEvent, smtp_cfg: dict) -> bool:
    """Send an SMTP email alert. Returns True on success."""
    from netcheck.utils.config import NetCheckConfig

    host = smtp_cfg.get("host", "")
    port = int(smtp_cfg.get("port", 587))
    user = NetCheckConfig.get_smtp_user()
    to_addr = NetCheckConfig.get_smtp_to()
    use_tls = smtp_cfg.get("use_tls", True)

    if not all([host, user, to_addr]):
        return False

    # Retrieve password from keychain
    password = NetCheckConfig.get_password("email") or ""

    subject = _format_subject(event)
    body = _format_body_plain(event)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = user
    msg.attach(MIMEText(body, "plain"))

    try:
        smtp = smtplib.SMTP(host, port)
        if use_tls:
            smtp.starttls()
        if user and password:
            smtp.login(user, password)

        # Support comma-separated list of recipient emails
        recipients = [email.strip() for email in to_addr.split(",") if email.strip()]
        for email in recipients:
            if "To" in msg:
                del msg["To"]
            msg["To"] = email
            smtp.send_message(msg)

        smtp.quit()
        return True
    except Exception as exc:
        err_msg = f"[alert] Email alert failed: {exc}"
        print(err_msg, file=sys.stderr)
        try:
            from netcheck.cli.watch import add_watch_log
            add_watch_log(err_msg)
        except ImportError:
            pass
        traceback.print_exc(file=sys.stderr)
        return False


def send_slack_alert(event: AlertEvent, webhook_url: str) -> bool:
    """Send a Slack incoming webhook alert. Returns True on success."""
    if not webhook_url:
        return False
    payload = _format_slack_payload(event)
    return _post_json(webhook_url, payload)


def send_webhook_alert(
    event: AlertEvent,
    url: str,
    token: Optional[str] = None,
) -> bool:
    """Send a generic JSON webhook alert. Returns True on success."""
    if not url:
        return False
    payload = {
        "target": event.target,
        "old_state": event.old_state,
        "new_state": event.new_state,
        "timestamp": event.timestamp.isoformat(),
        "consecutive": event.consecutive,
        "error": event.last_error,
    }
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return _post_json(url, payload, headers=headers)


def send_desktop_notification(event: AlertEvent) -> bool:
    """
    Send a desktop notification using the best available backend.

    Backend priority:
      1. plyer   (cross-platform, optional pip package)
      2. Windows PowerShell WinRT toast  (Win 10/11, no extra deps)
      3. macOS   osascript               (built-in)
      4. Linux   notify-send             (libnotify, usually pre-installed)

    Returns True if at least one backend succeeded.
    """
    title = _format_subject(event)
    message = (
        f"{event.target}  |  {event.old_state} \u2192 {event.new_state}\n"
        f"{event.timestamp.strftime('%H:%M:%S UTC')}"
    )
    if event.last_error:
        message += f"\n{event.last_error[:120]}"

    # ── 1. plyer ──────────────────────────────────────────────────────────
    try:
        from plyer import notification as _plyer  # type: ignore
        _plyer.notify(
            title=title,
            message=message,
            app_name="NetCheck",
            timeout=10,
        )
        return True
    except ImportError:
        pass  # not installed — try native backends
    except Exception as exc:
        print(f"[netcheck] plyer notification failed: {exc}", file=sys.stderr)

    # ── 2. Windows — PowerShell WinRT toast (Win 10 / 11) ─────────────────
    if sys.platform == "win32":
        return _windows_toast(title, message)

    # ── 3. macOS — osascript ───────────────────────────────────────────────
    if sys.platform == "darwin":
        return _macos_notify(title, message)

    # ── 4. Linux — notify-send ────────────────────────────────────────────
    return _linux_notify(title, message)


# ---------------------------------------------------------------------------
# Native notification helpers
# ---------------------------------------------------------------------------

def _windows_toast(title: str, message: str) -> bool:
    """
    Show a Windows 10/11 Action Center toast via PowerShell WinRT.

    No extra Python packages required — uses the Windows Runtime APIs
    that ship with every Win 10/11 installation.
    """
    import subprocess
    import textwrap

    # Escape single-quotes for PowerShell string literals
    t = title.replace("'", "''")
    m = message.replace("'", "''")

    ps_script = textwrap.dedent(f"""\
        $ErrorActionPreference = 'Stop'
        try {{
            [void][Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime]
            [void][Windows.Data.Xml.Dom.XmlDocument,Windows.Data.Xml.Dom.XmlDocument,ContentType=WindowsRuntime]
            $tpl  = [Windows.UI.Notifications.ToastTemplateType]::ToastText02
            $xml  = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($tpl)
            $xml.GetElementsByTagName('text')[0].AppendChild($xml.CreateTextNode('{t}')) | Out-Null
            $xml.GetElementsByTagName('text')[1].AppendChild($xml.CreateTextNode('{m}')) | Out-Null
            $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('NetCheck').Show($toast)
            exit 0
        }} catch {{
            Write-Error $_.Exception.Message
            exit 1
        }}
    """)
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True
        # WinRT failed — try balloon tip fallback (works on older Windows too)
        return _windows_balloon(title, message)
    except Exception as exc:
        print(f"[netcheck] Windows toast failed: {exc}", file=sys.stderr)
        return _windows_balloon(title, message)


def _windows_balloon(title: str, message: str) -> bool:
    """
    Fallback: show a taskbar balloon tip via PowerShell System.Windows.Forms.
    Works on Windows 7+ and does not need a registered app ID.
    """
    import subprocess
    import textwrap

    t = title.replace("'", "''")
    m = message.replace("'", "''").replace("\n", " | ")

    ps_script = textwrap.dedent(f"""\
        Add-Type -AssemblyName System.Windows.Forms
        $n = New-Object System.Windows.Forms.NotifyIcon
        $n.Icon = [System.Drawing.SystemIcons]::Information
        $n.Visible = $true
        $n.BalloonTipTitle = '{t}'
        $n.BalloonTipText  = '{m}'
        $n.BalloonTipIcon  = 'Info'
        $n.ShowBalloonTip(8000)
        Start-Sleep -Milliseconds 8500
        $n.Dispose()
    """)
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
             "-Command", ps_script],
        )
        return True
    except Exception as exc:
        print(f"[netcheck] Windows balloon tip failed: {exc}", file=sys.stderr)
        return False


def _macos_notify(title: str, message: str) -> bool:
    """Send a macOS notification via osascript (no deps)."""
    import subprocess

    body = message.replace('"', '\\"').replace("\n", " | ")
    t = title.replace('"', '\\"')
    script = f'display notification "{body}" with title "{t}"'
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except Exception as exc:
        print(f"[netcheck] macOS notification failed: {exc}", file=sys.stderr)
        return False


def _linux_notify(title: str, message: str) -> bool:
    """Send a Linux desktop notification via notify-send (libnotify)."""
    import shutil
    import subprocess

    if not shutil.which("notify-send"):
        print(
            "[netcheck] Desktop notification skipped: 'notify-send' not found.\n"
            "  Install with: sudo apt install libnotify-bin  (Debian/Ubuntu)\n"
            "               sudo dnf install libnotify       (Fedora)",
            file=sys.stderr,
        )
        return False
    body = message.replace("\n", " | ")
    try:
        result = subprocess.run(
            ["notify-send", "--urgency=normal", "--expire-time=8000",
             "--app-name=NetCheck", title, body],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except Exception as exc:
        print(f"[netcheck] notify-send failed: {exc}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# AlertDispatcher
# ---------------------------------------------------------------------------

class AlertDispatcher:
    """
    Unified alert dispatcher. Reads channel config from the netcheck
    config dict and fires configured channels.

    Usage::

        dispatcher = AlertDispatcher(cfg)
        dispatcher.dispatch(event)                   # all channels
        dispatcher.dispatch(event, channels=["slack"]) # only Slack
    """

    def __init__(self, cfg: dict[str, Any]) -> None:
        self._cfg = cfg

    def dispatch(
        self,
        event: AlertEvent,
        channels: Optional[list[str]] = None,
    ) -> dict[str, bool]:
        """
        Fire alert channels.

        Parameters
        ----------
        event:
            The AlertEvent to dispatch.
        channels:
            Optional list of channel names ("email", "slack", "webhook",
            "desktop") to restrict dispatch to. If None or empty, all
            configured channels are fired.

        Returns a dict of channel → success flag.
        """
        from netcheck.utils.config import NetCheckConfig

        results: dict[str, bool] = {}
        _all = not channels  # True → fire everything

        # ── Email ──────────────────────────────────────────────────────────
        if _all or "email" in channels:
            smtp_cfg = self._cfg.get("smtp", {})
            host = smtp_cfg.get("host", "")
            to_addr = NetCheckConfig.get_smtp_to()
            if host and to_addr:
                results["email"] = send_email_alert(event, smtp_cfg)
            elif not _all:
                err_msg = "[netcheck] Email alert skipped: SMTP host or recipient not configured."
                print(err_msg, file=sys.stderr)
                try:
                    from netcheck.cli.watch import add_watch_log
                    add_watch_log(err_msg)
                except ImportError:
                    pass
                results["email"] = False

        # ── Slack ──────────────────────────────────────────────────────────
        if _all or "slack" in channels:
            # Prefer keyring; fall back to config.yaml for migration compat.
            slack_url = NetCheckConfig.get_slack_webhook()
            if not slack_url:
                slack_url = self._cfg.get("slack", {}).get("webhook_url", "")
            if slack_url:
                results["slack"] = send_slack_alert(event, slack_url)
            elif not _all:
                err_msg = (
                    "[netcheck] Slack alert skipped: no webhook URL configured.\n"
                    "  Run: netcheck config set-password slack"
                )
                print(err_msg, file=sys.stderr)
                try:
                    from netcheck.cli.watch import add_watch_log
                    add_watch_log("[netcheck] Slack alert skipped: no webhook URL configured.")
                except ImportError:
                    pass
                results["slack"] = False

        # ── Generic webhook ────────────────────────────────────────────────
        if _all or "webhook" in channels:
            webhook = self._cfg.get("webhook", {})
            url = webhook.get("url", "")
            if url:
                token = NetCheckConfig.get_webhook_token() or webhook.get("token", "")
                results["webhook"] = send_webhook_alert(event, url, token)
            elif not _all:
                err_msg = "[netcheck] Webhook alert skipped: no webhook URL configured."
                print(err_msg, file=sys.stderr)
                try:
                    from netcheck.cli.watch import add_watch_log
                    add_watch_log(err_msg)
                except ImportError:
                    pass
                results["webhook"] = False

        # ── Desktop ────────────────────────────────────────────────────────
        if _all or "desktop" in channels:
            results["desktop"] = send_desktop_notification(event)

        return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _post_json(
    url: str,
    payload: dict,
    headers: Optional[dict] = None,
    timeout: int = 10,
) -> bool:
    """HTTP POST JSON payload to *url*. Returns True on 2xx response."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            **(headers or {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except Exception as exc:
        err_msg = f"[alert] Webhook POST to {url!r} failed: {exc}"
        print(err_msg, file=sys.stderr)
        try:
            from netcheck.cli.watch import add_watch_log
            add_watch_log(err_msg)
        except ImportError:
            pass
        traceback.print_exc(file=sys.stderr)
        return False
