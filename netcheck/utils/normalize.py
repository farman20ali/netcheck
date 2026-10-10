from typing import Tuple


def normalize_host(raw: str) -> str:
    """Strips scheme, path, query, and port to return a clean hostname/IP."""
    if not raw:
        return ""
    if "://" in raw:
        raw = raw.split("://", 1)[1]
    raw = raw.split("/", 1)[0]
    raw = raw.split("?", 1)[0]
    raw = raw.split("#", 1)[0]

    # Handle IPv6 bracket notation, e.g. [2001:db8::1]:80 or [2001:db8::1]
    if raw.startswith("["):
        if "]" in raw:
            parts = raw.split("]", 1)
            host = parts[0][1:]
            return host.strip()

    # If it has multiple colons, treat as a bare IPv6 address and do not split
    if raw.count(":") > 1:
        return raw.strip()

    if ":" in raw:
        raw = raw.split(":", 1)[0]
    return raw.strip()

def is_valid_host(host: str) -> bool:
    """Checks if a normalized host is non-empty and potentially valid."""
    return bool(host and host.strip())


def parse_line_to_raw_host_port(line: str, default_port: str = "80") -> Tuple[str, str]:
    """
    Robustly parses an input line to extract raw host (could be range/CIDR)
    and raw port (could be list/range).
    Supports:
      - host port
      - host,port
      - host:port
      - http://host:port/path
      - [ipv6]:port
      - Handles trailing comments (#) and paths/queries.
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return "", ""

    # Remove trailing comments starting with #
    if "#" in line:
        line = line.split("#", 1)[0].strip()

    # Is it a URL?
    if "://" in line:
        try:
            proto, rest = line.split("://", 1)
            # Strip path, query, fragment
            rest_host = rest.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0].strip()
            default_p = "443" if proto.lower() == "https" else default_port

            if ":" in rest_host:
                if rest_host.startswith("["):
                    if "]:" in rest_host:
                        h, p = rest_host.split("]:", 1)
                        return h[1:], p
                    elif rest_host.endswith("]"):
                        return rest_host[1:-1], default_p
                h, p = rest_host.rsplit(":", 1)
                if all(c.isdigit() or c in ',- ' for c in p) and any(c.isdigit() for c in p):
                    return h, p
                return rest_host, default_p
            return rest_host, default_p
        except Exception:
            pass

    # Check for IPv6 bracket notation first, e.g. [2a00::]:80,443 or [2a00::] 80
    if line.startswith("["):
        if "]:" in line:
            h, p = line.split("]:", 1)
            p_clean = p.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0].strip()
            return h[1:], p_clean
        elif "]" in line:
            parts = line.split("]", 1)
            h = parts[0][1:].strip()
            p_part = parts[1].strip()
            if p_part.startswith(":"):
                p_part = p_part[1:].strip()
            p_clean = p_part.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0].strip()
            return h, (p_clean if p_clean else default_port)

    # Does it have whitespace? E.g. "192.168.1.1 80" or "google.com 80,443"
    parts = line.split(None, 1)
    if len(parts) == 2:
        h_cand, p_cand = parts[0].strip(), parts[1].strip()
        # Clean up any trailing path from the port if it leaked in
        p_clean = p_cand.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0].strip()
        if all(c.isdigit() or c in ',- ' for c in p_clean) and any(c.isdigit() for c in p_clean):
            return h_cand, p_clean

    # Does it have a colon? E.g. "google.com:80" or "google.com:80,443" or "google.com:80-90"
    if ":" in line:
        h_part, p_part = line.rsplit(":", 1)
        p_clean = p_part.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0].strip()
        if all(c.isdigit() or c in ',- ' for c in p_clean) and any(c.isdigit() for c in p_clean):
            return h_part.strip(), p_clean

    # Does it have a comma? E.g. "google.com,80" or "google.com,80,443"
    if "," in line and not line.startswith(",") and not line.endswith(","):
        parts = line.split(",", 1)
        h_part, p_part = parts[0].strip(), parts[1].strip()
        p_clean = p_part.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0].strip()
        if all(c.isdigit() or c in ',- ' for c in p_clean) and any(c.isdigit() for c in p_clean):
            return h_part, p_clean

    # Fallback: strip trailing paths/slashes if present (e.g. google.com/path)
    host_clean = line.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0].strip()
    return host_clean, default_port
