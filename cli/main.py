"""CareerOS CLI root — registers all subcommands and exposes the entrypoint."""

import typer

from cli.commands.ingest import ingest_all, ingest_jobs

app = typer.Typer(
    name="careeros",
    help="CareerOS — AI career intelligence system",
    no_args_is_help=True,
)

app.command(name="ingest")(ingest_all)
app.command(name="ingest-jobs")(ingest_jobs)


@app.command(name="version")
def version():
    """Show CareerOS version."""
    typer.echo("CareerOS 0.1.0")


if __name__ == "__main__":
    app()
