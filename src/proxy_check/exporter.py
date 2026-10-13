"""Export and filter utilities for proxy check results."""

import csv
import json
from dataclasses import asdict
from pathlib import Path

from proxy_check.models import CheckResult


def filter_results(
    results: list[CheckResult],
    protocol: str | None = None,
    country: str | None = None,
    anonymity: str | None = None,
    max_latency: float | None = None,
) -> list[CheckResult]:
    """Filter check results based on criteria."""
    filtered: list[CheckResult] = []
    for r in results:
        if protocol and (not r.protocol or r.protocol.lower() != protocol.lower()):
            continue
        if country and (not r.country or r.country.lower() != country.lower()):
            continue
        if anonymity and (not r.anonymity or r.anonymity.lower() != anonymity.lower()):
            continue
        if max_latency is not None and (r.latency_ms is None or r.latency_ms > max_latency):
            continue
        filtered.append(r)
    return filtered


def export_results(results: list[CheckResult], output_path: Path | str) -> None:
    """Export all results to a JSON or CSV file based on file extension."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()

    if suffix == ".json":
        data = [asdict(r) for r in results]
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    elif suffix == ".csv":
        fieldnames = [
            "proxy",
            "is_alive",
            "protocol",
            "latency_ms",
            "exit_ip",
            "anonymity",
            "country",
            "asn",
            "target_status",
            "target_blocked",
            "error",
        ]
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                writer.writerow(asdict(r))
    else:
        lines = [
            f"{r.proxy} | {'ALIVE' if r.is_alive else 'DEAD'} | {r.protocol or '-'} | "
            f"{r.latency_ms or '-'}ms | {r.exit_ip or '-'} | {r.anonymity or '-'} | "
            f"{r.country or '-'} | {r.error or ''}"
            for r in results
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_working_proxies(results: list[CheckResult], output_path: Path | str) -> None:
    """Export only working proxies in a format directly loadable by web scrapers."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    working = [r for r in results if r.is_alive]
    lines: list[str] = []
    for r in working:
        proxy_str = r.proxy
        if "://" not in proxy_str and r.protocol:
            lines.append(f"{r.protocol}://{proxy_str}")
        else:
            lines.append(proxy_str)

    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
