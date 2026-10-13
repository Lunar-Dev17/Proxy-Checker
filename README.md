# proxy-check ⚡

[![CI](https://github.com/Lunar-Dev17/Proxy-Checker/actions/workflows/tests.yml/badge.svg)](https://github.com/Lunar-Dev17/Proxy-Checker/actions/workflows/tests.yml)
[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

A lightning-fast, asynchronous CLI tool built for web scrapers to test, benchmark, and filter proxy lists at scale.

---

## ✨ Features

- **⚡ Blazing Fast Concurrency**: Built on `asyncio` and `httpx` to benchmark hundreds of proxies simultaneously with strict concurrency control.
- **🔌 Multi-Protocol Support**: Tests HTTP, HTTPS, SOCKS4, and SOCKS5 proxies. Automatically detects protocol if not explicitly specified.
- **🕵️ Anonymity Classification**: Inspects header-echo responses to classify proxies as **elite** (high anonymity / no trace), **anonymous** (proxy revealed, real IP hidden), or **transparent** (real client IP leaked).
- **🌍 Geo & ASN Intelligence**: Resolves exit IP geographic country and autonomous system numbers (ASN) with an in-memory cache and graceful rate limit handling.
- **🎯 Target Site Verification**: Verifies if proxies work against specific target domains (e.g. `--target https://example.com`) and flags blocked requests (HTTP 403, 429, or Cloudflare/DataDome/reCAPTCHA bot challenge pages).
- **📊 Rich Terminal UX**: Live animated progress bar with instantaneous success/failure counters, followed by a latency-sorted final summary table.
- **💾 Export & Filter**: Export all results to `.json` or `.csv`, or export working proxies directly to a scraper-ready text file (`--output-working working.txt`). Filter proxies by protocol, country, anonymity, or maximum latency.
- **🛡️ Graceful Interruption**: Pressing `Ctrl+C` cleanly aborts the run, displays tested results, and saves partial output files without losing data.

---

## 📦 Installation

### From PyPI (Standard)
```bash
pip install proxy-check
```

### From Source (Development)
```bash
git clone https://github.com/Lunar-Dev17/Proxy-Checker.git
cd Proxy-Checker

python -m venv .venv
# On Linux / macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

pip install -e ".[dev]"
```

---

## 📋 Supported Proxy Formats

`proxy-check` accepts a plain text file containing one proxy per line. Empty lines and comments starting with `#` are automatically ignored.

```text
# IP:Port (auto-probes and detects HTTP, SOCKS5, SOCKS4)
192.168.1.1:8080

# With authentication
admin:secret@192.168.1.1:8080
192.168.1.1:8080:admin:secret

# Explicit scheme
http://192.168.1.1:8080
https://192.168.1.1:8443
socks4://192.168.1.1:1080
socks5://admin:secret@192.168.1.1:1080
```

---

## 🚀 Quickstart & Usage

### 1. Basic Check
Test proxies using default settings (50 concurrent connections, 10s timeout):
```bash
proxy-check check proxies.txt
```

### 2. High-Concurrency Checking with Target Verification
Test 200 proxies concurrently against a target website:
```bash
proxy-check check proxies.txt --concurrency 200 --timeout 5.0 --target https://example.com
```

### 3. Filter & Export Scraper-Ready Proxies
Filter only elite proxies in the United States with latency under 300ms and export them:
```bash
proxy-check check proxies.txt \
  --country US \
  --anonymity elite \
  --max-latency 300 \
  --output results.json \
  --output-working working_proxies.txt
```

---

## 🖥️ Sample Terminal Output

```text
proxy-check loaded 100 proxies (concurrency: 50, timeout: 10.0s)...

  Testing proxies ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100/100 ✓ 82  ✗ 18 0:00:04

                          Proxy Check Results (Sorted by Latency)
┌────────┬────────────────────────────┬────────┬──────────┬──────────────┬───────────┬───────────────┬───────────────┬─────────┐
│ Status │ Proxy                      │ Proto  │  Latency │ Exit IP      │ Anonymity │ Country / ASN │ Target Status │ Details │
├────────┼────────────────────────────┼────────┼──────────┼──────────────┼───────────┼───────────────┼───────────────┼─────────┤
│ ALIVE  │ socks5://198.51.100.1:1080 │ socks5 │  45.2 ms │ 198.51.100.1 │   elite   │ US / AS15169  │ Passed (200)  │ OK      │
│ ALIVE  │ 203.0.113.50:8080          │  http  │  82.1 ms │ 203.0.113.50 │   anon    │ DE / AS24940  │ Passed (200)  │ OK      │
│ ALIVE  │ 192.0.2.14:3128            │  http  │ 125.4 ms │ 192.0.2.14   │  transp   │ CA / AS812    │ Blocked (403) │ OK      │
│  DEAD  │ 198.51.100.99:80           │   -    │        - │ -            │     -     │ -             │ -             │ Timeout │
└────────┴────────────────────────────┴────────┴──────────┴──────────────┴───────────┴───────────────┴───────────────┴─────────┘
=================================================================
Summary: Tested: 100/100 | Alive: 82 | Dead: 18 | Target: Passed: 79, Blocked: 3

✓ Exported 82 results to: results.json
✓ Exported 82 working proxies to: working_proxies.txt
```

---

## 📖 CLI Flags & Options

| Flag | Short | Default | Description |
|---|---|---|---|
| `file` | - | *Required* | Path to text file containing one proxy per line. |
| `--concurrency` | `-c` | `50` | Maximum number of concurrent async checks. |
| `--timeout` | `-t` | `10.0` | Timeout in seconds for each network test. |
| `--target` | - | `None` | Target website URL to test for blocks (403, 429, or captcha). |
| `--target-url` | - | `https://httpbin.org/ip` | Echo endpoint used to verify proxy alive status & exit IP. |
| `--judge-url` | - | `https://httpbin.org/headers` | Header-echo endpoint used for anonymity detection. |
| `--geo-provider` | - | `ip-api` | Country & ASN lookup provider (`ip-api`, `ipinfo`, or template URL). |
| `--protocol` | - | `None` | Filter results by protocol (`http`, `socks5`, `socks4`). |
| `--country` | - | `None` | Filter results by 2-letter country code (e.g. `US`, `DE`). |
| `--anonymity` | - | `None` | Filter results by anonymity level (`elite`, `anonymous`, `transparent`). |
| `--max-latency` | - | `None` | Filter results by maximum latency in milliseconds (e.g. `500`). |
| `--output` | `-o` | `None` | Export full results to a file based on extension (`.json` or `.csv`). |
| `--output-working` | `-w` | `None` | Export only working proxies directly to scraper format (`.txt`). |
| `--default-port` | `-p` | `None` | Default port for lines containing only raw IPs. Interactively prompted if omitted in a terminal. |
| `--version` | `-v` | - | Show the application version and exit. |
| `--help` | - | - | Show CLI usage documentation and exit. |

---

## 🗺️ Roadmap

- [ ] **DNS Leak Testing**: Test whether DNS queries leak the origin resolver when proxying.
- [ ] **Proxy Chain / Hop Detection**: Detect proxy chaining and analyze multi-hop response headers.
- [ ] **Interactive TUI Mode**: Full-screen interactive terminal dashboard with sorting, search, and live re-testing.
- [ ] **Automated Re-check Daemon**: Background daemon mode to continuously monitor proxy list health.
- [ ] **Custom HTTP Header / Cookie Injection**: Allow passing custom headers and session cookies when testing target endpoints.

---

## 🧪 Development & Testing

Run tests and linting locally:

```bash
# Run test suite
pytest -v

# Run lint and format checks
ruff check .
ruff format --check .
```

---

## 🤝 Contributing

Contributions are welcome! Please check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on branch naming, code standards, and PR submissions.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
