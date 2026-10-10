import platform
import re
import subprocess
import time
from typing import Any, Dict

from netcheck.utils.normalize import normalize_host


def ping_host(raw_target: str, count: int = 4, timeout: float = 2.0) -> Dict[str, Any]:
    """
    Pings a host using the system ping utility.
    Parses RTT statistics, packets transmitted, and loss percentage.
    """
    host = normalize_host(raw_target)
    if not host:
        return {
            "type": "ping",
            "target": raw_target,
            "status": "FAILED",
            "latency_ms": 0.0,
            "success": False,
            "error": "Empty ping target",
            "metadata": {}
        }


    result = {
        "type": "ping",
        "target": raw_target,
        "status": "FAILED",
        "latency_ms": None,
        "success": False,
        "error": None,
        "metadata": {
            "host": host,
            "packets_sent": count,
            "packets_received": 0,
            "packet_loss_pct": 100.0,
            "min_rtt_ms": None,
            "avg_rtt_ms": None,
            "max_rtt_ms": None
        }
    }


    plat = platform.system().lower()

    # Configure parameters based on operating system
    if plat == "windows":
        cmd = ["ping", "-n", str(count), "-w", str(int(timeout * 1000)), host]
    elif plat == "darwin":
        cmd = ["ping", "-c", str(count), "-t", str(int(timeout)), host]
    else:
        cmd = ["ping", "-c", str(count), "-W", str(int(timeout)), host]

    start_time = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout * count + 2.0
        )
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        result["latency_ms"] = round(duration_ms, 2)

        # Capture raw ping stdout and stderr
        result["metadata"]["ping_output"] = proc.stdout + (("\n" + proc.stderr) if proc.stderr else "")

        if proc.returncode == 0:
            result["success"] = True
            result["status"] = "SUCCESS"

            stdout = proc.stdout

            # Parse packet loss and received count
            # Examples:
            # Linux: 4 packets transmitted, 4 received, 0% packet loss, time 3004ms
            # Windows: Packets: Sent = 4, Received = 4, Lost = 0 (0% loss)
            received_match = re.search(r"(\d+)\s+received", stdout, re.IGNORECASE) or re.search(r"Received\s*=\s*(\d+)", stdout, re.IGNORECASE)
            loss_match = re.search(r"(\d+)%\s+packet\s+loss", stdout, re.IGNORECASE) or re.search(r"Lost\s*=\s*\d+\s*\((\d+)%\s*loss\)", stdout, re.IGNORECASE)

            if received_match:
                result["metadata"]["packets_received"] = int(received_match.group(1))
            if loss_match:
                result["metadata"]["packet_loss_pct"] = float(loss_match.group(1))

            # Parse RTT stats
            # Linux: rtt min/avg/max/mdev = 1.234/1.567/1.890/0.234 ms
            # Windows: Minimum = 1ms, Maximum = 3ms, Average = 2ms
            rtt_linux = re.search(r"rtt\s+min/avg/max/mdev\s*=\s*([\d\.]+)/([\d\.]+)/([\d\.]+)", stdout, re.IGNORECASE)
            rtt_windows = re.search(r"Minimum\s*=\s*(\d+)ms,\s*Maximum\s*=\s*(\d+)ms,\s*Average\s*=\s*(\d+)ms", stdout, re.IGNORECASE)

            if rtt_linux:
                result["metadata"]["min_rtt_ms"] = float(rtt_linux.group(1))
                result["metadata"]["avg_rtt_ms"] = float(rtt_linux.group(2))
                result["metadata"]["max_rtt_ms"] = float(rtt_linux.group(3))
            elif rtt_windows:
                result["metadata"]["min_rtt_ms"] = float(rtt_windows.group(1))
                result["metadata"]["max_rtt_ms"] = float(rtt_windows.group(2))
                result["metadata"]["avg_rtt_ms"] = float(rtt_windows.group(3))
            else:
                # Fallback to general estimation
                result["metadata"]["avg_rtt_ms"] = round(duration_ms / count, 2)
        else:
            stderr_cleaned = proc.stderr.strip()
            result["error"] = f"Ping failed (exit code {proc.returncode})"
            if stderr_cleaned:
                result["error"] += f": {stderr_cleaned}"
            if "permission" in stdout.lower() or "permission" in stderr_cleaned.lower() or proc.returncode == 126:
                result["error"] += " (Check snap permissions or try connecting snap network-observe plug)"
    except subprocess.TimeoutExpired:
        result["error"] = "Ping process timed out"
    except Exception as e:
        result["error"] = str(e)

    return result
