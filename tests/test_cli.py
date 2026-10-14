"""Tests for CLI."""

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from proxy_check import __version__
from proxy_check.cli import app
from proxy_check.models import CheckResult

runner = CliRunner()


def test_version_command():
    """Test `proxy-check version` command."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_version_option():
    """Test `proxy-check --version` option."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_check_command_file_not_found():
    """Test check command with missing file."""
    result = runner.invoke(app, ["check", "non_existent_file.txt"])
    assert result.exit_code != 0


def test_check_command_success(tmp_path: Path):
    """Test check command with live progress and sorted summary table."""
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text("1.2.3.4:8080\n", encoding="utf-8")

    mock_result = CheckResult(
        proxy="1.2.3.4:8080",
        is_alive=True,
        latency_ms=45.2,
        protocol="http",
        exit_ip="203.0.113.1",
    )

    async def mock_stream(self, proxies):
        yield mock_result

    with patch("proxy_check.checker.ProxyChecker.check_proxies_stream", mock_stream):
        result = runner.invoke(
            app, ["check", str(proxy_file), "--concurrency", "10", "--timeout", "5"]
        )
        assert result.exit_code == 0
        assert "ALIVE" in result.stdout
        assert "203.0.113.1" in result.stdout
        assert "45.2 ms" in result.stdout
        assert "Tested: 1/1" in result.stdout
        assert "Alive: 1" in result.stdout


def test_check_command_with_target_and_options(tmp_path: Path):
    """Test check command with target, anonymity, and geo flags."""
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text("1.2.3.4:8080\n", encoding="utf-8")

    mock_result = CheckResult(
        proxy="1.2.3.4:8080",
        is_alive=True,
        latency_ms=45.2,
        protocol="http",
        exit_ip="203.0.113.1",
        anonymity="elite",
        country="US",
        asn="AS15169",
        target_status="Passed (200)",
        target_blocked=False,
    )

    async def mock_stream(self, proxies):
        yield mock_result

    with patch("proxy_check.checker.ProxyChecker.check_proxies_stream", mock_stream):
        result = runner.invoke(
            app,
            [
                "check",
                str(proxy_file),
                "--target",
                "https://example.com",
                "--judge-url",
                "https://custom-judge.com",
                "--geo-provider",
                "ipinfo",
            ],
        )
        assert result.exit_code == 0
        assert "ALIVE" in result.stdout
        assert "elite" in result.stdout
        assert "US / AS15169" in result.stdout
        assert "Passed (200)" in result.stdout
        assert "Target: Passed: 1, Blocked: 0" in result.stdout


def test_check_command_exports_and_filters(tmp_path: Path):
    """Test exporting to JSON, working proxies file, and filtering."""
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text("1.2.3.4:8080\n5.6.7.8:1080\n", encoding="utf-8")
    out_json = tmp_path / "results.json"
    out_working = tmp_path / "working.txt"

    r1 = CheckResult(
        proxy="1.2.3.4:8080",
        is_alive=True,
        latency_ms=30.0,
        protocol="http",
        exit_ip="1.2.3.4",
        country="US",
        anonymity="elite",
    )
    r2 = CheckResult(
        proxy="socks5://5.6.7.8:1080",
        is_alive=True,
        latency_ms=300.0,
        protocol="socks5",
        exit_ip="5.6.7.8",
        country="DE",
        anonymity="anonymous",
    )

    async def mock_stream(self, proxies):
        yield r1
        yield r2

    with patch("proxy_check.checker.ProxyChecker.check_proxies_stream", mock_stream):
        result = runner.invoke(
            app,
            [
                "check",
                str(proxy_file),
                "--protocol",
                "http",
                "--country",
                "US",
                "--anonymity",
                "elite",
                "--max-latency",
                "100",
                "--output",
                str(out_json),
                "--output-working",
                str(out_working),
            ],
        )
        assert result.exit_code == 0
        assert "Matching Filters: 1" in result.stdout

    assert out_json.exists()
    exported_data = json.loads(out_json.read_text(encoding="utf-8"))
    assert len(exported_data) == 1
    assert exported_data[0]["proxy"] == "1.2.3.4:8080"

    assert out_working.exists()
    working_content = out_working.read_text(encoding="utf-8")
    assert "http://1.2.3.4:8080" in working_content
    assert "socks5://5.6.7.8:1080" not in working_content


def test_check_command_keyboard_interrupt_saves_partial(tmp_path: Path):
    """Test that Ctrl+C saves partial results and exits with code 130."""
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text("1.1.1.1:80\n2.2.2.2:80\n", encoding="utf-8")
    out_json = tmp_path / "partial.json"
    out_working = tmp_path / "partial_working.txt"

    r1 = CheckResult(
        proxy="1.1.1.1:80",
        is_alive=True,
        latency_ms=25.0,
        protocol="http",
    )

    async def mock_stream_interrupt(self, proxies):
        yield r1
        raise KeyboardInterrupt()

    with patch("proxy_check.checker.ProxyChecker.check_proxies_stream", mock_stream_interrupt):
        result = runner.invoke(
            app,
            [
                "check",
                str(proxy_file),
                "--output",
                str(out_json),
                "--output-working",
                str(out_working),
            ],
        )
        assert result.exit_code == 130
        assert "interrupted by user" in result.stdout.lower()
        assert out_json.exists()
        saved = json.loads(out_json.read_text(encoding="utf-8"))
        assert len(saved) == 1
        assert saved[0]["proxy"] == "1.1.1.1:80"
        assert out_working.exists()
        assert "http://1.1.1.1:80" in out_working.read_text(encoding="utf-8")


def test_check_command_missing_port_non_interactive(tmp_path: Path):
    """Test check command when port is missing and stdin is non-interactive."""
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text("1.1.1.1\n", encoding="utf-8")

    with patch("proxy_check.cli.is_interactive", return_value=False):
        result = runner.invoke(app, ["check", str(proxy_file)])
        assert result.exit_code == 1
        assert "Missing port in proxy" in result.stdout
        assert "--default-port" in result.stdout


def test_check_command_with_default_port_flag(tmp_path: Path):
    """Test check command when port is missing but --default-port is provided."""
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text("1.1.1.1\n", encoding="utf-8")

    mock_result = CheckResult(
        proxy="1.1.1.1:8080",
        is_alive=True,
        latency_ms=15.0,
        protocol="http",
    )

    async def mock_stream(self, proxies):
        assert proxies[0].port == 8080
        yield mock_result

    with patch("proxy_check.checker.ProxyChecker.check_proxies_stream", mock_stream):
        result = runner.invoke(app, ["check", str(proxy_file), "--default-port", "8080"])
        assert result.exit_code == 0
        assert "ALIVE" in result.stdout


def test_check_command_missing_port_interactive_prompt(tmp_path: Path):
    """Test check command prompts interactively when port is missing and session is interactive."""
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text("1.1.1.1\n", encoding="utf-8")

    mock_result = CheckResult(
        proxy="1.1.1.1:3128",
        is_alive=True,
        latency_ms=20.0,
        protocol="http",
    )

    async def mock_stream(self, proxies):
        assert proxies[0].port == 3128
        yield mock_result

    with (
        patch("proxy_check.cli.is_interactive", return_value=True),
        patch("proxy_check.checker.ProxyChecker.check_proxies_stream", mock_stream),
    ):
        result = runner.invoke(app, ["check", str(proxy_file)], input="3128\n")
        assert result.exit_code == 0
        assert "Enter default port for proxies without one" in result.stdout
        assert "ALIVE" in result.stdout


def test_check_command_missing_port_interactive_pasted_ip_port(tmp_path: Path):
    """Test check command handles pasting a full IP:port string like '172.104.60.153:8080'."""
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text("172.104.60.153\n", encoding="utf-8")

    mock_result = CheckResult(
        proxy="172.104.60.153:8080",
        is_alive=True,
        latency_ms=20.0,
        protocol="http",
    )

    async def mock_stream(self, proxies):
        assert proxies[0].port == 8080
        yield mock_result

    with (
        patch("proxy_check.cli.is_interactive", return_value=True),
        patch("proxy_check.checker.ProxyChecker.check_proxies_stream", mock_stream),
    ):
        result = runner.invoke(app, ["check", str(proxy_file)], input="172.104.60.153:8080\n")
        assert result.exit_code == 0
        assert "Detected port 8080" in result.stdout
        assert "ALIVE" in result.stdout
