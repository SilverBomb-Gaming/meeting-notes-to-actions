"""Heuristic extraction stays inside the lines that are actually marked."""

from __future__ import annotations

from pathlib import Path

from meeting_actions.extract import extract_notes
from meeting_actions.heuristic import extract_due, extract_heuristic
from meeting_actions.notes import load_notes

ROOT = Path(__file__).resolve().parents[1]


def _run(name: str):
    notes = load_notes(ROOT / "samples" / name)
    result = extract_notes(notes, client=None, use_llm=False)
    return result.document


def test_clear_sprint_notes_keep_named_owners_and_dates() -> None:
    document = _run("sprint-planning.md")
    actions = {(item.task, item.owner, item.due) for item in document.actions}
    assert actions == {
        ("Ship the staging deploy", "Alex Rivera", "2026-03-14"),
        ("Write the rollback note", "Sam Okonkwo", "Friday"),
        ("Update the on-call roster", "Priya Shah", "2026-03-18"),
    }
    assert [item.text for item in document.decisions] == [
        "Keep the staging cluster on the current image until the rollback note is written"
    ]
    assert [item.text for item in document.open_questions] == [
        "Who covers the pager if Sam is out next Monday?"
    ]
    assert all(item.owner != "unassigned" for item in document.actions)
    joined = " ".join(item.task for item in document.actions)
    assert "Attendees mentioned" not in joined


def test_messy_notes_do_not_invent_owners_or_deadlines() -> None:
    document = _run("messy-retro.txt")
    assert [(item.task, item.owner, item.due) for item in document.actions] == [
        ("Capture the incident timeline from the slack thread", None, None),
        ("Ask the vendor about the timeout", None, None),
    ]
    assert [item.text for item in document.decisions] == ["The retro stays 25 minutes"]
    assert [item.text for item in document.open_questions] == ["Do we even need the legacy webhook?"]
    blob = " ".join(
        [
            *(item.task for item in document.actions),
            *(item.text for item in document.decisions),
            *(item.text for item in document.open_questions),
            *(item.owner or "" for item in document.actions),
            *(item.due or "" for item in document.actions),
        ]
    )
    assert "Jordan" not in blob
    assert "pizza" not in blob.casefold()
    assert "rewrite the whole platform" not in blob.casefold()
    assert "clean up the labels" not in blob.casefold()
    assert "2099" not in blob
    assert "3/11" not in blob


def test_owner_and_due_lines_under_a_checkbox_attach_without_guessing(tmp_path: Path) -> None:
    path = tmp_path / "follow-up.md"
    path.write_text(
        "- [ ] publish the notes\n  Owner: Riley Chen\n  Due: 2026-04-02\n\n"
        "- [ ] order stickers\n  Owner: someone\n",
        encoding="utf-8",
    )
    document = extract_heuristic(load_notes(path))
    assert [(item.task, item.owner, item.due) for item in document.actions] == [
        ("Publish the notes", "Riley Chen", "2026-04-02"),
        ("Order stickers", None, None),
    ]
    assert "Riley Chen" in document.actions[0].evidence
    assert "2026-04-02" in document.actions[0].evidence


def test_extract_due_does_not_resolve_a_weekday() -> None:
    assert extract_due("Sam will write the note by Friday.") == "Friday"
    assert extract_due("Due: 2026-03-18") == "2026-03-18"
    assert extract_due("nobody wrote down a date to retry") is None
    assert extract_due("by next week") == "next week"
