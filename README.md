# proxy-check

[![CI](https://github.com/Lunar-Dev17/Proxy-Checker/actions/workflows/tests.yml/badge.svg)](https://github.com/Lunar-Dev17/Proxy-Checker/actions/workflows/tests.yml)

An asynchronous CLI tool for testing, benchmarking, and filtering proxy lists for web scraping.

---

## Features

- **Asynchronous Concurrency**: Built with `asyncio` and `httpx` to test proxy lists concurrently with a configurable concurrency limit (`--concurrency`).
- **Multi-Protocol Support**: Probes HTTP, HTTPS, SOCKS4, and SOCKS5 proxies. Automatically detects protocol if not specified.
- **Anonymity Level Detection**: Analyzes proxy judge response headers to classify proxies into `elite`, `anonymous`, or `transparent`.
- **Geolocation and ASN Lookup**: Resolves exit IP country and ASN via `ip-api` or `ipinfo`, caching responses locally to minimize redundant queries.
- **Target Site Verification**: Tests proxies against a specific target website URL (`--target`) and flags blocked responses (HTTP 403, 429, or bot challenges such as Cloudflare Turnstile, reCAPTCHA, and DataDome).
- **Summary Table and Live Progress**: Displays real-time progress with alive/dead counters, followed by a latency-sorted table in the terminal.
- **Filtering and Exporting**: Filters results by protocol, country, anonymity level, or latency limit. Exports structured data to `.json` or `.csv`, and exports working proxies in scraper-ready format (`--output-working`).
- **Graceful Cancellation**: Aborting with `Ctrl+C` prints tested results and writes partial exports to requested files before exiting.

---

## Installation

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

## Supported Proxy Formats

`proxy-check` accepts a plain text file containing one proxy per line. Empty lines and lines starting with `#` are ignored.

```text
# Host and port (auto-detects HTTP, SOCKS5, SOCKS4)
192.168.1.1:8080

# Authentication
admin:secret@192.168.1.1:8080
192.168.1.1:8080:admin:secret

# Explicit scheme
http://192.168.1.1:8080
https://192.168.1.1:8443
socks4://192.168.1.1:1080
socks5://admin:secret@192.168.1.1:1080

# IPv6 addresses (bracketed notation)
[2001:db8::1]:8080
user:pass@[::1]:8080
```

If lines lack a port number (for example, raw IP lists), provide a default port using `--default-port 8080`. When running interactively in a terminal without the flag, the tool prompts for one.

---

## Quickstart & Usage

### 1. Basic Check
Test a list of proxies using default settings (concurrency: 50, timeout: 10s):
```bash
proxy-check check proxies.txt
```

### 2. Check Against a Target Site
Test proxies against a target URL to check for blocks or bot challenges:
```bash
proxy-check check proxies.txt --concurrency 50 --timeout 5.0 --target https://example.com
```

### 3. Filter and Export
Filter only elite proxies in the US under 300ms latency, and save results:
```bash
proxy-check check proxies.txt \
  --country US \
  --anonymity elite \
  --max-latency 300 \
  --output results.json \
  --output-working working_proxies.txt
```

---

## Sample Terminal Output

Example run output captured from a CLI run against a sample proxy list:

```text
proxy-check loaded 6 proxies (concurrency: 50, timeout: 2.0s)...

  Testing proxies ---------------------------------------- 6/6 Alive: 0  Dead: 6 0:00:13

                                   Proxy Check Results (Sorted by Latency)                                   
┌────────┬──────────────────────┬───────┬────────────┬─────────┬───────────┬───────────────┬────────────────┐
│ Status │ Proxy                │ Proto │    Latency │ Exit IP │ Anonymity │ Country / ASN │ Details        │
├────────┼──────────────────────┼───────┼────────────┼─────────┼───────────┼───────────────┼────────────────┤
│  DEAD  │ 62.210.215.36:8080   │   -   │  2008.5 ms │ -       │     -     │ -             │ Timeout (2.0s) │
│  DEAD  │ 109.252.226.30:8080  │   -   │  3921.4 ms │ -       │     -     │ -             │ Timeout (2.0s) │
│  DEAD  │ 171.247.245.218:8080 │   -   │  5780.7 ms │ -       │     -     │ -             │ Timeout (2.0s) │
│  DEAD  │ 203.205.49.2:8080    │   -   │  7601.0 ms │ -       │     -     │ -             │ Timeout (2.0s) │
│  DEAD  │ 190.97.254.254:8080  │   -   │  9569.8 ms │ -       │     -     │ -             │ Timeout (2.0s) │
│  DEAD  │ 122.52.202.231:8080  │   -   │ 11744.0 ms │ -       │     -     │ -             │ Timeout (2.0s) │
└────────┴──────────────────────┴───────┴────────────┴─────────┴───────────┴───────────────┴────────────────┘
=================================================================
Summary: Tested: 6/6 | Alive: 0 | Dead: 6
```

---

## CLI Flags and Options

| Flag | Short | Default | Description |
|---|---|---|---|
| `file` | - | *Required* | Path to text file containing one proxy per line. |
| `--concurrency` | `-c` | `50` | Maximum number of concurrent proxy checks. |
| `--timeout` | `-t` | `10.0` | Timeout in seconds for each network request. |
| `--target-url` | - | `https://httpbin.org/ip` | Endpoint used to verify proxy connectivity and obtain exit IP. |
| `--judge-url` | - | `https://httpbin.org/headers` | Header-echo endpoint used for anonymity detection. |
| `--geo-provider` | - | `ip-api` | Geolocation provider (`ip-api`, `ipinfo`, or a custom URL template). |
| `--target` | - | `None` | Target website URL to test whether the proxy is blocked. |
| `--protocol` | - | `None` | Filter results by protocol (`http`, `socks5`, `socks4`). |
| `--country` | - | `None` | Filter results by two-letter country code (e.g. `US`, `DE`). |
| `--anonymity` | - | `None` | Filter results by anonymity level (`elite`, `anonymous`, `transparent`). |
| `--max-latency` | - | `None` | Filter results by maximum latency in milliseconds. |
| `--output` | `-o` | `None` | Export full results to a file (`.json` or `.csv`). |
| `--output-working` | `-w` | `None` | Export working proxies in scraper-ready format (`.txt`). |
| `--default-port` | `-p` | `None` | Default port for lines containing only raw IP addresses. |
| `--version` | `-v` | - | Show application version and exit. |
| `--help` | - | - | Show CLI usage documentation and exit. |

---

## Limitations

- **Public Endpoint Rate Limiting**: The default endpoints (`httpbin.org` and `ip-api.com`) enforce rate limits on unauthenticated traffic. When testing large proxy lists, supply dedicated or self-hosted endpoints with `--target-url`, `--judge-url`, or `--geo-provider`.
- **Static Bot Challenge Detection**: Target verification inspects HTTP status codes and response HTML for known challenge patterns (Cloudflare Turnstile, reCAPTCHA, hCaptcha, DataDome, PerimeterX). It does not execute JavaScript or bypass active challenges.
- **Protocol Constraints**: SOCKS4 proxies do not support authentication or IPv6 destinations.
- **Operating System Socket Limits**: High concurrency settings (`-c 200+`) depend on available system file descriptors (`ulimit -n` on Unix systems) and socket buffer limits.

---

## Development and Testing

Run tests and linting locally:

```bash
# Run test suite
pytest -v

# Run lint and format checks
ruff check .
ruff format --check .
```

---

## Contributing

Please see [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines and development workflow.

---

## License

This project is licensed under the [MIT License](LICENSE).
