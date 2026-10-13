"""Parser for proxy list files and proxy strings."""

from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urlsplit

from proxy_check.models import Proxy

SUPPORTED_SCHEMES = {"http", "https", "socks4", "socks4a", "socks5", "socks5h"}


class MissingPortError(ValueError):
    """Raised when a proxy string lacks a port and no default port was provided."""


def extract_port_from_input(user_input: str | int, default: int = 8080) -> int:
    """Extract and validate a port number from user input.

    Handles direct integers (8080), strings ('8080'), colon prefixes (':8080'),
    full host:port entries ('172.104.60.153:8080'), and full URLs ('http://host:8080').
    """
    raw = str(user_input).strip()
    if not raw:
        return default

    if "://" in raw:
        parts = urlsplit(raw)
        if parts.port is not None:
            return parts.port

    if ":" in raw:
        candidate = raw.rsplit(":", 1)[-1].strip()
        candidate = candidate.split("/")[0]
    else:
        candidate = raw

    try:
        port = int(candidate)
    except ValueError as err:
        raise ValueError(f"'{user_input}' does not contain a valid port number") from err

    if not (1 <= port <= 65535):
        raise ValueError(f"Port {port} is out of valid port range (1-65535)")

    return port


def parse_proxy(line: str, default_port: int | None = None) -> Proxy | None:
    """Parse a single proxy line into a Proxy instance.

    Supported formats:
    - scheme://host:port (e.g., http://1.2.3.4:8080, socks5://1.2.3.4:1080)
    - scheme://user:pass@host:port
    - user:pass@host:port
    - host:port:user:pass
    - host:port
    """
    clean = line.strip()
    if not clean or clean.startswith("#"):
        return None

    if "://" in clean:
        parts = urlsplit(clean)
        scheme = parts.scheme.lower()
        if scheme not in SUPPORTED_SCHEMES:
            raise ValueError(f"Unsupported proxy scheme: '{scheme}' in '{clean}'")

        if not parts.hostname or parts.port is None:
            raise ValueError(f"Invalid host or port in proxy: '{clean}'")

        return Proxy(
            raw=clean,
            host=parts.hostname,
            port=parts.port,
            scheme=scheme,
            username=parts.username,
            password=parts.password,
        )

    if "@" in clean:
        auth_part, host_part = clean.split("@", 1)
        if ":" in auth_part:
            username, password = auth_part.split(":", 1)
        else:
            username, password = auth_part, None

        if ":" not in host_part:
            raise ValueError(f"Missing port in proxy: '{clean}'")

        host, port_str = host_part.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError as err:
            raise ValueError(f"Invalid port '{port_str}' in proxy: '{clean}'") from err

        return Proxy(
            raw=clean,
            host=host,
            port=port,
            scheme=None,
            username=username,
            password=password,
        )

    colon_parts = clean.split(":")
    if len(colon_parts) == 2:
        host, port_str = colon_parts
        try:
            port = int(port_str)
        except ValueError as err:
            raise ValueError(f"Invalid port '{port_str}' in proxy: '{clean}'") from err

        return Proxy(
            raw=clean,
            host=host,
            port=port,
            scheme=None,
        )

    if len(colon_parts) == 4:
        host, port_str, username, password = colon_parts
        try:
            port = int(port_str)
        except ValueError as err:
            raise ValueError(f"Invalid port '{port_str}' in proxy: '{clean}'") from err

        return Proxy(
            raw=clean,
            host=host,
            port=port,
            scheme=None,
            username=username,
            password=password,
        )

    if ":" not in clean and "://" not in clean:
        if default_port is not None:
            return Proxy(
                raw=f"{clean}:{default_port}",
                host=clean,
                port=default_port,
                scheme=None,
            )
        raise MissingPortError(
            f"Missing port in proxy: '{clean}' (expected format: host:port, or use --default-port)"
        )

    raise ValueError(f"Unrecognized proxy format: '{clean}'")


def parse_proxies(lines: Iterable[str], default_port: int | None = None) -> list[Proxy]:
    """Parse multiple proxy lines, ignoring empty lines and comments."""
    proxies: list[Proxy] = []
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            proxy = parse_proxy(stripped, default_port=default_port)
            if proxy is not None:
                proxies.append(proxy)
        except MissingPortError as e:
            raise MissingPortError(f"Line {idx}: {e}") from e
        except ValueError as e:
            raise ValueError(f"Line {idx}: {e}") from e
    return proxies


def parse_proxy_file(file_path: Path | str, default_port: int | None = None) -> list[Proxy]:
    """Read a text file with one proxy per line and parse all valid proxies."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Proxy file not found: {path}")

    content = path.read_text(encoding="utf-8")
    return parse_proxies(content.splitlines(), default_port=default_port)
