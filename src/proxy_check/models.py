"""Data models for proxy-check."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Proxy:
    """Represents a parsed proxy configuration."""

    raw: str
    host: str
    port: int
    scheme: str | None = None
    username: str | None = None
    password: str | None = None

    def to_url(self, scheme: str | None = None) -> str:
        """Format the proxy as a URL with the given or configured scheme."""
        target_scheme = (scheme or self.scheme or "http").lower()
        if self.username is not None and self.password is not None:
            auth = f"{self.username}:{self.password}@"
        elif self.username is not None:
            auth = f"{self.username}@"
        else:
            auth = ""
        return f"{target_scheme}://{auth}{self.host}:{self.port}"

    def __str__(self) -> str:
        return self.raw


@dataclass
class CheckResult:
    """Represents the result of checking a single proxy."""

    proxy: str
    is_alive: bool
    latency_ms: float | None = None
    protocol: str | None = None
    exit_ip: str | None = None
    anonymity: str | None = None
    country: str | None = None
    asn: str | None = None
    target_status: str | None = None
    target_blocked: bool | None = None
    error: str | None = None
