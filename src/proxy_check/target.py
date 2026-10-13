"""Target site verification and bot/captcha block detection."""

import re

import httpx

CAPTCHA_PATTERNS = [
    re.compile(r"cf-turnstile", re.IGNORECASE),
    re.compile(r"cf-challenge", re.IGNORECASE),
    re.compile(r"challenge-platform", re.IGNORECASE),
    re.compile(r"cf-browser-verification", re.IGNORECASE),
    re.compile(r"Just a moment\.\.\.", re.IGNORECASE),
    re.compile(r"g-recaptcha", re.IGNORECASE),
    re.compile(r"recaptcha/api", re.IGNORECASE),
    re.compile(r"hcaptcha\.com", re.IGNORECASE),
    re.compile(r"h-captcha", re.IGNORECASE),
    re.compile(r"perimeterx", re.IGNORECASE),
    re.compile(r"px-captcha", re.IGNORECASE),
    re.compile(r"datadome", re.IGNORECASE),
    re.compile(r"verify you are (?:a )?human", re.IGNORECASE),
    re.compile(r"security check to access", re.IGNORECASE),
    re.compile(r"attention required!\s+\|\s+cloudflare", re.IGNORECASE),
]


def is_captcha_page(status_code: int, html: str) -> bool:
    """Detect whether a response contains a captcha or bot-protection challenge."""
    if not html:
        return False

    for pattern in CAPTCHA_PATTERNS:
        if pattern.search(html):
            return True

    if status_code in (403, 429, 503):
        if re.search(r"\b(?:captcha|bot detection|access denied)\b", html, re.IGNORECASE):
            return True

    return False


async def check_target_site(
    client: httpx.AsyncClient,
    target_url: str,
) -> tuple[bool, str]:
    """Test proxy against a target site and detect blocks.

    Returns:
        (is_blocked, status_message)
        e.g. (False, "Passed (200)") or (True, "Blocked (403)"), (True, "Blocked (Captcha)")
    """
    try:
        response = await client.get(target_url, follow_redirects=True)

        if is_captcha_page(response.status_code, response.text):
            return True, "Blocked (Captcha)"

        if response.status_code == 403:
            return True, "Blocked (403)"
        if response.status_code == 429:
            return True, "Blocked (429)"

        if response.is_error:
            return True, f"Blocked (HTTP {response.status_code})"

        return False, f"Passed ({response.status_code})"

    except Exception as exc:
        return True, f"Failed: {exc}"
