"""cli/commands/archetypes.py — CLI commands for the archetype pipeline."""
import asyncio
import logging

import typer

logger = logging.getLogger("lumia.cli.archetypes")


def build_archetypes(
    force: bool = typer.Option(
        False, "--force", help="Rebuild centroids even for archetypes that already have one."
    ),
) -> None:
    """
    Upsert all role archetypes from taxonomy and build corpus-bootstrapped centroids.

    For each archetype:
      - Finds matching jobs in the corpus (title ILIKE search).
      - Averages their embeddings to form a centroid + top canonical skills.
      - Falls back to embedding the archetype title directly if < 3 corpus jobs match.

    Run this once after ingesting jobs, then re-run with --force after any
    large new ingest to refresh centroids with the updated corpus.
    """
    from core.archetypes.bootstrapper import build
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(build(force=force))


def match_resume(
    resume_id: str = typer.Argument(..., help="UUID of the resume in user_resumes table."),
    top_n: int = typer.Option(5, "--top", "-n", help="Number of top archetypes to return."),
) -> None:
    """
    Show the top-N role archetypes that best match the given resume.

    Prints each archetype's title, similarity score, matched skills, and skill gaps.
    The resume must already be embedded (run 'lumia ingest-resume' first).
    """
    from core.archetypes.matcher import match_resume as _match
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    matches = asyncio.run(_match(resume_id=resume_id, top_n=top_n))

    if not matches:
        typer.echo("No archetype matches found. Run 'lumia build-archetypes' first.")
        raise typer.Exit(1)

    typer.echo(f"\nTop {len(matches)} role matches for resume {resume_id}\n")
    typer.echo(f"{'#':<3}  {'Title':<45}  {'Sim':>5}  {'Matches':>7}  {'Gaps':>5}")
    typer.echo("─" * 80)

    for i, m in enumerate(matches, start=1):
        typer.echo(
            f"{i:<3}  {m.title:<45}  {m.similarity:>5.3f}"
            f"  {len(m.skill_matches):>7}  {len(m.skill_gaps):>5}"
        )

    typer.echo()
    for m in matches:
        typer.echo(f"── {m.title}  [{m.category}]")
        if m.skill_matches:
            typer.echo(f"   You have:  {', '.join(m.skill_matches[:8])}")
        if m.skill_gaps:
            typer.echo(f"   You need:  {', '.join(m.skill_gaps[:8])}")
        typer.echo()
