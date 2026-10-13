"""Anonymity level detection for proxies."""

import json

import httpx

DEFAULT_JUDGE_URL = "https://httpbin.org/headers"

# Common headers that indicate proxy usage
PROXY_HEADERS = {
    "via",
    "x-forwarded-for",
    "x-forwarded-host",
    "x-forwarded-server",
    "x-forwarded-proto",
    "forwarded",
    "client-ip",
    "x-real-ip",
    "proxy-connection",
    "x-proxy-id",
    "mt-proxy-id",
    "surrogate-capability",
    "cf-connecting-ip",
    "true-client-ip",
}


def parse_judge_headers(body: str) -> dict[str, str]:
    """Parse header echo from JSON or plain text proxy judge responses."""
    # 1. Try parsing JSON (e.g., httpbin.org/headers)
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            headers = data.get("headers")
            if isinstance(headers, dict):
                return {k.lower(): str(v) for k, v in headers.items()}
            return {k.lower(): str(v) for k, v in data.items() if isinstance(v, (str, int, float))}
    except Exception:
        pass

    # 2. Try parsing plain text proxy judges (e.g. HTTP_VIA = ... or Header: Value)
    headers: dict[str, str] = {}
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            key = k.strip().lower()
            if key.startswith("http_"):
                key = key[5:]
            key = key.replace("_", "-")
            headers[key] = v.strip()
        elif ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()

    return headers


def classify_anonymity(headers: dict[str, str], real_ip: str | None = None) -> str:
    """Classify anonymity level:

    - transparent: leaks the user's real IP in header values
    - anonymous: reveals proxy usage (via proxy headers) without leaking real IP
    - elite: no trace of proxy usage in headers
    """
    # 1. Check if real IP is leaked anywhere in headers
    if real_ip and real_ip.strip():
        clean_ip = real_ip.strip()
        for v in headers.values():
            if clean_ip in v:
                return "transparent"

    # 2. Check if any proxy-revealing headers are present and non-empty
    for proxy_header in PROXY_HEADERS:
        if proxy_header in headers and headers[proxy_header].strip():
            return "anonymous"

    # 3. No proxy headers and real IP not leaked
    return "elite"


async def check_anonymity(
    client: httpx.AsyncClient,
    judge_url: str,
    real_ip: str | None = None,
) -> tuple[str | None, str | None]:
    """Request header-echo endpoint through client and classify anonymity.

    Returns:
        (anonymity_level, error_message)
    """
    try:
        response = await client.get(judge_url)
        if response.is_error:
            return None, f"Judge returned HTTP {response.status_code}"

        headers = parse_judge_headers(response.text)
        if not headers:
            return None, "Could not parse headers from judge response"

        anonymity = classify_anonymity(headers, real_ip=real_ip)
        return anonymity, None
    except Exception as exc:
        return None, f"Judge check failed: {exc}"
