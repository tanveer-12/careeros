"""CLI commands for running Lumia ingestion pipelines.

ingest        — scrape Remotive and load jobs into the database
ingest-jobs   — (legacy) placeholder, use `lumia ingest` instead
ingest-resume — parse a DOCX resume and store it

Usage:
    lumia ingest
    lumia ingest --dry-run
"""

from __future__ import annotations

import asyncio
from collections import Counter
from typing import Annotated

from dotenv import load_dotenv
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

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
    table.add_row("Jobs inserted (new)", f"[green]{result.inserted}[/green]")
    table.add_row("Jobs updated (refreshed)", f"[cyan]{result.updated}[/cyan]")
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
# ingest-resume command
# ---------------------------------------------------------------------------

def ingest_resume(
    file: Annotated[str, typer.Argument(help="Path to DOCX resume file")],
    user_id: Annotated[str, typer.Option("--user-id", help="User identifier")] = "default",
    top_n: Annotated[int, typer.Option("--top-n", help="Number of archetypes to match")] = 10,
) -> None:
    """Parse a DOCX resume, embed it, and match against role archetypes."""
    import uuid
    from pathlib import Path
    from sqlalchemy import select

    path = Path(file)
    if not path.exists():
        console.print(f"[bold red]File not found: {file}[/bold red]")
        raise typer.Exit(1)
    if path.suffix.lower() != ".docx":
        console.print("[bold red]Only DOCX files are supported.[/bold red]")
        raise typer.Exit(1)

    # Step 1: Parse (sync — no DB, no event loop)
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console, transient=True) as p:
        p.add_task("Parsing resume…", total=None)
        from core.resume_parser import parse_resume
        parsed = parse_resume(path)

    # Steps 2-5: all async work in a single event loop
    from database.session import async_session
    from database.models.user_resumes import UserResume
    from core.embeddings.resume_embedder import ResumeEmbedder
    from core.archetypes.matcher import match_resume as _match
    from core.archetypes.ranker import save_rankings

    async def _run_pipeline() -> tuple[str, bool, list]:
        resolved = str(path.resolve())

        # Store
        async with async_session() as session:
            existing = await session.scalar(
                select(UserResume).where(UserResume.file_path == resolved)
            )
            if existing:
                resume_id, already_existed = existing.id, True
            else:
                resume = UserResume(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    file_name=path.name,
                    file_path=resolved,
                    raw_text=parsed.raw_text,
                    parsed_skills=parsed.skills,
                    parsed_titles=[parsed.current_or_last_role] if parsed.current_or_last_role else [],
                    parsed_years_exp=int(parsed.experience_years) if parsed.experience_years else None,
                    is_embedded=False,
                )
                session.add(resume)
                await session.commit()
                resume_id, already_existed = resume.id, False

        # Embed
        ok = await ResumeEmbedder().embed_resume(resume_id)
        if not ok:
            raise RuntimeError("Embedding failed — check logs for details.")

        # Match
        matches = await _match(resume_id, top_n=top_n)

        # Save rankings
        if matches:
            await save_rankings(resume_id, matches)

        return resume_id, already_existed, matches

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console, transient=True) as p:
        p.add_task("Processing resume…", total=None)
        try:
            resume_id, already_existed, matches = asyncio.run(_run_pipeline())
        except RuntimeError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1)

    if already_existed:
        console.print("\n[yellow]Resume already ingested — re-running matching on existing record[/yellow]")

    if not matches:
        console.print("\n[yellow]No archetype centroids found — run 'lumia build-archetypes' first.[/yellow]\n")
        console.print(f"resume_id: [cyan]{resume_id}[/cyan]")
        raise typer.Exit(0)

    # Print summary
    console.print(f"\n[bold green]Resume processed[/bold green]  [cyan]{resume_id}[/cyan]")
    if parsed.current_or_last_role:
        console.print(f"Detected role:  [yellow]{parsed.current_or_last_role}[/yellow]")
    if parsed.skills:
        console.print(f"Detected skills: [yellow]{', '.join(parsed.skills[:8])}{'…' if len(parsed.skills) > 8 else ''}[/yellow]")
    if parsed.experience_years:
        console.print(f"Experience est: [yellow]~{parsed.experience_years:.0f} years[/yellow]")
    console.print()

    table = Table(title=f"Top {len(matches)} Archetype Matches", show_lines=True)
    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("Archetype", style="cyan", no_wrap=False)
    table.add_column("Category", style="green")
    table.add_column("Similarity", justify="right", width=10)
    table.add_column("Fit", justify="center", width=9)
    table.add_column("Skill Gaps (top 4)")

    for i, m in enumerate(matches, start=1):
        sim = m.similarity
        if sim >= 0.75:
            fit_color, fit_label = "green", "Strong"
        elif sim >= 0.50:
            fit_color, fit_label = "yellow", "Adjacent"
        else:
            fit_color, fit_label = "red", "Weak"
        gaps = m.skill_gaps[:4]
        gaps_str = ", ".join(gaps) + ("…" if len(m.skill_gaps) > 4 else "") if gaps else "—"
        table.add_row(
            str(i),
            m.title,
            m.category,
            f"[{fit_color}]{sim:.3f}[/{fit_color}]",
            f"[{fit_color}]{fit_label}[/{fit_color}]",
            gaps_str,
        )

    console.print(table)
    console.print()


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
# ingest command — Himalayas entry point
# ---------------------------------------------------------------------------

def ingest_all(
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Scrape and normalize without writing to DB")] = False,
    companies: Annotated[str, typer.Option("--companies", help="Comma-separated company names to filter (default: all)")] = "",
) -> None:
    """Scrape Himalayas and load fresh remote jobs into the database."""
    from core.collectors.api_scrapers.himalayas import HimalayasScraper

    slugs = _parse_slugs(companies) if companies else []
    scraper = HimalayasScraper()
    normalizer = JobNormalizer()

    if dry_run:
        async def _dry():
            async with scraper:
                raw_jobs = await scraper.scrape_companies(slugs)
            normalized = await normalizer.normalize_batch(raw_jobs)
            return raw_jobs, normalized

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("Scraping Himalayas (dry run)…", total=None)
            raw_jobs, normalized = asyncio.run(_dry())

        _print_dry_run_table(normalized, len(raw_jobs))
        _print_domain_table(Counter(job.domain or "unknown" for job in normalized))
        return

    from database.session import async_session

    pipeline = IngestionPipeline(scraper, normalizer, async_session)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Scraping Himalayas…", total=None)
        result = asyncio.run(pipeline.run(slugs))

    _print_result_table(result)
    _print_domain_table(Counter(result.domain_counts))
