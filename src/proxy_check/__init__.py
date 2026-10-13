"""proxy-check: A fast async CLI tool that tests proxy lists for web scraping."""

from proxy_check.anonymity import check_anonymity, classify_anonymity
from proxy_check.checker import ProxyChecker
from proxy_check.exporter import (
    export_results,
    export_working_proxies,
    filter_results,
)
from proxy_check.geo import GeoInfo, GeoLookup
from proxy_check.models import CheckResult, Proxy
from proxy_check.parser import (
    MissingPortError,
    extract_port_from_input,
    parse_proxies,
    parse_proxy,
    parse_proxy_file,
)
from proxy_check.target import check_target_site

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "MissingPortError",
    "extract_port_from_input",
    "Proxy",
    "CheckResult",
    "ProxyChecker",
    "GeoInfo",
    "GeoLookup",
    "check_anonymity",
    "classify_anonymity",
    "check_target_site",
    "export_results",
    "export_working_proxies",
    "filter_results",
    "parse_proxy",
    "parse_proxies",
    "parse_proxy_file",
]
