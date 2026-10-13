"""Unit tests for Geo and ASN lookup with caching and rate limit handling."""

import asyncio
from unittest.mock import AsyncMock

import httpx

from proxy_check.geo import GeoLookup


def test_resolve_url():
    lookup = GeoLookup(provider="ip-api")
    assert "ip-api.com" in lookup._resolve_url("1.2.3.4")

    lookup_custom = GeoLookup(provider="https://api.example.com/{ip}")
    assert lookup_custom._resolve_url("1.2.3.4") == "https://api.example.com/1.2.3.4"


def test_parse_response_ip_api():
    lookup = GeoLookup()
    data = {
        "status": "success",
        "country": "United States",
        "countryCode": "US",
        "as": "AS15169 Google LLC",
    }
    info = lookup._parse_response(data)
    assert info.country == "US"
    assert info.asn == "AS15169 Google LLC"


def test_parse_response_ipinfo():
    lookup = GeoLookup(provider="ipinfo")
    data = {
        "country": "DE",
        "org": "AS24940 Hetzner Online GmbH",
    }
    info = lookup._parse_response(data)
    assert info.country == "DE"
    assert info.asn == "AS24940 Hetzner Online GmbH"


def test_geo_lookup_caching():
    async def _run():
        lookup = GeoLookup(provider="ip-api")
        mock_client = AsyncMock()
        mock_response = httpx.Response(
            200,
            json={
                "status": "success",
                "country": "Canada",
                "countryCode": "CA",
                "as": "AS812 Rogers",
            },
            request=httpx.Request("GET", "http://ip-api.com/json/198.51.100.1"),
        )
        mock_client.get.return_value = mock_response

        info1 = await lookup.lookup("198.51.100.1", client=mock_client)
        assert info1 is not None
        assert info1.country == "CA"
        assert info1.asn == "AS812 Rogers"
        assert mock_client.get.call_count == 1

        info2 = await lookup.lookup("198.51.100.1", client=mock_client)
        assert info2 == info1
        assert mock_client.get.call_count == 1

    asyncio.run(_run())


def test_geo_lookup_rate_limiting_http_429():
    async def _run():
        lookup = GeoLookup(provider="ip-api")
        mock_client = AsyncMock()
        mock_response = httpx.Response(
            429,
            text="Too Many Requests",
            request=httpx.Request("GET", "http://ip-api.com/json/198.51.100.2"),
        )
        mock_client.get.return_value = mock_response

        info = await lookup.lookup("198.51.100.2", client=mock_client)
        assert info is not None
        assert info.country == "Rate-Limited"

        info_next = await lookup.lookup("198.51.100.3", client=mock_client)
        assert info_next is not None
        assert info_next.country == "Rate-Limited"

    asyncio.run(_run())


def test_geo_lookup_rate_limiting_json_status():
    async def _run():
        lookup = GeoLookup(provider="ip-api")
        mock_client = AsyncMock()
        mock_response = httpx.Response(
            200,
            json={"status": "fail", "message": "user rate limited"},
            request=httpx.Request("GET", "http://ip-api.com/json/198.51.100.4"),
        )
        mock_client.get.return_value = mock_response

        info = await lookup.lookup("198.51.100.4", client=mock_client)
        assert info is not None
        assert info.country == "Rate-Limited"

    asyncio.run(_run())


def test_geo_lookup_handles_network_error():
    async def _run():
        lookup = GeoLookup(provider="ip-api")
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Network unreachable")

        info = await lookup.lookup("198.51.100.5", client=mock_client)
        assert info is None

    asyncio.run(_run())
