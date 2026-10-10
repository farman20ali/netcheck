import platform
import re
import socket
import subprocess
import time
from typing import Any, Dict, List


def run_native_traceroute(host: str, max_hops: int = 30, timeout: float = 2.0) -> List[Dict[str, Any]]:
    """
    Attempts to perform a native Python raw socket traceroute (ICMP).
    Requires root/administrator privileges.
    """
    dest_ip = socket.gethostbyname(host)
    icmp_proto = socket.getprotobyname("icmp")

    hops = []

    for ttl in range(1, max_hops + 1):
        # Create raw sockets
        # rx socket to listen to ICMP replies
        rx = socket.socket(socket.AF_INET, socket.SOCK_RAW, icmp_proto)
        rx.settimeout(timeout)
        rx.bind(("", 0))

        # tx socket to send ICMP Echo Request with custom TTL
        tx = socket.socket(socket.AF_INET, socket.SOCK_RAW, icmp_proto)
        tx.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)

        # Build a simple ICMP Echo Request packet (Type 8, Code 0)
        # Header: Type (1 byte), Code (1 byte), Checksum (2 bytes), ID (2 bytes), Sequence (2 bytes)
        # For a simple ping, checksum can be computed or we can let OS handle it, but raw sockets usually require checksum.
        # Simple ICMP Echo Request structure:
        # Type=8, Code=0, Checksum=0 (will calculate), ID=12345, Seq=ttl
        packet_id = 12345
        header = bytearray([8, 0, 0, 0, (packet_id >> 8) & 0xff, packet_id & 0xff, (ttl >> 8) & 0xff, ttl & 0xff])

        # Compute checksum
        def checksum(source_string):
            sum_val = 0
            count_to = (len(source_string) // 2) * 2
            count = 0
            while count < count_to:
                this_val = source_string[count + 1] * 256 + source_string[count]
                sum_val = sum_val + this_val
                sum_val = sum_val & 0xffffffff
                count = count + 2
            if count_to < len(source_string):
                sum_val = sum_val + source_string[len(source_string) - 1]
                sum_val = sum_val & 0xffffffff
            sum_val = (sum_val >> 16) + (sum_val & 0xffff)
            sum_val = sum_val + (sum_val >> 16)
            answer = ~sum_val
            answer = answer & 0xffff
            answer = answer >> 8 | (answer << 8 & 0xff00)
            return answer

        csum = checksum(header)
        header[2] = (csum >> 8) & 0xff
        header[3] = csum & 0xff

        curr_ip = None
        curr_name = ""
        latency_ms = None

        start_time = time.perf_counter()
        try:
            tx.sendto(header, (dest_ip, 0))
            _, addr = rx.recvfrom(512)
            duration = (time.perf_counter() - start_time) * 1000.0
            latency_ms = round(duration, 2)
            curr_ip = addr[0]
            try:
                curr_name = socket.gethostbyaddr(curr_ip)[0]
            except Exception:
                curr_name = curr_ip
        except socket.timeout:
            pass
        except Exception:
            pass
        finally:
            tx.close()
            rx.close()

        hops.append({
            "hop": ttl,
            "ip": curr_ip or "*",
            "name": curr_name or "*",
            "latency_ms": latency_ms
        })

        if curr_ip == dest_ip:
            break

    return hops

def parse_tracert_output_windows(output: str) -> List[Dict[str, Any]]:
    """
    Parses Windows 'tracert' output format.
    Example:
      1    <1 ms    <1 ms    <1 ms  192.168.1.1
      2     3 ms     2 ms     2 ms  96.120.101.9
    """
    hops = []
    lines = output.splitlines()
    for line in lines:
        line = line.strip()
        # Look for line starting with hop number
        match = re.match(r"^(\d+)\s+([\s\S]+)$", line)
        if not match:
            continue

        hop_num = int(match.group(1))
        rest = match.group(2).strip()

        # Find IP/Host at the end of the line
        # Tracert prints: <ms values> [optionally host] [IP]
        parts = rest.split()
        if not parts:
            continue

        # Get target IP/host
        target = parts[-1]
        # Strip brackets if present
        target = target.strip("[]()")

        # Get latency values
        latencies = []
        for p in parts[:-1]:
            if "ms" in p or "<" in p:
                p_clean = p.replace("ms", "").replace("<", "").strip()
                try:
                    latencies.append(float(p_clean))
                except ValueError:
                    pass

        avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else None

        hops.append({
            "hop": hop_num,
            "ip": target,
            "name": target,
            "latency_ms": avg_latency
        })
    return hops

def parse_traceroute_output_unix(output: str) -> List[Dict[str, Any]]:
    """
    Parses Linux/macOS 'traceroute' or 'tracepath' output format.
    Example:
      1  192.168.1.1 (192.168.1.1)  1.025 ms  1.011 ms  0.985 ms
      1: 192.168.1.1  2.073ms
      2  * * *
    """
    hops = []
    lines = output.splitlines()
    for line in lines:
        line = line.strip()
        # Hop line format starts with number and optional colon
        match = re.match(r"^(\d+):?\s+([\s\S]+)$", line)
        if not match:
            continue

        hop_num = int(match.group(1))
        rest = match.group(2).strip()

        if rest.startswith("*"):
            hops.append({
                "hop": hop_num,
                "ip": "*",
                "name": "*",
                "latency_ms": None
            })
            continue

        # Extract IP and latencies
        ip_matches = re.findall(r"\(?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\)?", rest)
        ip_addr = ip_matches[0] if ip_matches else "*"

        # Extracted name
        parts = rest.split()
        name = parts[0] if parts else "*"
        if name.startswith("(") or name == ip_addr or name.endswith(":"):
            name = ip_addr

        # Find latencies (e.g. 1.234 ms)
        latencies = []
        ms_matches = re.findall(r"(\d+\.?\d*)\s*ms", rest)
        for m in ms_matches:
            try:
                latencies.append(float(m))
            except ValueError:
                pass

        avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else None

        hops.append({
            "hop": hop_num,
            "ip": ip_addr,
            "name": name,
            "latency_ms": avg_latency
        })
    return hops

def run_subprocess_traceroute(host: str, max_hops: int = 30) -> List[Dict[str, Any]]:
    """
    Runs system traceroute command via subprocess.
    """
    is_windows = (platform.system().lower() == "windows")

    if is_windows:
        cmd = ["tracert", "-d", "-h", str(max_hops), host]
        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60.0)
            return parse_tracert_output_windows(proc.stdout)
        except Exception:
            return []

    # Try traceroute first
    try:
        cmd = ["traceroute", "-n", "-m", str(max_hops), host]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60.0)
        if proc.returncode == 0:
            return parse_traceroute_output_unix(proc.stdout)
    except (FileNotFoundError, Exception):
        pass

    # Try tracepath as fallback
    try:
        cmd = ["tracepath", "-n", "-m", str(max_hops), host]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60.0)
        return parse_traceroute_output_unix(proc.stdout)
    except Exception:
        return []

def traceroute(host: str, max_hops: int = 30, timeout: float = 2.0) -> Dict[str, Any]:
    """
    Traceroutes to a destination host, resolving hops and latencies.
    Tries native raw-sockets first, falling back to OS utility if permission is denied.
    """
    target = host
    if "://" in target:
        target = target.split("://", 1)[1]
    target_host = target.split("/", 1)[0].split(":", 1)[0]

    result = {
        "type": "traceroute",
        "target": target_host,
        "status": "FAILED",
        "latency_ms": None,
        "success": False,
        "error": None,
        "metadata": {
            "hops": []
        }
    }


    start_time = time.perf_counter()
    hops = []
    method = "native"

    try:
        # Try native raw sockets
        hops = run_native_traceroute(target_host, max_hops, timeout)
    except PermissionError:
        # Fallback to subprocess traceroute/tracert
        method = "subprocess"
        hops = run_subprocess_traceroute(target_host, max_hops)
    except Exception:
        method = "subprocess"
        hops = run_subprocess_traceroute(target_host, max_hops)

    duration = (time.perf_counter() - start_time) * 1000.0
    result["latency_ms"] = round(duration, 2)

    if hops:
        result["status"] = "SUCCESS"
        result["success"] = True
        result["metadata"]["hops"] = hops
        result["metadata"]["method"] = method
    else:
        result["error"] = "Failed to run traceroute"

    return result
