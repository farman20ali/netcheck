import platform
import re
import socket
import subprocess
from typing import Any, Dict, List, Optional, Tuple


def get_active_local_ip() -> str:
    """
    Finds the primary outbound IP address using the UDP routing table query.
    Falls back to a local IP check or returns '127.0.0.1' if disconnected.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Does not actually transmit packets, just queries the OS routing table
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        return ip
    except Exception:
        # Fallback to query local gateway subnet
        try:
            s.connect(('192.168.1.1', 80))
            ip = s.getsockname()[0]
            return ip
        except Exception:
            return "127.0.0.1"
    finally:
        s.close()

def get_public_ip(timeout: float = 1.5) -> str:
    """Retrieves public IP address from public APIs concurrently."""
    import urllib.request
    from concurrent.futures import ThreadPoolExecutor, as_completed

    services = ["https://api.ipify.org", "https://ifconfig.me", "https://icanhazip.com"]

    def fetch_ip(url: str) -> Optional[str]:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'NetCheck/2.0'})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                ip = response.read().decode('utf-8').strip()
                if ip and (re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip) or ':' in ip):
                    return ip
        except Exception:
            pass
        return None

    with ThreadPoolExecutor(max_workers=len(services)) as executor:
        futures = {executor.submit(fetch_ip, url): url for url in services}
        for fut in as_completed(futures):
            res = fut.result()
            if res:
                return res

    return "Unknown"

def get_default_gateway() -> Tuple[Optional[str], Optional[str]]:
    """Returns (gateway_ip, interface_name) for the default route."""
    plat = platform.system().lower()
    if plat == "linux":
        try:
            with open("/proc/net/route", "r") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 3 and parts[1] == "00000000": # default route
                        gw_hex = parts[2]
                        dev = parts[0]
                        # Hex IP is little-endian in /proc/net/route (e.g. 010116AC for 172.22.1.1)
                        gw_ip = socket.inet_ntoa(int(gw_hex, 16).to_bytes(4, byteorder='little'))
                        return gw_ip, dev
        except Exception:
            pass

    # Cross-platform fallback using route commands
    try:
        if plat == "windows":
            proc = subprocess.run(["route", "print", "0.0.0.0"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if proc.returncode == 0:
                for line in proc.stdout.splitlines():
                    if "0.0.0.0" in line:
                        parts = line.strip().split()
                        if len(parts) >= 4 and parts[0] == "0.0.0.0":
                            return parts[2], None
        else: # macOS / Unix fallback
            proc = subprocess.run(["netstat", "-rn"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if proc.returncode == 0:
                for line in proc.stdout.splitlines():
                    if line.strip().startswith("default") or line.strip().startswith("0.0.0.0"):
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            gateway = parts[1]
                            dev = parts[-1] if len(parts) >= 4 else None
                            return gateway, dev
    except Exception:
        pass

    return None, None

def get_network_interfaces(all_interfaces: bool = False, include_public: bool = False, timeout: float = 1.5) -> Dict[str, Any]:
    """
    Identifies local network interfaces, their status, IPv4/IPv6 addresses,
    and flags the primary active connection.
    """
    primary_ip = get_active_local_ip()
    plat = platform.system().lower()

    interfaces = {}

    if plat == "windows":
        interfaces = _parse_windows_ipconfig()
    elif plat == "darwin":
        interfaces = _parse_unix_ifconfig(all_interfaces)
    else:
        interfaces = _parse_linux_ip_addr(all_interfaces)

    # If no interfaces were parsed but we have a primary IP, insert a dummy entry
    if not interfaces and primary_ip != "127.0.0.1":
        interfaces["default"] = {
            "ipv4": [primary_ip],
            "ipv6": [],
            "status": "UP",
            "active": True
        }
    else:
        # Post-process interfaces to set "active" flags based on primary IP match
        has_active = False
        for name, iface in interfaces.items():
            iface["active"] = False
            # Check if primary_ip matches any IPv4 address on this interface
            if primary_ip in iface["ipv4"]:
                iface["active"] = True
                iface["status"] = "UP"  # Force status to UP if it holds the active IP
                has_active = True

        # If no interface matched the primary IP, set the first one with an IP as active
        if not has_active:
            for name, iface in interfaces.items():
                if iface["ipv4"] and primary_ip != "127.0.0.1":
                    iface["active"] = True
                    iface["status"] = "UP"
                    break

    # Get gateway details
    gateway_ip, gateway_dev = get_default_gateway()

    # Get public IP
    if include_public and primary_ip != "127.0.0.1":
        public_ip = get_public_ip(timeout=timeout)
    else:
        public_ip = "Unknown"

    # Filter active only if all_interfaces is False
    if not all_interfaces:
        interfaces = {name: iface for name, iface in interfaces.items() if iface.get("status") == "UP"}

    return {
        "type": "interfaces",
        "target": "interfaces",
        "status": "SUCCESS",
        "latency_ms": 0.0,
        "success": True,
        "error": None,
        "metadata": {
            "primary_ip": primary_ip,
            "interfaces": interfaces,
            "gateway_ip": gateway_ip,
            "gateway_dev": gateway_dev,
            "public_ip": public_ip,
            "public_ip_checked": include_public,
            "all_interfaces_shown": all_interfaces
        }
    }


def check_listening_ports() -> Dict[str, Any]:
    """
    Identifies all local active listening TCP sockets, process names, PIDs,
    and maps them to Docker container names where applicable.
    """
    try:
        ports = get_listening_ports()
        success = True
        error = None
    except Exception as e:
        ports = []
        success = False
        error = str(e)

    return {
        "type": "ports",
        "target": "ports",
        "status": "SUCCESS" if success else "FAILED",
        "latency_ms": 0.0,
        "success": success,
        "error": error,
        "metadata": {
            "listening_ports": ports
        }
    }


def _parse_linux_ip_addr(all_interfaces: bool = False) -> Dict[str, Any]:
    interfaces = {}
    try:
        proc = subprocess.run(["ip", "addr", "show"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode == 0:
            current_iface = None
            for line in proc.stdout.splitlines():
                iface_match = re.match(r"^\d+:\s+([^:]+):", line)
                if iface_match:
                    current_iface = iface_match.group(1).strip()
                    if not all_interfaces and (current_iface == "lo" or current_iface.startswith("veth")):
                        current_iface = None
                        continue

                    state = "DOWN"
                    if "state UP" in line:
                        state = "UP"
                    elif "state UNKNOWN" in line:
                        state = "UNKNOWN"
                    elif "state DORMANT" in line:
                        state = "DORMANT"

                    interfaces[current_iface] = {
                        "ipv4": [],
                        "ipv6": [],
                        "status": state
                    }
                elif current_iface and line.strip().startswith("inet "):
                    inet_match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", line)
                    if inet_match:
                        interfaces[current_iface]["ipv4"].append(inet_match.group(1))
                        # If interface has an IP, ensure it's considered UP
                        if interfaces[current_iface]["status"] in ("DOWN", "DORMANT"):
                            interfaces[current_iface]["status"] = "UP"
                elif current_iface and line.strip().startswith("inet6 "):
                    inet6_match = re.search(r"inet6\s+([0-9a-fA-F:]+)", line)
                    if inet6_match:
                        ip6 = inet6_match.group(1)
                        if not ip6.lower().startswith("fe80"):
                            interfaces[current_iface]["ipv6"].append(ip6)
    except Exception:
        # Fallback to ifconfig
        return _parse_unix_ifconfig(all_interfaces)
    return interfaces

def _parse_unix_ifconfig(all_interfaces: bool = False) -> Dict[str, Any]:
    interfaces = {}
    try:
        proc = subprocess.run(["ifconfig"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode == 0:
            current_iface = None
            for line in proc.stdout.splitlines():
                if line and not line.startswith("\t") and not line.startswith(" "):
                    parts = line.split(":")
                    if len(parts) > 0:
                        current_iface = parts[0].strip()
                        if not all_interfaces and (current_iface.startswith("lo") or current_iface.startswith("veth")):
                            current_iface = None
                            continue
                        state = "DOWN"
                        if "UP" in line or "RUNNING" in line:
                            state = "UP"
                        interfaces[current_iface] = {
                            "ipv4": [],
                            "ipv6": [],
                            "status": state
                        }
                elif current_iface and line.strip().startswith("inet "):
                    inet_match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", line)
                    if inet_match:
                        interfaces[current_iface]["ipv4"].append(inet_match.group(1))
                        interfaces[current_iface]["status"] = "UP"
                elif current_iface and line.strip().startswith("inet6 "):
                    inet6_match = re.search(r"inet6\s+([0-9a-fA-F:]+)", line)
                    if inet6_match:
                        ip6 = inet6_match.group(1)
                        if not ip6.lower().startswith("fe80"):
                            interfaces[current_iface]["ipv6"].append(ip6)
    except Exception:
        pass
    return interfaces

def _parse_windows_ipconfig() -> Dict[str, Any]:
    interfaces = {}
    try:
        proc = subprocess.run(["ipconfig"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode == 0:
            current_iface = None
            for line in proc.stdout.splitlines():
                if line.strip() and not line.startswith("   "):
                    if "adapter" in line:
                        current_iface = line.split(":", 1)[0].replace("adapter", "").strip()
                        current_iface = current_iface.replace("Wireless LAN", "WLAN").replace("Ethernet adapter", "Ethernet")
                        interfaces[current_iface] = {
                            "ipv4": [],
                            "ipv6": [],
                            "status": "DOWN"
                        }
                elif current_iface and "IPv4 Address" in line:
                    ip_match = re.search(r":\s*(\d+\.\d+\.\d+\.\d+)", line)
                    if ip_match:
                        interfaces[current_iface]["ipv4"].append(ip_match.group(1))
                        interfaces[current_iface]["status"] = "UP"
                elif current_iface and "IPv6 Address" in line:
                    ip6_match = re.search(r":\s*([0-9a-fA-F:]+)", line)
                    if ip6_match:
                        ip6 = ip6_match.group(1)
                        if not ip6.lower().startswith("fe80"):
                            interfaces[current_iface]["ipv6"].append(ip6)
                            interfaces[current_iface]["status"] = "UP"
    except Exception:
        pass
    return interfaces

def get_docker_port_mappings() -> Dict[int, str]:
    mappings = {}
    try:
        proc = subprocess.run(["docker", "ps", "--format", "{{.Ports}}\t{{.Names}}"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) >= 2:
                    ports_str, name = parts[0], parts[1]
                    for port_match in re.findall(r'(?::| )(\d+)->', ports_str):
                        mappings[int(port_match)] = f"Docker: {name}"
    except Exception:
        pass
    return mappings

def _get_listening_ports_windows(docker_mappings: Dict[int, str]) -> List[Dict[str, Any]]:
    ports = []
    pid_map = {}
    try:
        proc = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode == 0:
            import csv
            import io
            reader = csv.reader(io.StringIO(proc.stdout))
            for row in reader:
                if len(row) >= 2:
                    pid_map[row[1]] = row[0]
    except Exception:
        pass

    try:
        proc = subprocess.run(["netstat", "-ano"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if "LISTENING" not in line:
                    continue
                parts = line.strip().split()
                if len(parts) >= 5:
                    proto = parts[0]
                    local_addr = parts[1]
                    pid = parts[4]
                    if ":" in local_addr:
                        addr, port_str = local_addr.rsplit(":", 1)
                        try:
                            port = int(port_str)
                        except ValueError:
                            continue
                        proc_name = pid_map.get(pid, f"PID {pid}")
                        if port in docker_mappings:
                            proc_name = f"{docker_mappings[port]} (container)"
                        elif not proc_name or proc_name.lower().startswith("pid"):
                            from netcheck.utils.services import get_service_name
                            srv = get_service_name(port)
                            if srv:
                                proc_name = srv
                        ports.append({
                            "proto": proto,
                            "address": addr,
                            "port": port,
                            "process": proc_name,
                            "pid": pid
                        })
    except Exception:
        pass
    return ports

def _get_listening_ports_unix(docker_mappings: Dict[int, str]) -> List[Dict[str, Any]]:
    ports = []
    try:
        proc = subprocess.run(["ss", "-tlnp"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if "LISTEN" not in line:
                    continue
                parts = line.strip().split()
                if len(parts) >= 4:
                    local_addr = parts[3]
                    if ":" in local_addr:
                        addr, port_str = local_addr.rsplit(":", 1)
                        if "%" in addr:
                            addr = addr.split("%")[0]
                        try:
                            port = int(port_str)
                        except ValueError:
                            continue
                        proc_name = ""
                        pid = ""
                        if len(parts) >= 6:
                            proc_col = " ".join(parts[5:])
                            m = re.search(r'users:\(\("([^"]+)",pid=(\d+)', proc_col)
                            if m:
                                proc_name = m.group(1)
                                pid = m.group(2)
                        if port in docker_mappings:
                            proc_name = f"{docker_mappings[port]} (container)"
                        elif proc_name == "docker-proxy":
                            proc_name = "Docker Proxy"
                        elif not proc_name:
                            from netcheck.utils.services import get_service_name
                            srv = get_service_name(port)
                            if srv:
                                proc_name = srv
                            else:
                                proc_name = "Unknown"
                        ports.append({
                            "proto": "TCP",
                            "address": addr,
                            "port": port,
                            "process": proc_name,
                            "pid": pid
                        })
            return ports
    except Exception:
        pass

    try:
        proc = subprocess.run(["lsof", "-iTCP", "-sTCP:LISTEN", "-P", "-n"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if line.startswith("COMMAND") or not line.strip():
                    continue
                parts = line.strip().split()
                if len(parts) >= 9:
                    command = parts[0]
                    pid = parts[1]
                    name_col = parts[8]
                    if ":" in name_col:
                        addr, port_str = name_col.rsplit(":", 1)
                        try:
                            port = int(port_str)
                        except ValueError:
                            continue
                        proc_name = command
                        if port in docker_mappings:
                            proc_name = f"{docker_mappings[port]} (container)"
                        elif proc_name == "docker-proxy":
                            proc_name = "Docker Proxy"
                        ports.append({
                            "proto": "TCP",
                            "address": addr,
                            "port": port,
                            "process": proc_name,
                            "pid": pid
                        })
            return ports
    except Exception:
        pass

    try:
        proc = subprocess.run(["netstat", "-tln"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if "LISTEN" not in line:
                    continue
                parts = line.strip().split()
                if len(parts) >= 4:
                    local_addr = parts[3]
                    if ":" in local_addr:
                        addr, port_str = local_addr.rsplit(":", 1)
                        try:
                            port = int(port_str)
                        except ValueError:
                            continue
                        proc_name = ""
                        if port in docker_mappings:
                            proc_name = f"{docker_mappings[port]} (container)"
                        else:
                            from netcheck.utils.services import get_service_name
                            srv = get_service_name(port)
                            proc_name = srv if srv else "Unknown"
                        ports.append({
                            "proto": "TCP",
                            "address": addr,
                            "port": port,
                            "process": proc_name,
                            "pid": ""
                        })
    except Exception:
        pass
    return ports

def get_listening_ports() -> List[Dict[str, Any]]:
    plat = platform.system().lower()
    docker_mappings = get_docker_port_mappings()
    if plat == "windows":
        return _get_listening_ports_windows(docker_mappings)
    return _get_listening_ports_unix(docker_mappings)
