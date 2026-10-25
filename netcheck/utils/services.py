import socket

# Curated dictionary of well-known port mapping to service names
_CURATED_SERVICES = {
    20: "ftp-data",
    21: "ftp",
    22: "ssh",
    23: "telnet",
    25: "smtp",
    53: "dns",
    67: "dhcp-server",
    68: "dhcp-client",
    69: "tftp",
    80: "http",
    88: "kerberos",
    110: "pop3",
    115: "sftp",
    119: "nntp",
    123: "ntp",
    135: "msrpc",
    137: "netbios-ns",
    138: "netbios-dgm",
    139: "netbios-ssn",
    143: "imap",
    161: "snmp",
    162: "snmp-trap",
    179: "bgp",
    389: "ldap",
    443: "https",
    445: "microsoft-ds",
    465: "smtps",
    500: "isakmp",
    514: "syslog",
    587: "submission",
    636: "ldaps",
    873: "rsync",
    993: "imaps",
    995: "pop3s",
    1080: "socks",
    1433: "mssql",
    1521: "oracle",
    2049: "nfs",
    3000: "gitea/react",
    3306: "mysql",
    3389: "rdp",
    5060: "sip",
    5432: "postgresql",
    5672: "rabbitmq",
    5900: "vnc",
    6379: "redis",
    8000: "http-alt",
    8080: "http-proxy",
    8443: "https-alt",
    9000: "portainer",
    9092: "kafka",
    9200: "elasticsearch",
    11211: "memcached",
    27017: "mongodb"
}

def get_service_name(port: int) -> str:
    """
    Returns a service name string for a given port.
    Tries standard library socket.getservbyport first,
    falling back to a curated internal dictionary.
    """
    try:
        return socket.getservbyport(port, "tcp")
    except Exception:
        pass
    try:
        return socket.getservbyport(port, "udp")
    except Exception:
        pass
    return _CURATED_SERVICES.get(port, "")


# Empirical Top 100 most common Internet ports (from Nmap empirical frequency rankings)
TOP_100_PORTS = [
    7, 9, 13, 21, 22, 23, 25, 26, 37, 53, 79, 80, 81, 88, 106, 110, 111, 113, 119, 135,
    139, 143, 144, 179, 199, 389, 427, 443, 444, 445, 465, 513, 514, 515, 543, 544, 548,
    554, 587, 631, 646, 873, 990, 993, 995, 1025, 1026, 1027, 1028, 1029, 1110, 1433,
    1720, 1723, 1755, 1900, 2000, 2001, 2049, 2121, 2717, 3000, 3128, 3306, 3389, 3986,
    4899, 5000, 5009, 5051, 5060, 5101, 5190, 5357, 5432, 5631, 5666, 5800, 5900, 6000,
    6001, 6646, 7070, 8000, 8008, 8009, 8080, 8081, 8443, 8888, 9100, 9999, 10000, 32768,
    49152, 49153, 49154, 49155, 49156, 49157
]


def get_top_ports(count: int = 100) -> list:
    """Return the top N most frequent Internet ports (capped at 1000)."""
    if count <= 0:
        return []
    count = min(count, 1000)
    if count <= len(TOP_100_PORTS):
        return sorted(TOP_100_PORTS[:count])
    # For count > 100 up to 1000, supplement with common services ports and sequential common ports
    extra = set(range(1, 1024)) - set(TOP_100_PORTS)
    combined = sorted(set(TOP_100_PORTS) | set(list(extra)[: count - len(TOP_100_PORTS)]))
    return combined[:count]
