"""Command-line interface for meeting-actions."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from meeting_actions import __version__
from meeting_actions.dotenv import load_dotenv
from meeting_actions.errors import LLMError, MeetingActionsError, UsageError
from meeting_actions.extract import extract_notes
from meeting_actions.llm import build_client
from meeting_actions.notes import load_notes
from meeting_actions.render import render_document, render_normalized

app = typer.Typer(
    name="meeting-actions",
    help="Turn meeting notes into action items, decisions, and open questions.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"meeting-actions {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
) -> None:
    """Turn meeting notes into action items, decisions, and open questions."""


@app.command("extract")
def extract_cmd(
    notes: Annotated[
        Path,
        typer.Option("--notes", help="Path to a .txt or .md notes file."),
    ],
    out: Annotated[
        Optional[Path],
        typer.Option("--out", help="Also write the stdout text to this file."),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", help="markdown (default) or json. Ignored with --dry-run."),
    ] = "markdown",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Print the normalized notes and stop. Do not extract and do not call a model.",
        ),
    ] = False,
    no_llm: Annotated[
        bool,
        typer.Option(
            "--no-llm",
            help="Heuristic extraction only. Do not call a model.",
        ),
    ] = False,
    provider: Annotated[
        Optional[str],
        typer.Option("--provider", help="ollama (default) or openai. Overrides MEETING_ACTIONS_PROVIDER."),
    ] = None,
    model: Annotated[
        Optional[str],
        typer.Option("--model", help="Model name. Overrides OLLAMA_MODEL or OPENAI_MODEL for this command."),
    ] = None,
) -> None:
    """Extract action items from a notes file and write them to stdout."""
    try:
        _extract(
            notes=notes,
            out=out,
            output_format=output_format,
            dry_run=dry_run,
            no_llm=no_llm,
            provider=provider,
            model=model,
        )
    except UsageError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc
    except (LLMError, MeetingActionsError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(2) from exc


def _extract(
    *,
    notes: Path,
    out: Path | None,
    output_format: str,
    dry_run: bool,
    no_llm: bool,
    provider: str | None,
    model: str | None,
) -> None:
    if dry_run and no_llm:
        raise UsageError(
            "Use either --dry-run (normalized notes only) or --no-llm (heuristic extraction). Both skip the model."
        )
    selected = output_format.strip().lower()
    if selected not in {"markdown", "json"}:
        raise UsageError("--format must be markdown or json.")

    load_dotenv()
    loaded = load_notes(notes)
    if dry_run:
        if selected == "json":
            typer.echo("warning: --format is ignored with --dry-run.", err=True)
        payload = render_normalized(loaded)
        _emit(payload, out)
        return

    use_llm = not no_llm
    client = build_client(provider, model) if use_llm else None
    try:
        result = extract_notes(loaded, client=client, use_llm=use_llm)
    finally:
        if client is not None:
            client.close()

    for warning in result.warnings:
        typer.echo(f"warning: {warning}", err=True)
    _emit(render_document(result.document, selected), out)


def _emit(payload: str, out: Path | None) -> None:
    typer.echo(payload, nl=False)
    if out is None:
        return
    if not out.parent.exists():
        raise UsageError(f"Directory does not exist: {out.parent}")
    out.write_text(payload, encoding="utf-8")
    typer.echo(f"Wrote {out}.", err=True)
