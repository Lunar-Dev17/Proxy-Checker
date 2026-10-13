"""Unit tests for proxy checker logic with mocked responses."""

import asyncio
from unittest.mock import AsyncMock, patch

import httpx

from proxy_check.checker import (
    ProxyChecker,
    extract_exit_ip,
    format_error,
)
from proxy_check.models import Proxy


def test_extract_exit_ip_json_origin():
    raw = '{"origin": "198.51.100.42"}'
    assert extract_exit_ip(raw) == "198.51.100.42"


def test_extract_exit_ip_json_comma_separated():
    raw = '{"origin": "203.0.113.19, 198.51.100.42"}'
    assert extract_exit_ip(raw) == "203.0.113.19"


def test_extract_exit_ip_json_ip_key():
    raw = '{"ip": "198.51.100.99"}'
    assert extract_exit_ip(raw) == "198.51.100.99"


def test_extract_exit_ip_plaintext():
    raw = "Your IP is 192.0.2.1."
    assert extract_exit_ip(raw) == "192.0.2.1"


def test_extract_exit_ip_invalid():
    raw = "<html><body>Error 500</body></html>"
    assert extract_exit_ip(raw) is None


def test_format_error():
    assert "Timeout (5.0s)" in format_error(httpx.ReadTimeout("timed out"), 5.0)
    assert "Connection refused" in format_error(
        httpx.ConnectError("Connection refused by peer"), 5.0
    )


def test_check_working_proxy_explicit_scheme():
    async def _run():
        checker = ProxyChecker(timeout=5.0, concurrency=10, judge_url=None, geo_provider=None)
        proxy = Proxy(raw="socks5://1.2.3.4:1080", host="1.2.3.4", port=1080, scheme="socks5")

        mock_response = httpx.Response(
            200,
            text='{"origin": "203.0.113.88"}',
            request=httpx.Request("GET", checker.target_url),
        )

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client

        with patch("proxy_check.checker.create_client", return_value=mock_client):
            result = await checker.check_proxy(proxy)

        assert result.is_alive is True
        assert result.protocol == "socks5"
        assert result.exit_ip == "203.0.113.88"
        assert result.latency_ms is not None
        assert result.error is None

    asyncio.run(_run())


def test_check_working_proxy_detect_protocol():
    async def _run():
        checker = ProxyChecker(timeout=5.0, concurrency=10, judge_url=None, geo_provider=None)
        proxy = Proxy(raw="1.2.3.4:8080", host="1.2.3.4", port=8080, scheme=None)

        def side_effect(proxy_url: str, timeout: float):
            client = AsyncMock()
            client.__aenter__.return_value = client
            if "http://" in proxy_url:
                client.get.return_value = httpx.Response(
                    200,
                    text='{"origin": "198.51.100.5"}',
                    request=httpx.Request("GET", checker.target_url),
                )
            else:
                client.get.side_effect = httpx.ConnectError("Connection refused")
            return client

        with patch("proxy_check.checker.create_client", side_effect=side_effect):
            result = await checker.check_proxy(proxy)

        assert result.is_alive is True
        assert result.protocol == "http"
        assert result.exit_ip == "198.51.100.5"

    asyncio.run(_run())


def test_check_proxy_timeout():
    async def _run():
        checker = ProxyChecker(timeout=3.0, concurrency=10)
        proxy = Proxy(raw="http://1.2.3.4:8080", host="1.2.3.4", port=8080, scheme="http")

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("timed out")
        mock_client.__aenter__.return_value = mock_client

        with patch("proxy_check.checker.create_client", return_value=mock_client):
            result = await checker.check_proxy(proxy)

        assert result.is_alive is False
        assert result.protocol == "http"
        assert "Timeout (3.0s)" in result.error

    asyncio.run(_run())


def test_check_proxy_auth_required():
    async def _run():
        checker = ProxyChecker(timeout=3.0, concurrency=10)
        proxy = Proxy(raw="http://1.2.3.4:8080", host="1.2.3.4", port=8080, scheme="http")

        mock_response = httpx.Response(
            407,
            text="Proxy Authentication Required",
            request=httpx.Request("GET", checker.target_url),
        )
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client

        with patch("proxy_check.checker.create_client", return_value=mock_client):
            result = await checker.check_proxy(proxy)

        assert result.is_alive is False
        assert "Proxy authentication required" in result.error

    asyncio.run(_run())


def test_check_proxies_stream():
    async def _run():
        checker = ProxyChecker(timeout=3.0, concurrency=5, judge_url=None, geo_provider=None)
        proxies = [
            Proxy(raw=f"http://1.1.1.{i}:8080", host=f"1.1.1.{i}", port=8080, scheme="http")
            for i in range(1, 4)
        ]

        mock_response = httpx.Response(
            200,
            text='{"origin": "1.2.3.4"}',
            request=httpx.Request("GET", checker.target_url),
        )
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client

        with patch("proxy_check.checker.create_client", return_value=mock_client):
            results = [res async for res in checker.check_proxies_stream(proxies)]

        assert len(results) == 3
        assert all(r.is_alive for r in results)

    asyncio.run(_run())


def test_check_proxy_with_anonymity_geo_target():
    async def _run():
        checker = ProxyChecker(
            timeout=3.0,
            concurrency=5,
            judge_url="https://httpbin.org/headers",
            geo_provider="ip-api",
            target="https://target.com",
            real_ip="192.0.2.1",
        )
        proxy = Proxy(raw="http://1.2.3.4:8080", host="1.2.3.4", port=8080, scheme="http")

        def mock_get(url, **kwargs):
            if "headers" in str(url):
                # Judge response with no proxy headers
                return httpx.Response(
                    200,
                    text='{"headers": {"Host": "target"}}',
                    request=httpx.Request("GET", str(url)),
                )
            if "target.com" in str(url):
                # Target response
                return httpx.Response(
                    200, text="<html>welcome</html>", request=httpx.Request("GET", str(url))
                )
            # Default IP target
            return httpx.Response(
                200, text='{"origin": "203.0.113.50"}', request=httpx.Request("GET", str(url))
            )

        mock_client = AsyncMock()
        mock_client.get.side_effect = mock_get
        mock_client.__aenter__.return_value = mock_client

        with patch("proxy_check.checker.create_client", return_value=mock_client):
            with patch.object(
                checker.geo_lookup,
                "lookup",
                AsyncMock(return_value=type("G", (), {"country": "US", "asn": "AS12345"})()),
            ):
                result = await checker.check_proxy(proxy)

        assert result.is_alive is True
        assert result.anonymity == "elite"
        assert result.country == "US"
        assert result.asn == "AS12345"
        assert result.target_status == "Passed (200)"
        assert result.target_blocked is False

    asyncio.run(_run())
