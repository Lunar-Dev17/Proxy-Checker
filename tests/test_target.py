"""Unit tests for target site testing and block/captcha detection."""

import asyncio
from unittest.mock import AsyncMock

import httpx

from proxy_check.target import check_target_site, is_captcha_page


def test_is_captcha_page_detection():
    # Cloudflare challenge
    assert is_captcha_page(
        403, "<html><title>Just a moment...</title><div id='challenge-platform'></div></html>"
    )
    assert is_captcha_page(
        200,
        "<script src='https://challenges.cloudflare.com/turnstile/v0/api.js'></script>cf-turnstile",
    )

    # reCAPTCHA & hCaptcha
    assert is_captcha_page(200, "<div class='g-recaptcha' data-sitekey='xyz'></div>")
    assert is_captcha_page(200, "<script src='https://hcaptcha.com/1/api.js'></script>")

    # PerimeterX & DataDome
    assert is_captcha_page(403, "<script>window._pxAppId = 'PX123';</script>perimeterx")
    assert is_captcha_page(403, "<html>datadome captcha challenge</html>")

    # Clean HTML
    assert not is_captcha_page(
        200, "<html><head><title>Scraping Target</title></head><body><h1>Welcome</h1></body></html>"
    )


def test_check_target_site_passed():
    async def _run():
        mock_client = AsyncMock()
        mock_client.get.return_value = httpx.Response(
            200,
            text="<html><h1>Normal content</h1></html>",
            request=httpx.Request("GET", "https://example.com"),
        )
        blocked, status = await check_target_site(mock_client, "https://example.com")
        assert blocked is False
        assert status == "Passed (200)"

    asyncio.run(_run())


def test_check_target_site_blocked_403():
    async def _run():
        mock_client = AsyncMock()
        mock_client.get.return_value = httpx.Response(
            403,
            text="Forbidden",
            request=httpx.Request("GET", "https://example.com"),
        )
        blocked, status = await check_target_site(mock_client, "https://example.com")
        assert blocked is True
        assert status == "Blocked (403)"

    asyncio.run(_run())


def test_check_target_site_blocked_429():
    async def _run():
        mock_client = AsyncMock()
        mock_client.get.return_value = httpx.Response(
            429,
            text="Too Many Requests",
            request=httpx.Request("GET", "https://example.com"),
        )
        blocked, status = await check_target_site(mock_client, "https://example.com")
        assert blocked is True
        assert status == "Blocked (429)"

    asyncio.run(_run())


def test_check_target_site_blocked_captcha():
    async def _run():
        mock_client = AsyncMock()
        mock_client.get.return_value = httpx.Response(
            200,
            text="<html><title>Just a moment...</title>cf-challenge</html>",
            request=httpx.Request("GET", "https://example.com"),
        )
        blocked, status = await check_target_site(mock_client, "https://example.com")
        assert blocked is True
        assert status == "Blocked (Captcha)"

    asyncio.run(_run())


def test_check_target_site_connection_failed():
    async def _run():
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")
        blocked, status = await check_target_site(mock_client, "https://example.com")
        assert blocked is True
        assert "Failed" in status

    asyncio.run(_run())
