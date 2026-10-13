"""Unit tests for exporter and filtering utilities."""

import csv
import json
from pathlib import Path

from proxy_check.exporter import (
    export_results,
    export_working_proxies,
    filter_results,
)
from proxy_check.models import CheckResult


def sample_results():
    return [
        CheckResult(
            proxy="1.1.1.1:8080",
            is_alive=True,
            latency_ms=45.0,
            protocol="http",
            exit_ip="1.1.1.1",
            anonymity="elite",
            country="US",
            asn="AS123",
        ),
        CheckResult(
            proxy="socks5://2.2.2.2:1080",
            is_alive=True,
            latency_ms=180.0,
            protocol="socks5",
            exit_ip="2.2.2.2",
            anonymity="anonymous",
            country="DE",
            asn="AS456",
        ),
        CheckResult(
            proxy="3.3.3.3:3128",
            is_alive=False,
            latency_ms=None,
            protocol="http",
            error="Timeout (10.0s)",
        ),
    ]


def test_filter_results_protocol():
    results = sample_results()
    http_res = filter_results(results, protocol="http")
    assert len(http_res) == 2

    socks_res = filter_results(results, protocol="socks5")
    assert len(socks_res) == 1
    assert socks_res[0].proxy == "socks5://2.2.2.2:1080"


def test_filter_results_country():
    results = sample_results()
    us_res = filter_results(results, country="US")
    assert len(us_res) == 1
    assert us_res[0].proxy == "1.1.1.1:8080"


def test_filter_results_anonymity():
    results = sample_results()
    elite_res = filter_results(results, anonymity="elite")
    assert len(elite_res) == 1
    assert elite_res[0].anonymity == "elite"


def test_filter_results_max_latency():
    results = sample_results()
    fast_res = filter_results(results, max_latency=50.0)
    assert len(fast_res) == 1
    assert fast_res[0].latency_ms == 45.0


def test_filter_combined():
    results = sample_results()
    res = filter_results(results, protocol="http", country="US", max_latency=100.0)
    assert len(res) == 1
    assert res[0].proxy == "1.1.1.1:8080"


def test_export_results_json(tmp_path: Path):
    dest = tmp_path / "results.json"
    results = sample_results()
    export_results(results, dest)

    assert dest.exists()
    data = json.loads(dest.read_text(encoding="utf-8"))
    assert len(data) == 3
    assert data[0]["proxy"] == "1.1.1.1:8080"
    assert data[0]["is_alive"] is True
    assert data[1]["protocol"] == "socks5"


def test_export_results_csv(tmp_path: Path):
    dest = tmp_path / "results.csv"
    results = sample_results()
    export_results(results, dest)

    assert dest.exists()
    with dest.open("r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        assert len(reader) == 3
        assert reader[0]["proxy"] == "1.1.1.1:8080"
        assert reader[0]["is_alive"] == "True"
        assert reader[1]["protocol"] == "socks5"


def test_export_working_proxies(tmp_path: Path):
    dest = tmp_path / "working.txt"
    results = sample_results()
    export_working_proxies(results, dest)

    assert dest.exists()
    lines = dest.read_text(encoding="utf-8").splitlines()
    # Only 2 working proxies, and 1.1.1.1:8080 without scheme gets prepended with http://
    assert len(lines) == 2
    assert "http://1.1.1.1:8080" in lines
    assert "socks5://2.2.2.2:1080" in lines
