"""Country and ASN lookup for exit IPs with caching and rate limit handling."""

import asyncio
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class GeoInfo:
    """Geographic and network information for an IP address."""

    country: str | None
    asn: str | None


class GeoLookup:
    """Asynchronous Geo and ASN lookup service with local in-memory caching."""

    PROVIDERS = {
        "ip-api": "http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,as",
        "ipinfo": "https://ipinfo.io/{ip}/json",
    }

    def __init__(
        self,
        provider: str = "ip-api",
        timeout: float = 5.0,
    ) -> None:
        self.provider = provider
        self.timeout = timeout
        self._cache: dict[str, GeoInfo | None] = {}
        self._lock = asyncio.Lock()
        self._rate_limited = False

    def _resolve_url(self, ip: str) -> str:
        """Resolve the provider URL for the given IP."""
        if self.provider in self.PROVIDERS:
            return self.PROVIDERS[self.provider].format(ip=ip)
        if "{ip}" in self.provider:
            return self.provider.format(ip=ip)
        return f"{self.provider.rstrip('/')}/{ip}"

    def _parse_response(self, data: dict) -> GeoInfo:
        """Extract country and ASN from provider JSON response."""
        # Check ip-api format
        if "as" in data:
            asn = data.get("as")
            country = data.get("countryCode") or data.get("country")
            return GeoInfo(country=country, asn=asn)

        # Check ipinfo format
        if "org" in data:
            asn = data.get("org")
            country = data.get("country")
            return GeoInfo(country=country, asn=asn)

        # General fallbacks
        country = data.get("country_code") or data.get("countryCode") or data.get("country")
        asn = data.get("asn") or data.get("as_number") or data.get("org")
        return GeoInfo(country=country, asn=str(asn) if asn else None)

    async def lookup(self, ip: str, client: httpx.AsyncClient | None = None) -> GeoInfo | None:
        """Look up country and ASN for an IP address with caching and rate limit handling."""
        if not ip:
            return None

        async with self._lock:
            # Check local cache
            if ip in self._cache:
                return self._cache[ip]

            if self._rate_limited:
                return GeoInfo(country="Rate-Limited", asn=None)

        url = self._resolve_url(ip)

        try:
            if client is not None:
                resp = await client.get(url, timeout=self.timeout)
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as local_client:
                    resp = await local_client.get(url)

            # Check rate limiting status
            if resp.status_code == 429:
                async with self._lock:
                    self._rate_limited = True
                    self._cache[ip] = GeoInfo(country="Rate-Limited", asn=None)
                return self._cache[ip]

            if resp.is_error:
                async with self._lock:
                    self._cache[ip] = None
                return None

            data = resp.json()

            # Check for provider-level rate-limit messages (e.g. ip-api.com)
            if isinstance(data, dict) and data.get("status") == "fail":
                msg = str(data.get("message", "")).lower()
                if "rate" in msg or "limit" in msg:
                    async with self._lock:
                        self._rate_limited = True
                        self._cache[ip] = GeoInfo(country="Rate-Limited", asn=None)
                    return self._cache[ip]
                async with self._lock:
                    self._cache[ip] = None
                return None

            info = self._parse_response(data)
            async with self._lock:
                self._cache[ip] = info
            return info

        except Exception:
            async with self._lock:
                self._cache[ip] = None
            return None
