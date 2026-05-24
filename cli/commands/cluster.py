"""CLI command for running job clustering (Phase 5)."""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from sqlalchemy import select

console = Console()


def cluster(
    k: Annotated[int, typer.Option("--k", help="Number of clusters")] = 10,
    force: Annotated[bool, typer.Option("--force", help="Re-run even if today's run exists")] = False,
) -> None:
    """Group jobs into role clusters using KMeans on job embeddings."""

    async def _main():
        from core.clustering.kmeans import ClusteringEngine
        from database.models import RoleCluster
        from database.session import async_session

        console.print(f"\n[bold]Running KMeans clustering (k={k})…[/bold]\n")

        engine = ClusteringEngine()
        run_id = await engine.run_clustering(k=k, force=force)

        if run_id is None:
            console.print("[bold red]Clustering failed — no job embeddings found. Run embed-jobs first.[/bold red]")
            raise typer.Exit(1)

        async with async_session() as session:
            clusters = (await session.execute(
                select(RoleCluster)
                .where(RoleCluster.run_id == run_id)
                .order_by(RoleCluster.cluster_index)
            )).scalars().all()

        table = Table(title=f"Role Clusters — run {run_id}", show_lines=True)
        table.add_column("#", style="bold", justify="right")
        table.add_column("Label", style="cyan")
        table.add_column("Jobs", justify="right")
        table.add_column("Top Skills")

        for c in clusters:
            top3 = ", ".join((c.top_skills or [])[:3]) or "—"
            table.add_row(str(c.cluster_index), c.label or "—", str(c.job_count), top3)

        console.print(table)
        console.print()

    asyncio.run(_main())