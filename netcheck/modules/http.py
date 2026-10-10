import time
import urllib.error
import urllib.request
from typing import Any, Dict


def check_http_status(
    url: str,
    timeout: float = 5.0,
    method: str = "GET",
    headers: Dict[str, str] = None,
    auth: tuple = None
) -> Dict[str, Any]:
    """
    Validates the HTTP/HTTPS status code, response time, and size for a given URL.
    Identifies HTTP redirection and handles error codes gracefully.
    """
    target_url = url
    if not (url.startswith("http://") or url.startswith("https://")):
        target_url = "http://" + url

    result = {
        "type": "http",
        "target": target_url,
        "status": "FAILED",
        "latency_ms": None,
        "success": False,
        "error": None,
        "metadata": {
            "status_code": None,
            "redirect_url": None,
            "size_bytes": 0,
            "headers": {}
        }
    }

    start_time = time.perf_counter()
    try:
        req_headers = {'User-Agent': 'Mozilla/5.0 NetCheck/2.0'}
        if headers:
            for k, v in headers.items():
                req_headers[k] = v

        if auth:
            if not isinstance(auth, (tuple, list)) or len(auth) != 2:
                raise ValueError("Auth parameter must be a tuple or list of (username, password)")
            import base64
            auth_str = f"{auth[0]}:{auth[1]}"
            auth_bytes = auth_str.encode('utf-8')
            b64_auth = base64.b64encode(auth_bytes).decode('utf-8')
            req_headers["Authorization"] = f"Basic {b64_auth}"


        req = urllib.request.Request(
            target_url,
            headers=req_headers,
            method=method.upper()
        )

        with urllib.request.urlopen(req, timeout=timeout) as response:
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            final_url = response.geturl()
            status_code = response.getcode()
            resp_headers = {k.lower(): v for k, v in response.info().items()}

            # Estimate response size
            content_length = resp_headers.get("content-length")
            if content_length is not None:
                try:
                    size_bytes = int(content_length)
                except ValueError:
                    size_bytes = 0
            else:
                # Read response safely up to 1MB
                content = response.read(1024 * 1024)
                size_bytes = len(content)

            result["latency_ms"] = round(duration_ms, 2)
            # Success is defined as any status code < 400
            result["success"] = (200 <= status_code < 400)
            result["status"] = "SUCCESS" if result["success"] else "FAILED"

            result["metadata"]["status_code"] = status_code
            result["metadata"]["size_bytes"] = size_bytes
            result["metadata"]["headers"] = resp_headers


            if final_url != target_url:
                result["metadata"]["redirect_url"] = final_url
                # If it's a redirect status but success, we can still report redirect status
                if 300 <= status_code < 400:
                    result["status"] = "REDIRECT"

    except urllib.error.HTTPError as e:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        result["latency_ms"] = round(duration_ms, 2)
        result["status"] = "FAILED"
        result["success"] = False
        result["error"] = f"HTTP Error {e.code}: {e.reason}"
        result["metadata"]["status_code"] = e.code
        result["metadata"]["headers"] = {k.lower(): v for k, v in e.headers.items()}
    except urllib.error.URLError as e:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        result["latency_ms"] = round(duration_ms, 2)
        result["status"] = "FAILED"
        result["success"] = False
        result["error"] = f"URL Error: {e.reason}"
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        result["latency_ms"] = round(duration_ms, 2)
        result["status"] = "FAILED"
        result["success"] = False
        result["error"] = str(e)

    return result
