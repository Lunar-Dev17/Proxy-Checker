"""CLI interface for proxy-check."""

import asyncio
import sys
from pathlib import Path

import typer
from rich.console import Console

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from proxy_check import (
    MissingPortError,
    ProxyChecker,
    __version__,
    export_results,
    export_working_proxies,
    extract_port_from_input,
    filter_results,
    parse_proxy_file,
)
from proxy_check.anonymity import DEFAULT_JUDGE_URL
from proxy_check.checker import DEFAULT_CONCURRENCY, DEFAULT_TARGET_URL, DEFAULT_TIMEOUT
from proxy_check.models import CheckResult

app = typer.Typer(
    name="proxy-check",
    help="A fast async CLI tool that tests proxy lists for web scraping.",
    add_completion=False,
)
console = Console(width=120 if not Console().is_terminal else None)


def is_interactive() -> bool:
    """Check if standard input is attached to an interactive terminal."""
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except Exception:
        return False


def prompt_for_default_port(default: int = 8080) -> int:
    """Interactively prompt for a port number, automatically handling host:port strings and prefixes."""
    while True:
        raw_val = typer.prompt(
            "Enter default port for proxies without one",
            default=str(default),
        )
        try:
            port = extract_port_from_input(raw_val, default=default)
            if str(raw_val).strip() != str(port):
                console.print(
                    f"[cyan]Detected port [bold green]{port}[/bold green] from '{raw_val.strip()}'.[/cyan]"
                )
            return port
        except ValueError as err:
            console.print(
                f"[bold red]Invalid port:[/bold red] {err}. Please enter a port between 1 and 65535."
            )


def version_callback(value: bool) -> None:
    """Print version and exit when --version or -v is passed."""
    if value:
        console.print(f"[bold cyan]proxy-check[/bold cyan] version [green]{__version__}[/green]")
        raise typer.Exit()


def render_summary_table(
    results: list[CheckResult],
    has_target: bool = False,
) -> None:
    """Render a sorted summary table using Rich."""
    if not results:
        console.print("[yellow]No results to display.[/yellow]")
        return

    # Sort results by latency: alive proxies with lowest latency first, then dead proxies
    sorted_results = sorted(
        results,
        key=lambda r: (
            not r.is_alive,
            r.latency_ms if r.latency_ms is not None else float("inf"),
        ),
    )

    table = Table(
        title="Proxy Check Results (Sorted by Latency)",
        title_style="bold cyan",
        show_header=True,
        header_style="bold white",
    )

    table.add_column("Status", justify="center")
    table.add_column("Proxy", no_wrap=True)
    table.add_column("Proto", justify="center")
    table.add_column("Latency", justify="right")
    table.add_column("Exit IP", no_wrap=True)
    table.add_column("Anonymity", justify="center")
    table.add_column("Country / ASN")
    if has_target:
        table.add_column("Target Status")
    table.add_column("Details")

    for r in sorted_results:
        if r.is_alive:
            status_cell = "[bold green]ALIVE[/bold green]"
            proto_cell = f"[cyan]{r.protocol}[/cyan]" if r.protocol else "-"
            lat_cell = f"[green]{r.latency_ms:.1f} ms[/green]" if r.latency_ms is not None else "-"
            exit_ip_cell = f"[white]{r.exit_ip}[/white]" if r.exit_ip else "-"

            if r.anonymity == "elite":
                anon_cell = "[bold magenta]elite[/bold magenta]"
            elif r.anonymity == "anonymous":
                anon_cell = "[yellow]anon[/yellow]"
            elif r.anonymity == "transparent":
                anon_cell = "[red]transp[/red]"
            else:
                anon_cell = "[dim]-[/dim]"

            geo_parts = [p for p in (r.country, r.asn) if p]
            geo_cell = f"[blue]{' / '.join(geo_parts)}[/blue]" if geo_parts else "[dim]-[/dim]"

            if has_target:
                if r.target_blocked:
                    target_cell = f"[bold red]{r.target_status}[/bold red]"
                else:
                    target_cell = f"[bold green]{r.target_status}[/bold green]"
            details_cell = "[dim]OK[/dim]"
        else:
            status_cell = "[bold red]DEAD[/bold red]"
            proto_cell = f"[dim]{r.protocol or '-'}[/dim]"
            lat_cell = (
                f"[dim]{r.latency_ms:.1f} ms[/dim]" if r.latency_ms is not None else "[dim]-[/dim]"
            )
            exit_ip_cell = "[dim]-[/dim]"
            anon_cell = "[dim]-[/dim]"
            geo_cell = "[dim]-[/dim]"
            if has_target:
                target_cell = "[dim]-[/dim]"
            details_cell = f"[red]{r.error or 'Failed'}[/red]"

        row = [
            status_cell,
            r.proxy,
            proto_cell,
            lat_cell,
            exit_ip_cell,
            anon_cell,
            geo_cell,
        ]
        if has_target:
            row.append(target_cell)
        row.append(details_cell)
        table.add_row(*row)

    console.print("\n", table)


def handle_exports(
    results: list[CheckResult],
    output: Path | None,
    output_working: Path | None,
) -> None:
    """Save results and working proxies to requested files."""
    if output:
        try:
            export_results(results, output)
            console.print(
                f"[green]Exported {len(results)} results to:[/green] [bold]{output}[/bold]"
            )
        except Exception as exc:
            console.print(f"[bold red]Failed to export results to {output}:[/bold red] {exc}")

    if output_working:
        try:
            working_count = sum(1 for r in results if r.is_alive)
            export_working_proxies(results, output_working)
            console.print(
                f"[green]Exported {working_count} working proxies to:[/green] [bold]{output_working}[/bold]"
            )
        except Exception as exc:
            console.print(
                f"[bold red]Failed to export working proxies to {output_working}:[/bold red] {exc}"
            )


async def run_checks(
    file_path: Path,
    concurrency: int,
    timeout: float,
    target_url: str,
    judge_url: str | None,
    geo_provider: str | None,
    target: str | None,
    protocol_filter: str | None,
    country_filter: str | None,
    anonymity_filter: str | None,
    max_latency_filter: float | None,
    output: Path | None,
    output_working: Path | None,
    default_port: int | None = None,
) -> None:
    """Run concurrent proxy checks with live progress, filtering, and export handling."""
    try:
        proxies = parse_proxy_file(file_path, default_port=default_port)
    except MissingPortError as exc:
        if is_interactive():
            console.print(f"[yellow]Notice:[/yellow] {exc}")
            try:
                entered_port = prompt_for_default_port(default=8080)
                proxies = parse_proxy_file(file_path, default_port=entered_port)
            except (typer.Abort, KeyboardInterrupt):
                console.print("\n[bold yellow]Aborted by user.[/bold yellow]")
                raise typer.Exit(code=130) from None
        else:
            console.print(f"[bold red]Error reading proxies:[/bold red] {exc}")
            raise typer.Exit(code=1) from exc
    except Exception as exc:
        console.print(f"[bold red]Error reading proxies:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    if not proxies:
        console.print("[yellow]No proxies found in file.[/yellow]")
        return

    console.print(
        f"[bold cyan]proxy-check[/bold cyan] loaded [bold green]{len(proxies)}[/bold green] "
        f"proxies (concurrency: [bold]{concurrency}[/bold], timeout: [bold]{timeout}s[/bold])...\n"
    )

    checker = ProxyChecker(
        target_url=target_url,
        timeout=timeout,
        concurrency=concurrency,
        judge_url=judge_url,
        geo_provider=geo_provider,
        target=target,
    )

    results: list[CheckResult] = []
    alive_count = 0
    dead_count = 0
    interrupted = False

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}[/bold cyan]"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn(
            "[green]Alive: {task.fields[alive]}[/green]  [red]Dead: {task.fields[dead]}[/red]"
        ),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        task_id = progress.add_task(
            "Testing proxies",
            total=len(proxies),
            alive=0,
            dead=0,
        )

        try:
            async for result in checker.check_proxies_stream(proxies):
                results.append(result)
                if result.is_alive:
                    alive_count += 1
                else:
                    dead_count += 1

                progress.update(
                    task_id,
                    advance=1,
                    alive=alive_count,
                    dead=dead_count,
                )
        except (KeyboardInterrupt, asyncio.CancelledError):
            interrupted = True
            console.print(
                "\n[bold yellow]Check interrupted by user (Ctrl+C). Saving partial results...[/bold yellow]"
            )

    # Apply filters if specified
    filtered_results = filter_results(
        results,
        protocol=protocol_filter,
        country=country_filter,
        anonymity=anonymity_filter,
        max_latency=max_latency_filter,
    )

    # Render final summary table sorted by latency
    render_summary_table(filtered_results, has_target=bool(target))

    # Print summary statistics
    console.print("=" * 65)
    summary_text = (
        f"[bold]Summary:[/bold] Tested: {len(results)}/{len(proxies)} | "
        f"[bold green]Alive: {alive_count}[/bold green] | "
        f"[bold red]Dead: {dead_count}[/bold red]"
    )
    if protocol_filter or country_filter or anonymity_filter or max_latency_filter is not None:
        summary_text += f" | [bold cyan]Matching Filters: {len(filtered_results)}[/bold cyan]"

    if target:
        t_passed = sum(1 for r in filtered_results if r.is_alive and not r.target_blocked)
        t_blocked = sum(1 for r in filtered_results if r.is_alive and r.target_blocked)
        summary_text += (
            f" | Target: [bold green]Passed: {t_passed}[/bold green], "
            f"[bold red]Blocked: {t_blocked}[/bold red]"
        )
    console.print(summary_text + "\n")

    # Handle file exports (saves filtered results or all results if no filter)
    handle_exports(filtered_results, output=output, output_working=output_working)

    if interrupted:
        raise typer.Exit(code=130)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show the application version and exit.",
    ),
) -> None:
    """proxy-check CLI entrypoint."""
    if ctx.invoked_subcommand is None and not version:
        console.print(ctx.get_help())


@app.command("check")
def check_command(
    file: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to text file containing one proxy per line.",
    ),
    concurrency: int = typer.Option(
        DEFAULT_CONCURRENCY,
        "--concurrency",
        "-c",
        help="Maximum concurrent checks.",
    ),
    timeout: float = typer.Option(
        DEFAULT_TIMEOUT,
        "--timeout",
        "-t",
        help="Timeout in seconds for each proxy test.",
    ),
    target_url: str = typer.Option(
        DEFAULT_TARGET_URL,
        "--target-url",
        help="Echo endpoint used to verify proxies and fetch exit IP.",
    ),
    judge_url: str | None = typer.Option(
        DEFAULT_JUDGE_URL,
        "--judge-url",
        help="Header-echo judge endpoint URL for anonymity level detection.",
    ),
    geo_provider: str | None = typer.Option(
        "ip-api",
        "--geo-provider",
        help="Country & ASN lookup provider ('ip-api', 'ipinfo', or custom URL template).",
    ),
    target: str | None = typer.Option(
        None,
        "--target",
        help="Specific target website URL to test whether the proxy is blocked (403, 429, captcha).",
    ),
    protocol: str | None = typer.Option(
        None,
        "--protocol",
        help="Filter results by protocol (e.g. 'http', 'socks5').",
    ),
    country: str | None = typer.Option(
        None,
        "--country",
        help="Filter results by 2-letter country code (e.g. 'US', 'DE').",
    ),
    anonymity: str | None = typer.Option(
        None,
        "--anonymity",
        help="Filter results by anonymity level ('elite', 'anonymous', 'transparent').",
    ),
    max_latency: float | None = typer.Option(
        None,
        "--max-latency",
        help="Filter results by maximum latency in milliseconds.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Export all results to a file (.json or .csv).",
    ),
    output_working: Path | None = typer.Option(
        None,
        "--output-working",
        "-w",
        help="Export only working proxies in a format scrapers can load directly (.txt).",
    ),
    default_port: int | None = typer.Option(
        None,
        "--default-port",
        "-p",
        help="Default port to use for lines containing only an IP address without a port.",
    ),
) -> None:
    """Test a list of proxies from a text file with live progress, filtering, and export."""
    try:
        asyncio.run(
            run_checks(
                file_path=file,
                concurrency=concurrency,
                timeout=timeout,
                target_url=target_url,
                judge_url=judge_url,
                geo_provider=geo_provider,
                target=target,
                protocol_filter=protocol,
                country_filter=country,
                anonymity_filter=anonymity,
                max_latency_filter=max_latency,
                output=output,
                output_working=output_working,
                default_port=default_port,
            )
        )
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Aborted by user.[/bold yellow]")
        raise typer.Exit(code=130) from None


@app.command("version")
def version_command() -> None:
    """Print the version of proxy-check."""
    console.print(f"[bold cyan]proxy-check[/bold cyan] version [green]{__version__}[/green]")


if __name__ == "__main__":
    app()
