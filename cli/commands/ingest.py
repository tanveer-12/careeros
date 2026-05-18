"""CLI commands for running CareerOS ingestion pipelines.

ingest-jobs — single-source scrape with explicit company slugs (backward-compatible)
ingest       — multi-source scrape across all ATS + feed sources

Usage:
    careeros ingest
    careeros ingest --sources greenhouse,lever --limit 200
    careeros ingest --dry-run
    careeros ingest-jobs --companies stripe,notion --source greenhouse --dry-run
"""

from __future__ import annotations

import asyncio
from collections import Counter
from typing import Annotated, Optional

from dotenv import load_dotenv
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from config.settings import settings
from core.collectors.ats_scrapers import ATS_REGISTRY
from core.normalization.job_normalizer import JobNormalizer, NormalizedJob
from core.workflows.pipeline import IngestionPipeline, IngestionResult

load_dotenv()
app = typer.Typer(invoke_without_command=True)
console = Console()

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _parse_slugs(companies: str) -> list[str]:
    return [s.strip().lower() for s in companies.split(",") if s.strip()]


def _build_scraper(source: str):
    if source not in ATS_REGISTRY:
        console.print(f"Unknown source: {source}")
        raise typer.Exit(1)
    return ATS_REGISTRY[source]()


async def _scrape_and_normalize(
    scraper, normalizer: JobNormalizer, slugs: list[str]
) -> tuple[list[NormalizedJob], int]:
    """Returns (normalized_jobs, raw_count). Runs scraper as async context manager."""
    async with scraper:
        raw_jobs = await scraper.scrape_companies(slugs)

    raw_count = len(raw_jobs)
    normalized: list[NormalizedJob] = []
    for raw in raw_jobs:
        try:
            normalized.append(normalizer.normalize(raw))
        except Exception:
            pass
    return normalized, raw_count


def _print_dry_run_table(jobs: list[NormalizedJob], raw_count: int) -> None:
    console.print(f"\n[bold]Dry run — {raw_count} jobs fetched, {len(jobs)} normalized[/bold]\n")

    preview = jobs[:5]
    table = Table(title=f"First {len(preview)} normalized jobs", show_lines=True)
    table.add_column("Title", style="cyan", no_wrap=False)
    table.add_column("Company", style="green")
    table.add_column("Location")
    table.add_column("Seniority")
    table.add_column("Domain")
    table.add_column("Skills (first 3)")

    for job in preview:
        table.add_row(
            job.title or "—",
            job.company or "—",
            job.location or "—",
            job.seniority or "—",
            job.domain or "—",
            ", ".join(job.skills[:3]) if job.skills else "—",
        )

    console.print(table)


def _print_result_table(result) -> None:
    table = Table(title="Ingestion Summary", show_header=False, box=None, padding=(0, 2))
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Companies scraped", str(result.companies))
    table.add_row("Jobs fetched", str(result.fetched))
    table.add_row("Jobs inserted", f"[green]{result.inserted}[/green]")
    table.add_row("Jobs skipped (duplicates)", str(result.skipped))
    table.add_row("Jobs failed", f"[red]{result.failed}[/red]" if result.failed else "0")

    console.print()
    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# ingest-jobs command (single-source, backward-compatible)
# ---------------------------------------------------------------------------

def ingest_jobs(
    companies: Annotated[str, typer.Option("--companies", help='Comma-separated company slugs')],
    source: Annotated[str, typer.Option("--source")] = "greenhouse",
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    """Scrape job postings and load them into the CareerOS database."""

    slugs = _parse_slugs(companies)
    if not slugs:
        console.print("[bold red]No valid company slugs provided.[/bold red]")
        raise typer.Exit(code=1)

    scraper = _build_scraper(source)
    normalizer = JobNormalizer()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(
            f"Scraping [bold]{source}[/bold] for {len(slugs)} company(s)…",
            total=None,
        )
        normalized, raw_count = asyncio.run(
            _scrape_and_normalize(scraper, normalizer, slugs)
        )

    if dry_run:
        _print_dry_run_table(normalized, raw_count)
        return

    from database.session import async_session  # deferred: avoids DB import when --dry-run

    pipeline = IngestionPipeline(scraper, normalizer, async_session)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Writing to database…", total=None)
        result = asyncio.run(pipeline.run(slugs))

    _print_result_table(result)


# ---------------------------------------------------------------------------
# ingest command — multi-source helpers
# ---------------------------------------------------------------------------

async def _run_dry_run_all(
    source_configs,
    normalizer: JobNormalizer,
) -> dict[str, tuple[int, list[NormalizedJob]]]:
    """Scrape + normalize each source without writing to DB. Returns (raw_count, jobs) per source."""
    results: dict[str, tuple[int, list[NormalizedJob]]] = {}
    for config in source_configs:
        slugs: list[str] = [] if config.is_feed else config.slugs
        async with config.scraper:
            raw_jobs = await config.scraper.scrape_companies(slugs)
        normalized = await normalizer.normalize_batch(raw_jobs)
        results[config.name] = (len(raw_jobs), normalized)
    return results


def _print_multi_source_table(results: dict[str, IngestionResult]) -> None:
    table = Table(title="Ingestion Results by Source", show_lines=True)
    table.add_column("Source", style="bold cyan")
    table.add_column("Scraped", justify="right")
    table.add_column("Inserted", style="green", justify="right")
    table.add_column("Skipped", justify="right")
    table.add_column("Stale", justify="right")
    table.add_column("Failed", justify="right")

    for name, result in results.items():
        table.add_row(
            name,
            str(result.fetched),
            str(result.inserted),
            str(result.skipped),
            str(result.stale_filtered),
            f"[red]{result.failed}[/red]" if result.failed else "0",
        )

    console.print()
    console.print(table)


def _print_dry_run_multi_table(
    dry_results: dict[str, tuple[int, list[NormalizedJob]]],
) -> None:
    console.print("\n[bold]Dry run — no data written to database[/bold]")
    table = Table(title="Scrape + Normalize Preview", show_lines=True)
    table.add_column("Source", style="bold cyan")
    table.add_column("Scraped", justify="right")
    table.add_column("Normalized", justify="right")

    for name, (raw_count, jobs) in dry_results.items():
        table.add_row(name, str(raw_count), str(len(jobs)))

    console.print()
    console.print(table)


def _print_domain_table(counts: Counter) -> None:
    if not counts:
        return
    total = sum(counts.values())
    table = Table(title="Domain Breakdown", show_lines=True)
    table.add_column("Domain", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Share", justify="right")
    for domain, count in counts.most_common(10):
        table.add_row(domain, str(count), f"{count / total:.1%}")
    console.print()
    console.print(table)


# ---------------------------------------------------------------------------
# ingest command — multi-source entry point
# ---------------------------------------------------------------------------

def ingest_all(
    sources: Annotated[Optional[str], typer.Option(
        "--sources", help="Comma-separated feed source names to run (default: all)"
    )] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Scrape and normalize without writing to DB")] = False,
) -> None:
    """Scrape all feed sources (Simplify, YC, Jobright, HiringCafe) and load jobs into the database."""
    from core.collectors.feed_scrapers import FEED_REGISTRY
    from core.workflows.pipeline import MultiSourcePipeline, SourceConfig

    all_feeds = list(FEED_REGISTRY.keys())

    if sources:
        requested = [s.strip().lower() for s in sources.split(",") if s.strip()]
        unknown = [s for s in requested if s not in all_feeds]
        if unknown:
            console.print(f"[bold red]Unknown sources: {', '.join(unknown)}[/bold red]")
            console.print(f"Available: {', '.join(all_feeds)}")
            raise typer.Exit(1)
        feed_names = requested
    else:
        feed_names = all_feeds

    source_configs = [
        SourceConfig(name=feed, scraper=FEED_REGISTRY[feed](), is_feed=True)
        for feed in feed_names
    ]

    normalizer = JobNormalizer()

    if dry_run:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("Scraping and normalizing (dry run)…", total=None)
            dry_results = asyncio.run(_run_dry_run_all(source_configs, normalizer))

        _print_dry_run_multi_table(dry_results)
        all_jobs = [job for _, jobs in dry_results.values() for job in jobs]
        _print_domain_table(Counter(job.domain or "unknown" for job in all_jobs))
        return

    from database.session import async_session  # deferred: avoids DB import when --dry-run

    pipeline = MultiSourcePipeline(source_configs, normalizer, async_session)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Running all sources…", total=None)
        results = asyncio.run(pipeline.run())

    _print_multi_source_table(results)

    combined_counts: Counter = Counter()
    for result in results.values():
        combined_counts.update(result.domain_counts)
    _print_domain_table(combined_counts)
