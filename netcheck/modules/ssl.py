import socket
import ssl
import time
from datetime import datetime, timezone
from typing import Any, Dict

from netcheck.modules.dns import dns_lookup
from netcheck.utils.normalize import normalize_host

try:
    from cryptography import x509
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

def extract_dn_from_crypto(name) -> Dict[str, str]:
    from cryptography.oid import NameOID
    OID_MAP = {
        NameOID.COMMON_NAME: "commonName",
        NameOID.ORGANIZATION_NAME: "organizationName",
        NameOID.ORGANIZATIONAL_UNIT_NAME: "organizationalUnitName",
        NameOID.COUNTRY_NAME: "countryName",
        NameOID.STATE_OR_PROVINCE_NAME: "stateOrProvinceName",
        NameOID.LOCALITY_NAME: "localityName",
    }
    dn_dict = {}
    for oid, name_key in OID_MAP.items():
        try:
            attrs = name.get_attributes_for_oid(oid)
            if attrs:
                dn_dict[name_key] = attrs[0].value
        except Exception:
            pass
    return dn_dict

def check_ssl_certificate(raw_target: str, port: int = 443, timeout: float = 5.0) -> Dict[str, Any]:
    """
    Validates SSL/TLS certificate for a target host.
    Extracts validity dates, subject, issuer, and calculates days remaining.
    Tries all resolved IPs to handle mixed IPv4/IPv6 networks.
    """
    target = raw_target
    if "://" in target:
        target = target.split("://", 1)[1]
    target_host = target.split("/", 1)[0]

    if ":" in target_host:
        host_part, port_part = target_host.rsplit(":", 1)
        if port_part.isdigit():
            target_host = host_part
            port = int(port_part)

    target_host = normalize_host(target_host)

    result = {
        "type": "ssl",
        "target": f"{target_host}:{port}",
        "status": "FAILED",
        "latency_ms": None,
        "success": False,
        "error": None,
        "metadata": {
            "host": target_host,
            "port": port,
            "subject": {},
            "issuer": {},
            "valid_from": None,
            "valid_until": None,
            "days_until_expiry": None,
            "expired": False,
            "verification_error": None,
            "cipher": None,
            "tls_version": None,
            "fingerprint": None
        }
    }


    # Resolve DNS
    dns_res = dns_lookup(target_host, timeout=min(timeout, 3.0))
    if not dns_res["success"]:
        result["error"] = f"DNS Resolution failed: {dns_res['error']}"
        return result

    ips = dns_res["metadata"]["ips"]
    if not ips:
        result["error"] = "No IP addresses resolved"
        return result

    start_time = time.perf_counter()
    cert = None
    verification_error = None
    resolved_ip = None
    strict_success = False

    # 1. Attempt connection with strict verification (try all resolved IPs)
    for ip in ips:
        family = socket.AF_INET6 if ":" in ip else socket.AF_INET
        try:
            context = ssl.create_default_context()
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED

            with socket.socket(family, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                with context.wrap_socket(sock, server_hostname=target_host) as ssock:
                    ssock.connect((ip, port))
                    cert = ssock.getpeercert()
                    try:
                        ciph = ssock.cipher()
                        if ciph:
                            result["metadata"]["cipher"] = ciph[0]
                            result["metadata"]["tls_version"] = ssock.version()
                        der_bytes = ssock.getpeercert(binary_form=True)
                        if der_bytes:
                            import hashlib
                            result["metadata"]["fingerprint"] = hashlib.sha256(der_bytes).hexdigest()
                    except Exception:
                        pass
            resolved_ip = ip
            strict_success = True
            verification_error = None
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            result["latency_ms"] = round(duration_ms, 2)
            break
        except ssl.SSLCertVerificationError as e:
            verification_error = f"SSL verification failed: {e.reason}"
            resolved_ip = ip
            break
        except Exception as e:
            verification_error = str(e)
            resolved_ip = ip
            # Continue trying other resolved IPs
            continue

    # 2. If connection failed or verification failed, try with verification disabled to inspect certificate metadata
    if cert is None and resolved_ip:
        try:
            context_fallback = ssl.create_default_context()
            context_fallback.check_hostname = False
            context_fallback.verify_mode = ssl.CERT_NONE

            family = socket.AF_INET6 if ":" in resolved_ip else socket.AF_INET
            fallback_start = time.perf_counter()
            with socket.socket(family, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                with context_fallback.wrap_socket(sock, server_hostname=target_host) as ssock:
                    ssock.connect((resolved_ip, port))
                    try:
                        ciph = ssock.cipher()
                        if ciph:
                            result["metadata"]["cipher"] = ciph[0]
                            result["metadata"]["tls_version"] = ssock.version()
                        der_bytes = ssock.getpeercert(binary_form=True)
                        if der_bytes:
                            import hashlib
                            result["metadata"]["fingerprint"] = hashlib.sha256(der_bytes).hexdigest()
                    except Exception:
                        pass

                    # Try fallback to cryptography parsing of binary certificate
                    if HAS_CRYPTOGRAPHY:
                        try:
                            der_bytes = ssock.getpeercert(binary_form=True)
                            if der_bytes:
                                x509_cert = x509.load_der_x509_certificate(der_bytes)
                                subject_dict = extract_dn_from_crypto(x509_cert.subject)
                                issuer_dict = extract_dn_from_crypto(x509_cert.issuer)
                                not_before = x509_cert.not_valid_before.replace(tzinfo=timezone.utc)
                                not_after = x509_cert.not_valid_after.replace(tzinfo=timezone.utc)

                                # Subject Alternative Names
                                sans = []
                                try:
                                    from cryptography.x509.oid import ExtensionOID
                                    ext = x509_cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
                                    for name in ext.value:
                                        if isinstance(name, x509.DNSName):
                                            sans.append(name.value)
                                except Exception:
                                    pass

                                cert = {
                                    "subject": [[(k, v)] for k, v in subject_dict.items()],
                                    "issuer": [[(k, v)] for k, v in issuer_dict.items()],
                                    "notBefore": not_before.strftime("%b %d %H:%M:%S %Y GMT"),
                                    "notAfter": not_after.strftime("%b %d %H:%M:%S %Y GMT"),
                                    "subjectAltName": [("DNS", san) for san in sans]
                                }
                        except Exception:
                            pass

                    if not cert:
                        cert = ssock.getpeercert(binary_form=False)

            duration_ms = (time.perf_counter() - fallback_start) * 1000.0
            result["latency_ms"] = round(duration_ms, 2)
        except Exception as e:
            result["error"] = verification_error or str(e)
            return result

    # 3. Parse certificate metadata
    if not cert:
        result["error"] = verification_error or "Failed to retrieve certificate details"
        return result

    def parse_dn(dn_list) -> Dict[str, str]:
        dn_dict = {}
        for item in dn_list:
            for key, val in item:
                dn_dict[key] = val
        return dn_dict

    subject = parse_dn(cert.get("subject", []))
    issuer = parse_dn(cert.get("issuer", []))

    valid_from_str = cert.get("notBefore")
    valid_until_str = cert.get("notAfter")

    date_format = "%b %d %H:%M:%S %Y %Z"

    try:
        valid_from = datetime.strptime(valid_from_str, date_format).replace(tzinfo=timezone.utc)
        valid_until = datetime.strptime(valid_until_str, date_format).replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)

        days_until_expiry = (valid_until - now).days
        expired = (now > valid_until)

        result["metadata"]["subject"] = subject
        result["metadata"]["issuer"] = issuer
        result["metadata"]["valid_from"] = valid_from.strftime("%Y-%m-%d %H:%M:%S UTC")
        result["metadata"]["valid_until"] = valid_until.strftime("%Y-%m-%d %H:%M:%S UTC")
        result["metadata"]["days_until_expiry"] = days_until_expiry
        result["metadata"]["expired"] = expired

        # Extract SANs (Subject Alternative Names)
        sans = []
        alt_names = cert.get("subjectAltName", [])
        if alt_names:
            for type_name, value in alt_names:
                if type_name == "DNS":
                    sans.append(value)
        result["metadata"]["sans"] = sans

        if verification_error and not strict_success:
            result["metadata"]["verification_error"] = verification_error
            result["error"] = verification_error
            result["status"] = "EXPIRED" if expired else "VERIFICATION_FAILED"
            result["success"] = False
        else:
            result["success"] = not expired
            result["status"] = "SUCCESS" if result["success"] else "EXPIRED"
            if expired:
                result["error"] = "Certificate has expired"
    except Exception as e:
        result["error"] = f"Failed to parse cert dates: {e}"
        result["status"] = "FAILED"
        result["success"] = False

    return result
