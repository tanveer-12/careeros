"""Lumia CLI root — registers all subcommands and exposes the entrypoint."""

import typer

from cli.commands.ingest import ingest_all, ingest_jobs, ingest_resume
from cli.commands.archetypes import build_archetypes, match_resume

app = typer.Typer(
    name="lumia",
    help="Lumia - AI career intelligence system",
    no_args_is_help=True,
)

app.command(name="ingest")(ingest_all)
app.command(name="ingest-jobs")(ingest_jobs)
app.command(name="ingest-resume")(ingest_resume)
app.command(name="build-archetypes")(build_archetypes)
app.command(name="match-resume")(match_resume)


@app.command(name="version")
def version():
    """Show Lumia version."""
    typer.echo("Lumia 0.2.0")


if __name__ == "__main__":
    app()
