"""Loading and normalizing .txt and .md notes."""

from __future__ import annotations

from pathlib import Path

import pytest

from meeting_actions.errors import UsageError
from meeting_actions.notes import load_notes, normalize_notes

ROOT = Path(__file__).resolve().parents[1]


def test_normalize_strips_bom_crlf_and_extra_blank_lines() -> None:
    raw = "\ufeff# Notes\r\n\r\n\r\nAlex will send the recap.\r\n"
    assert normalize_notes(raw) == "# Notes\n\nAlex will send the recap.\n"


def test_load_txt_and_md(tmp_path: Path) -> None:
    text_path = tmp_path / "notes.txt"
    text_path.write_text("Alex will send the recap.\n", encoding="utf-8")
    md_path = tmp_path / "NOTES.MD"
    md_path.write_text("# Standup\n\n- [ ] File the report.\n", encoding="utf-8")

    text = load_notes(text_path)
    markdown = load_notes(md_path)
    assert text.source == "notes.txt"
    assert "Alex will send the recap." in text.text
    assert markdown.source == "NOTES.MD"
    assert markdown.text.startswith("# Standup\n")


def test_samples_load() -> None:
    sprint = load_notes(ROOT / "samples" / "sprint-planning.md")
    messy = load_notes(ROOT / "samples" / "messy-retro.txt")
    assert sprint.source == "sprint-planning.md"
    assert "Alex Rivera will ship the staging deploy" in sprint.text
    assert messy.source == "messy-retro.txt"
    assert "legacy webhook" in messy.text


@pytest.mark.parametrize("name", ["notes.pdf", "notes.docx", "notes.mp3", "notes.markdown"])
def test_rejects_unsupported_types(tmp_path: Path, name: str) -> None:
    path = tmp_path / name
    path.write_text("Alex will send the recap.\n", encoding="utf-8")
    with pytest.raises(UsageError, match="PDF, DOCX, and audio"):
        load_notes(path)


def test_rejects_missing_empty_and_directory(tmp_path: Path) -> None:
    with pytest.raises(UsageError, match="not found"):
        load_notes(tmp_path / "missing.md")
    empty = tmp_path / "empty.md"
    empty.write_text("  \n\n", encoding="utf-8")
    with pytest.raises(UsageError, match="empty"):
        load_notes(empty)
    with pytest.raises(UsageError, match="not a file"):
        load_notes(tmp_path)


def test_rejects_non_utf8(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_bytes(b"\xff\xfe not utf-8")
    with pytest.raises(UsageError, match="UTF-8"):
        load_notes(path)


def test_rejects_oversized_notes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("meeting_actions.notes.MAX_NOTES_CHARS", 30)
    path = tmp_path / "notes.md"
    path.write_text("Alex will send a very long recap that does not fit.\n", encoding="utf-8")
    with pytest.raises(UsageError, match="longer than 30"):
        load_notes(path)
