"""Load .txt and .md notes. PDF, DOCX, and audio are out of scope."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from meeting_actions.errors import UsageError

ALLOWED_SUFFIXES = {".txt", ".md"}
MAX_NOTES_CHARS = 100_000

_OUT_OF_SCOPE = (
    "This tool reads .txt and .md only. PDF, DOCX, and audio transcription are out of scope."
)


@dataclass(frozen=True)
class LoadedNotes:
    """Normalized notes plus the file name used as the extraction source."""

    path: Path
    source: str
    text: str


def load_notes(path: Path) -> LoadedNotes:
    """Read UTF-8 notes and reject anything that is not a plain .txt or .md file."""
    suffix = path.suffix.lower()
    if suffix and suffix not in ALLOWED_SUFFIXES:
        raise UsageError(f"Unsupported notes file {path.name}. {_OUT_OF_SCOPE}")
    if not path.exists():
        raise UsageError(f"Notes file not found: {path}")
    if not path.is_file():
        raise UsageError(f"Notes path is not a file: {path}")
    if suffix not in ALLOWED_SUFFIXES:
        raise UsageError(f"Unsupported notes file {path.name}. {_OUT_OF_SCOPE}")
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise UsageError(f"{path} is not UTF-8 text. {_OUT_OF_SCOPE}") from exc
    text = normalize_notes(raw)
    if not text.strip():
        raise UsageError(f"Notes file is empty: {path}")
    if len(text) > MAX_NOTES_CHARS:
        raise UsageError(
            f"Notes file is longer than {MAX_NOTES_CHARS} characters. Split it into smaller .txt or .md files."
        )
    return LoadedNotes(path=path, source=path.name, text=text)


def normalize_notes(raw: str) -> str:
    """Newlines, a leading BOM, and trailing spaces. The words stay as written."""
    text = raw.replace("\ufeff", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    if not text:
        return ""
    return text + "\n"


def normalize_ws(value: str) -> str:
    """Casefold and collapse whitespace so a quote can be found in the notes."""
    return re.sub(r"\s+", " ", value).strip().casefold()
