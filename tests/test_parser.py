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

    with pytest.raises(ValueError, match="out of valid port range"):
        parse_proxy("1.2.3.4:0")

    with pytest.raises(ValueError, match="out of valid port range"):
        parse_proxy("1.2.3.4:70000")


def test_parse_readme_formats():
    """Verify that every proxy format listed in the README parses correctly."""
    p1 = parse_proxy("192.168.1.1:8080")
    assert p1 is not None and p1.host == "192.168.1.1" and p1.port == 8080

    p2 = parse_proxy("admin:secret@192.168.1.1:8080")
    assert p2 is not None and p2.host == "192.168.1.1" and p2.port == 8080
    assert p2.username == "admin" and p2.password == "secret"

    p3 = parse_proxy("192.168.1.1:8080:admin:secret")
    assert p3 is not None and p3.host == "192.168.1.1" and p3.port == 8080
    assert p3.username == "admin" and p3.password == "secret"

    p4 = parse_proxy("http://192.168.1.1:8080")
    assert p4 is not None and p4.scheme == "http" and p4.host == "192.168.1.1" and p4.port == 8080

    p5 = parse_proxy("https://192.168.1.1:8443")
    assert p5 is not None and p5.scheme == "https" and p5.host == "192.168.1.1" and p5.port == 8443

    p6 = parse_proxy("socks4://192.168.1.1:1080")
    assert p6 is not None and p6.scheme == "socks4" and p6.host == "192.168.1.1" and p6.port == 1080

    p7 = parse_proxy("socks5://admin:secret@192.168.1.1:1080")
    assert p7 is not None and p7.scheme == "socks5" and p7.host == "192.168.1.1" and p7.port == 1080
    assert p7.username == "admin" and p7.password == "secret"


def test_parse_extended_formats():
    """Test extended formats such as passwords with colons, IPv6, and scheme with trailing auth."""
    # Password with colons in host:port:user:pass
    p = parse_proxy("192.168.1.1:8080:myuser:p@ss:w0rd:123")
    assert p is not None and p.username == "myuser" and p.password == "p@ss:w0rd:123"

    # Scheme with host:port:user:pass
    p_scheme = parse_proxy("http://192.168.1.1:8080:admin:secret")
    assert p_scheme is not None
    assert p_scheme.scheme == "http" and p_scheme.host == "192.168.1.1" and p_scheme.port == 8080
    assert p_scheme.username == "admin" and p_scheme.password == "secret"

    # Bracketed IPv6
    p_ipv6 = parse_proxy("[2001:db8::1]:8080")
    assert p_ipv6 is not None and p_ipv6.host == "2001:db8::1" and p_ipv6.port == 8080

    p_ipv6_auth = parse_proxy("user:pass@[::1]:8080")
    assert p_ipv6_auth is not None and p_ipv6_auth.host == "::1" and p_ipv6_auth.port == 8080


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

    assert extract_port_from_input(8080) == 8080
    assert extract_port_from_input("8080") == 8080
    assert extract_port_from_input("  8080  ") == 8080

    assert extract_port_from_input("", default=8080) == 8080
    assert extract_port_from_input("   ", default=3128) == 3128

    assert extract_port_from_input(":8080") == 8080
    assert extract_port_from_input(" :3128 ") == 3128

    assert extract_port_from_input("172.104.60.153:8080") == 8080
    assert extract_port_from_input("example.com:1080") == 1080
    assert extract_port_from_input("user:pass@1.2.3.4:8080") == 8080

    assert extract_port_from_input("http://1.2.3.4:8080") == 8080
    assert extract_port_from_input("socks5://1.2.3.4:1080/path") == 1080

    with pytest.raises(ValueError, match="does not contain a valid port number"):
        extract_port_from_input("invalid")

    with pytest.raises(ValueError, match="out of valid port range"):
        extract_port_from_input("70000")

    with pytest.raises(ValueError, match="out of valid port range"):
        extract_port_from_input("0")
