"""Core async proxy checking logic."""

import asyncio
import json
import re
import time
from collections.abc import AsyncIterator, Callable, Sequence

import httpx
from httpx_socks import AsyncProxyTransport

from proxy_check.anonymity import DEFAULT_JUDGE_URL, check_anonymity
from proxy_check.geo import GeoLookup
from proxy_check.models import CheckResult, Proxy
from proxy_check.target import check_target_site

DEFAULT_TARGET_URL = "https://httpbin.org/ip"
DEFAULT_TIMEOUT = 10.0
DEFAULT_CONCURRENCY = 50
CANDIDATE_PROTOCOLS = ("http", "socks5", "socks4")


def extract_exit_ip(text: str) -> str | None:
    """Extract public IP address from JSON or plain text response."""
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            val = data.get("origin") or data.get("ip")
            if isinstance(val, str):
                ips = [ip.strip() for ip in val.split(",") if ip.strip()]
                if ips:
                    return ips[0]
    except Exception:
        pass

    ipv4_match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text)
    if ipv4_match:
        return ipv4_match.group(0)

    ipv6_match = re.search(r"\b(?:[a-fA-F0-9]{1,4}:){7}[a-fA-F0-9]{1,4}\b", text)
    if ipv6_match:
        return ipv6_match.group(0)

    return None


def format_error(exc: Exception, timeout: float) -> str:
    """Format exceptions into clear, human-readable failure reasons."""
    if isinstance(exc, (httpx.TimeoutException, asyncio.TimeoutError)):
        return f"Timeout ({timeout:.1f}s)"
    if isinstance(exc, httpx.ConnectError):
        msg = str(exc)
        if "Connection refused" in msg or "Connect call failed" in msg:
            return "Connection refused"
        return f"Connection failed: {msg}" if msg else "Connection failed"
    if isinstance(exc, httpx.ProxyError):
        return f"Proxy error: {exc}"
    if isinstance(exc, httpx.HTTPStatusError):
        if exc.response.status_code == 407:
            return "Proxy authentication required (HTTP 407)"
        return f"HTTP {exc.response.status_code} error"

    exc_name = type(exc).__name__
    msg = str(exc).strip()
    return f"{exc_name}: {msg}" if msg else exc_name


def create_client(proxy_url: str, timeout: float) -> httpx.AsyncClient:
    """Instantiate an httpx.AsyncClient with appropriate proxy transport."""
    scheme = proxy_url.split("://", 1)[0].lower()
    if scheme.startswith("socks"):
        transport = AsyncProxyTransport.from_url(proxy_url)
        return httpx.AsyncClient(transport=transport, timeout=timeout)
    return httpx.AsyncClient(proxy=proxy_url, timeout=timeout)


class ProxyChecker:
    """Async checker for testing proxies concurrently."""

    def __init__(
        self,
        target_url: str = DEFAULT_TARGET_URL,
        timeout: float = DEFAULT_TIMEOUT,
        concurrency: int = DEFAULT_CONCURRENCY,
        judge_url: str | None = DEFAULT_JUDGE_URL,
        geo_provider: str | None = "ip-api",
        target: str | None = None,
        real_ip: str | None = None,
    ) -> None:
        self.target_url = target_url
        self.timeout = timeout
        self.concurrency = concurrency
        self.judge_url = judge_url
        self.target = target
        self.real_ip = real_ip
        self._real_ip_resolved: str | None = real_ip
        self._real_ip_lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(concurrency)
        self.geo_lookup = (
            GeoLookup(provider=geo_provider, timeout=timeout) if geo_provider else None
        )

    async def get_real_ip(self) -> str | None:
        """Fetch the direct client IP once if not already resolved."""
        if self._real_ip_resolved is not None:
            return self._real_ip_resolved

        async with self._real_ip_lock:
            if self._real_ip_resolved is not None:
                return self._real_ip_resolved
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get(self.target_url)
                    self._real_ip_resolved = extract_exit_ip(resp.text)
            except Exception:
                self._real_ip_resolved = None
            return self._real_ip_resolved

    async def _test_protocol(self, proxy: Proxy, scheme: str) -> CheckResult:
        """Test a proxy using a specific protocol scheme."""
        proxy_url = proxy.to_url(scheme=scheme)
        start_time = time.perf_counter()

        try:
            async with asyncio.timeout(self.timeout):
                async with create_client(proxy_url, timeout=self.timeout) as client:
                    response = await client.get(self.target_url)
                    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

                    if response.status_code == 407:
                        return CheckResult(
                            proxy=proxy.raw,
                            is_alive=False,
                            latency_ms=latency_ms,
                            protocol=scheme,
                            error="Proxy authentication required (HTTP 407)",
                        )

                    if response.is_error:
                        return CheckResult(
                            proxy=proxy.raw,
                            is_alive=False,
                            latency_ms=latency_ms,
                            protocol=scheme,
                            error=f"Target returned HTTP {response.status_code}",
                        )

                    exit_ip = extract_exit_ip(response.text)
                    if not exit_ip:
                        return CheckResult(
                            proxy=proxy.raw,
                            is_alive=False,
                            latency_ms=latency_ms,
                            protocol=scheme,
                            error="Could not extract exit IP from target response",
                        )

                    anonymity = None
                    if self.judge_url:
                        try:
                            real_ip = await self.get_real_ip()
                            anonymity, _ = await check_anonymity(
                                client, self.judge_url, real_ip=real_ip
                            )
                        except Exception:
                            anonymity = None

                    target_status = None
                    target_blocked = None
                    if self.target:
                        target_blocked, target_status = await check_target_site(client, self.target)

                    country = None
                    asn = None
                    if self.geo_lookup and exit_ip:
                        try:
                            geo_info = await self.geo_lookup.lookup(exit_ip)
                            if geo_info:
                                country = geo_info.country
                                asn = geo_info.asn
                        except Exception:
                            pass

                    return CheckResult(
                        proxy=proxy.raw,
                        is_alive=True,
                        latency_ms=latency_ms,
                        protocol=scheme,
                        exit_ip=exit_ip,
                        anonymity=anonymity,
                        country=country,
                        asn=asn,
                        target_status=target_status,
                        target_blocked=target_blocked,
                    )

        except Exception as exc:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return CheckResult(
                proxy=proxy.raw,
                is_alive=False,
                latency_ms=latency_ms,
                protocol=scheme,
                error=format_error(exc, self.timeout),
            )

    async def check_proxy(self, proxy: Proxy) -> CheckResult:
        """Check a single proxy.

        If a scheme was specified in the proxy, tests that scheme (confirmed).
        If no scheme was specified, tests candidate protocols concurrently
        and selects the first working protocol (detected).
        """
        async with self._semaphore:
            if proxy.scheme:
                return await self._test_protocol(proxy, proxy.scheme)

            tasks = [
                asyncio.create_task(self._test_protocol(proxy, scheme))
                for scheme in CANDIDATE_PROTOCOLS
            ]

            results: list[CheckResult] = []
            try:
                for completed in asyncio.as_completed(tasks):
                    res = await completed
                    results.append(res)
                    if res.is_alive:
                        for t in tasks:
                            if not t.done():
                                t.cancel()
                        return res
            finally:
                for t in tasks:
                    if not t.done():
                        t.cancel()

            http_result = next((r for r in results if r.protocol == "http"), results[0])
            return CheckResult(
                proxy=proxy.raw,
                is_alive=False,
                latency_ms=http_result.latency_ms,
                protocol=None,
                error=http_result.error,
            )

    async def check_proxies_stream(self, proxies: Sequence[Proxy]) -> AsyncIterator[CheckResult]:
        """Check multiple proxies concurrently and stream results as they finish."""
        tasks = [asyncio.create_task(self.check_proxy(p)) for p in proxies]
        for finished in asyncio.as_completed(tasks):
            yield await finished

    async def check_proxies(
        self,
        proxies: Sequence[Proxy],
        callback: Callable[[CheckResult], None] | None = None,
    ) -> list[CheckResult]:
        """Check multiple proxies concurrently and return all results."""
        results: list[CheckResult] = []
        async for result in self.check_proxies_stream(proxies):
            results.append(result)
            if callback:
                callback(result)
        return results
