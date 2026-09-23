"""Markdown labels gaps; JSON uses null and keeps the evidence quote."""

from __future__ import annotations

import json
from pathlib import Path

from meeting_actions.models import ActionItem, Decision, MeetingExtraction, OpenQuestion
from meeting_actions.notes import LoadedNotes
from meeting_actions.render import render_json, render_markdown, render_normalized


def _document() -> MeetingExtraction:
    return MeetingExtraction(
        source="notes.md",
        actions=[
            ActionItem(task="File the report", owner="Alex", due="2026-05-01", evidence="Alex will file the report."),
            ActionItem(task="Order stickers", owner=None, due=None, evidence="TODO: order stickers"),
        ],
        decisions=[Decision(text="Ship on Friday", evidence="We decided to ship on Friday.")],
        open_questions=[OpenQuestion(text="Who owns the pager?", evidence="Who owns the pager?")],
    )


def test_markdown_checklist_marks_unassigned_and_no_due_date() -> None:
    text = render_markdown(_document())
    assert text.startswith("# Actions from notes.md\n")
    assert "- [ ] File the report — Alex — due 2026-05-01\n" in text
    assert "- [ ] Order stickers — unassigned — no due date\n" in text
    assert "- Ship on Friday\n" in text
    assert "- Who owns the pager?\n" in text
    assert "attendees" not in text.casefold()


def test_markdown_empty_sections_are_explicit() -> None:
    text = render_markdown(MeetingExtraction(source="empty.md"))
    assert "_No action items found in the notes._" in text
    assert "_No decisions found in the notes._" in text
    assert "_No open questions found in the notes._" in text


def test_json_uses_null_and_includes_evidence() -> None:
    payload = json.loads(render_json(_document()))
    assert payload["source"] == "notes.md"
    assert payload["actions"][1] == {
        "task": "Order stickers",
        "owner": None,
        "due": None,
        "evidence": "TODO: order stickers",
    }
    assert "attendees" not in payload
    assert list(payload) == ["source", "actions", "decisions", "open_questions"]


def test_dry_run_render_is_the_normalized_notes() -> None:
    notes = LoadedNotes(path=Path("notes.md"), source="notes.md", text="Alex will file the report.\n")
    text = render_normalized(notes)
    assert text == "# Normalized notes: notes.md\n\nAlex will file the report.\n"
    assert "## Action items" not in text
