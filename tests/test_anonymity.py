"""Unit tests for anonymity detection."""

import asyncio
from unittest.mock import AsyncMock

import httpx

from proxy_check.anonymity import (
    check_anonymity,
    classify_anonymity,
    parse_judge_headers,
)


def test_parse_judge_headers_json():
    body = '{"headers": {"Host": "httpbin.org", "Via": "1.1 squid", "User-Agent": "curl"}}'
    headers = parse_judge_headers(body)
    assert headers["host"] == "httpbin.org"
    assert headers["via"] == "1.1 squid"
    assert headers["user-agent"] == "curl"


def test_parse_judge_headers_plaintext():
    body = """
    REMOTE_ADDR = 198.51.100.2
    HTTP_VIA = 1.1 proxy.domain.com
    HTTP_X_FORWARDED_FOR = 203.0.113.1
    """
    headers = parse_judge_headers(body)
    assert headers["remote-addr"] == "198.51.100.2"
    assert headers["via"] == "1.1 proxy.domain.com"
    assert headers["x-forwarded-for"] == "203.0.113.1"


def test_classify_anonymity_transparent():
    # User's real IP is leaked in X-Forwarded-For
    headers = {
        "host": "example.com",
        "via": "1.1 squid",
        "x-forwarded-for": "203.0.113.99, 198.51.100.1",
    }
    level = classify_anonymity(headers, real_ip="203.0.113.99")
    assert level == "transparent"


def test_classify_anonymity_anonymous():
    # Proxy header present, but real IP is not leaked
    headers = {
        "host": "example.com",
        "via": "1.1 squid",
        "x-forwarded-for": "198.51.100.1",
    }
    level = classify_anonymity(headers, real_ip="203.0.113.99")
    assert level == "anonymous"


def test_classify_anonymity_elite():
    # No proxy headers, no real IP leaked
    headers = {
        "host": "example.com",
        "user-agent": "Mozilla/5.0",
        "accept": "*/*",
    }
    level = classify_anonymity(headers, real_ip="203.0.113.99")
    assert level == "elite"


def test_check_anonymity_async():
    async def _run():
        mock_client = AsyncMock()
        mock_response = httpx.Response(
            200,
            text='{"headers": {"Host": "httpbin.org"}}',
            request=httpx.Request("GET", "https://httpbin.org/headers"),
        )
        mock_client.get.return_value = mock_response

        level, err = await check_anonymity(
            mock_client,
            "https://httpbin.org/headers",
            real_ip="1.2.3.4",
        )
        assert level == "elite"
        assert err is None

    asyncio.run(_run())


def test_check_anonymity_error():
    async def _run():
        mock_client = AsyncMock()
        mock_response = httpx.Response(
            500,
            text="Internal Server Error",
            request=httpx.Request("GET", "https://httpbin.org/headers"),
        )
        mock_client.get.return_value = mock_response

        level, err = await check_anonymity(
            mock_client,
            "https://httpbin.org/headers",
        )
        assert level is None
        assert "HTTP 500" in err

    asyncio.run(_run())
