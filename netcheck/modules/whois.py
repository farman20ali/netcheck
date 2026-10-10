import json
import socket
import time
import urllib.request
from typing import Any, Dict


def get_rdap_info(target: str, is_ip: bool = False) -> Dict[str, Any]:
    """
    Retrieves registration data using modern Registration Data Access Protocol (RDAP).
    """
    if is_ip:
        url = f"https://rdap.db.ripenet.net/ip/{target}"
    else:
        url = f"https://rdap.org/domain/{target}"

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 NetCheck/2.0", "Accept": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=5.0) as response:
        content = response.read().decode("utf-8")
        return json.loads(content)

def get_whois_socket(target: str, server: str = "whois.iana.org") -> str:
    """
    Performs legacy WHOIS query over TCP port 43.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5.0)
            s.connect((server, 43))
            s.sendall(f"{target}\r\n".encode("utf-8"))

            # Read response
            response = []
            while True:
                data = s.recv(4096)
                if not data:
                    break
                response.append(data)
            return b"".join(response).decode("utf-8", errors="replace")
    except Exception as e:
        return f"WHOIS error: {e}"

def lookup_registration(target: str) -> Dict[str, Any]:
    """
    Looks up registrar/allocation information for domain or IP.
    Uses RDAP first, falling back to legacy WHOIS socket query.
    """
    # Normalize target
    target_clean = target.strip()
    if "://" in target_clean:
        target_clean = target_clean.split("://", 1)[1]
    target_clean = target_clean.split("/", 1)[0].split(":", 1)[0]

    is_ip = False
    try:
        socket.inet_aton(target_clean)
        is_ip = True
    except socket.error:
        try:
            socket.inet_pton(socket.AF_INET6, target_clean)
            is_ip = True
        except socket.error:
            pass

    result = {
        "type": "whois",
        "target": target_clean,
        "status": "FAILED",
        "latency_ms": None,
        "success": False,
        "error": None,
        "metadata": {
            "type": "IP" if is_ip else "DOMAIN",
            "rdap_source": None,
            "registrar": None,
            "creation_date": None,
            "raw_whois": None
        }
    }


    start_time = time.perf_counter()

    # 1. Attempt RDAP
    try:
        rdap_data = get_rdap_info(target_clean, is_ip)
        duration = (time.perf_counter() - start_time) * 1000.0
        result["status"] = "SUCCESS"
        result["success"] = True
        result["latency_ms"] = round(duration, 2)
        result["metadata"]["rdap_source"] = "RDAP API"

        # Extract registrar / entity details
        if "entities" in rdap_data:
            registrars = []
            for ent in rdap_data["entities"]:
                roles = ent.get("roles", [])
                if "registrar" in roles or "registrant" in roles:
                    vcard = ent.get("vcardArray", [])
                    if len(vcard) > 1:
                        for entry in vcard[1]:
                            if entry[0] == "fn":
                                registrars.append(entry[3])
            if registrars:
                result["metadata"]["registrar"] = ", ".join(registrars)

        # Extract creation date
        if "events" in rdap_data:
            for event in rdap_data["events"]:
                if event.get("eventAction") in ("registration", "birth"):
                    result["metadata"]["creation_date"] = event.get("eventDate")
                    break
        return result
    except Exception:
        # Fall back to WHOIS socket query
        pass

    # 2. Attempt legacy WHOIS
    try:
        whois_server = "whois.iana.org"
        raw_output = get_whois_socket(target_clean, whois_server)

        # Parse output for referral whois server
        refer_match = None
        for line in raw_output.splitlines():
            if "refer:" in line.lower() or "whois:" in line.lower():
                parts = line.split(":")
                if len(parts) > 1:
                    refer_match = parts[1].strip()
                    break

        if refer_match and refer_match != whois_server:
            raw_output = get_whois_socket(target_clean, refer_match)

        duration = (time.perf_counter() - start_time) * 1000.0
        result["status"] = "SUCCESS"
        result["success"] = True
        result["latency_ms"] = round(duration, 2)
        result["metadata"]["rdap_source"] = "Legacy WHOIS"
        result["metadata"]["raw_whois"] = raw_output

        # Parse registrar/creation info from raw text
        for line in raw_output.splitlines():
            line_lower = line.lower()
            if "registrar:" in line_lower:
                result["metadata"]["registrar"] = line.split(":", 1)[1].strip()
            elif "creation date:" in line_lower or "created:" in line_lower:
                result["metadata"]["creation_date"] = line.split(":", 1)[1].strip()

        return result
    except Exception as e:
        duration = (time.perf_counter() - start_time) * 1000.0
        result["latency_ms"] = round(duration, 2)
        result["error"] = f"RDAP and WHOIS queries failed: {e}"
        return result
