import ipaddress
from typing import List


def expand_ip_range(ip_str: str) -> List[str]:
    """
    Expands an IP string representing a single IP, a CIDR block (e.g. 192.168.1.0/24),
    or a dash-range (e.g. 192.168.1.1-50).
    """
    ip_str = ip_str.strip()
    if not ip_str:
        return []

    if "/" in ip_str:
        try:
            network = ipaddress.ip_network(ip_str, strict=False)
            hosts = [str(ip) for ip in network.hosts()]
            if len(hosts) > 256:
                import sys
                print(f"⚠️  Warning: CIDR {ip_str} generates {len(hosts)} hosts - this may take a while", file=sys.stderr)
            return hosts
        except Exception:
            return [ip_str]

    elif "-" in ip_str:
        try:
            parts = ip_str.split("-")
            start_ip = parts[0].strip()
            end_val = parts[1].strip()

            # If the second part is just a single octet (e.g. 192.168.1.1-50)
            if "." not in end_val:
                base_parts = start_ip.split(".")
                base_parts[-1] = end_val
                end_ip = ".".join(base_parts)
            else:
                end_ip = end_val

            start = ipaddress.ip_address(start_ip)
            end = ipaddress.ip_address(end_ip)

            ips = []
            curr = start
            while curr <= end:
                ips.append(str(curr))
                curr += 1
            if len(ips) > 256:
                import sys
                print(f"⚠️  Warning: IP range {ip_str} generates {len(ips)} hosts - this may take a while", file=sys.stderr)
            return ips
        except Exception:
            return [ip_str]
    else:
        return [ip_str]

def expand_port_range(port_str: str) -> List[int]:
    """
    Expands a port range string which can be a single port (80), a list (80,443),
    or a dash-range (8000-8100).
    """
    port_str = str(port_str).strip()
    ports = []
    if "," in port_str:
        for p in port_str.split(","):
            ports.extend(expand_port_range(p))
    elif "-" in port_str:
        try:
            parts = port_str.split("-")
            start = int(parts[0])
            end = int(parts[1])
            if 1 <= start <= 65535 and 1 <= end <= 65535:
                ports.extend(range(start, end + 1))
        except Exception:
            pass
    else:
        try:
            p_val = int(port_str)
            if 1 <= p_val <= 65535:
                ports.append(p_val)
        except ValueError:
            pass

    # Remove duplicates and preserve order
    seen = set()
    return [p for p in ports if not (p in seen or seen.add(p))]


def parse_target_string(target: str):
    """
    Parse a compact ``host:port`` (or ``host:ports``) string into
    ``(host, port_str)`` pairs, correctly handling:

    - Plain hostname / IPv4:   ``google.com:443``
    - Port ranges:             ``192.168.1.1:8000-8100``
    - Port lists:              ``10.0.0.1:80,443``
    - IPv6 bracketed:          ``[::1]:80``, ``[::1]:80,443``
    - IPv6 unbracketed (last colon = port): ``::1:80``  — treated as host=``::1``, port=``80``

    Returns ``(host, port_str)`` or ``(target, None)`` if no port can be parsed.
    """
    target = target.strip()

    # --- Bracketed IPv6: [addr]:port ---
    if target.startswith("["):
        bracket_end = target.find("]")
        if bracket_end != -1:
            host = target[1:bracket_end]
            rest = target[bracket_end + 1:]
            if rest.startswith(":"):
                return host, rest[1:]
            return host, None
        # Malformed bracket — return as-is
        return target, None

    # --- Count colons ---
    colon_count = target.count(":")

    if colon_count == 0:
        # No colon at all → hostname/IP only, no port
        return target, None

    if colon_count >= 2:
        # Looks like IPv6.  Only peel off a port if the suffix after the
        # LAST colon looks like port digits / range / list.
        last_colon = target.rfind(":")
        suffix = target[last_colon + 1:]
        # suffix must be purely digits / commas / hyphens to be a port spec
        if suffix and all(c.isdigit() or c in ",-" for c in suffix):
            host = target[:last_colon]
            return host, suffix
        # Otherwise treat entire string as IPv6 host
        return target, None

    # --- Exactly one colon: classic host:port ---
    host, port_str = target.rsplit(":", 1)
    # Make sure port_str is actually a port spec (digits/range/list)
    if port_str and all(c.isdigit() or c in ",-" for c in port_str):
        return host, port_str
    # Not a port — treat whole string as host
    return target, None

