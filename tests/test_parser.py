"""Unit tests for proxy parsing."""

from pathlib import Path

import pytest

from proxy_check.parser import parse_proxies, parse_proxy, parse_proxy_file


def test_parse_ip_port():
    proxy = parse_proxy("192.168.1.50:8080")
    assert proxy is not None
    assert proxy.host == "192.168.1.50"
    assert proxy.port == 8080
    assert proxy.scheme is None
    assert proxy.username is None
    assert proxy.password is None
    assert proxy.to_url(scheme="http") == "http://192.168.1.50:8080"


def test_parse_ip_with_default_port():
    proxy = parse_proxy("192.168.1.50", default_port=8080)
    assert proxy is not None
    assert proxy.host == "192.168.1.50"
    assert proxy.port == 8080
    assert proxy.raw == "192.168.1.50:8080"


def test_parse_user_pass_at_ip_port():
    proxy = parse_proxy("myuser:mypass@10.0.0.1:3128")
    assert proxy is not None
    assert proxy.host == "10.0.0.1"
    assert proxy.port == 3128
    assert proxy.username == "myuser"
    assert proxy.password == "mypass"
    assert proxy.scheme is None
    assert proxy.to_url(scheme="socks5") == "socks5://myuser:mypass@10.0.0.1:3128"


def test_parse_ip_port_user_pass():
    proxy = parse_proxy("10.0.0.1:3128:myuser:mypass")
    assert proxy is not None
    assert proxy.host == "10.0.0.1"
    assert proxy.port == 3128
    assert proxy.username == "myuser"
    assert proxy.password == "mypass"


def test_parse_schemes():
    schemes = ["http", "https", "socks4", "socks5"]
    for s in schemes:
        raw = f"{s}://1.2.3.4:9050"
        proxy = parse_proxy(raw)
        assert proxy is not None
        assert proxy.scheme == s
        assert proxy.host == "1.2.3.4"
        assert proxy.port == 9050
        assert proxy.to_url() == raw


def test_parse_scheme_with_auth():
    raw = "socks5://admin:secret@proxy.domain.com:1080"
    proxy = parse_proxy(raw)
    assert proxy is not None
    assert proxy.scheme == "socks5"
    assert proxy.host == "proxy.domain.com"
    assert proxy.port == 1080
    assert proxy.username == "admin"
    assert proxy.password == "secret"


def test_parse_comments_and_empty():
    assert parse_proxy("") is None
    assert parse_proxy("   ") is None
    assert parse_proxy("# comment") is None


def test_parse_invalid_format():
    with pytest.raises(ValueError):
        parse_proxy("invalid_proxy_without_port")

    with pytest.raises(ValueError):
        parse_proxy("ftp://1.2.3.4:21")

    with pytest.raises(ValueError):
        parse_proxy("1.2.3.4:invalid_port")


def test_parse_proxies_list():
    lines = [
        "# Sample list",
        "1.1.1.1:80",
        "",
        "socks5://2.2.2.2:1080",
        "user:pass@3.3.3.3:3128",
    ]
    proxies = parse_proxies(lines)
    assert len(proxies) == 3
    assert proxies[0].host == "1.1.1.1"
    assert proxies[1].scheme == "socks5"
    assert proxies[2].username == "user"


def test_parse_proxy_file(tmp_path: Path):
    file_path = tmp_path / "proxies.txt"
    file_path.write_text("1.1.1.1:8080\nsocks5://2.2.2.2:1080\n", encoding="utf-8")
    proxies = parse_proxy_file(file_path)
    assert len(proxies) == 2


def test_extract_port_from_input():
    from proxy_check.parser import extract_port_from_input

    # Direct integer or string
    assert extract_port_from_input(8080) == 8080
    assert extract_port_from_input("8080") == 8080
    assert extract_port_from_input("  8080  ") == 8080

    # Empty string defaults
    assert extract_port_from_input("", default=8080) == 8080
    assert extract_port_from_input("   ", default=3128) == 3128

    # Colon prefix
    assert extract_port_from_input(":8080") == 8080
    assert extract_port_from_input(" :3128 ") == 3128

    # Full host:port strings (user pasting an IP with port)
    assert extract_port_from_input("172.104.60.153:8080") == 8080
    assert extract_port_from_input("example.com:1080") == 1080
    assert extract_port_from_input("user:pass@1.2.3.4:8080") == 8080

    # Full URLs
    assert extract_port_from_input("http://1.2.3.4:8080") == 8080
    assert extract_port_from_input("socks5://1.2.3.4:1080/path") == 1080

    # Invalid values
    with pytest.raises(ValueError, match="does not contain a valid port number"):
        extract_port_from_input("invalid")

    with pytest.raises(ValueError, match="out of valid port range"):
        extract_port_from_input("70000")

    with pytest.raises(ValueError, match="out of valid port range"):
        extract_port_from_input("0")
