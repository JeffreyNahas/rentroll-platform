"""Typer entrypoint. Behind `make load`, invoked as `python -m ingest load ...`."""

from __future__ import annotations

from pathlib import Path

import typer
from dotenv import load_dotenv

from ingest.loader import _dsn, load_directory

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command()
def load(
    dir: Path = typer.Option(
        Path("data/raw"), "--dir",
        help="Root that contains Rent_Roll_with_Lease_Charges/ and Unit_Availability/.",
    ),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress per-file output."),
) -> None:
    """Parse and load every Excel file under DIR into the database.

    Idempotent: files whose SHA-256 is already present in `source_file` are
    skipped. A bad file rolls back its own transaction and the run continues
    with the next file.
    """
    load_dotenv()
    results = load_directory(_dsn(), dir, verbose=not quiet)

    loaded = sum(1 for r in results if r.status == "loaded")
    skipped = sum(1 for r in results if r.status == "skipped")
    errored = sum(1 for r in results if r.status == "error")
    audits_pass = sum(r.audits_pass for r in results)
    audits_fail = sum(r.audits_fail for r in results)

    typer.echo("\n" + "=" * 60)
    typer.echo(f"loaded={loaded}  skipped={skipped}  errored={errored}")
    typer.echo(f"audits: {audits_pass} pass, {audits_fail} fail")
    if errored:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
