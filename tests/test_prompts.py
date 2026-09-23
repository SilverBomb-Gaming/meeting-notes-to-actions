"""The model is told, in the system prompt, not to invent people or dates."""

from __future__ import annotations

from pathlib import Path

from meeting_actions.notes import LoadedNotes
from meeting_actions.prompts import SYSTEM_PROMPT, build_user_prompt

_FORBIDDEN = (
    "Do not fabricate attendees, owners, deadlines, or decisions that are not grounded in the notes text."
)


def test_system_prompt_forbids_fabrication() -> None:
    assert _FORBIDDEN in SYSTEM_PROMPT
    assert "Never guess." in SYSTEM_PROMPT
    assert "Do not add attendees." in SYSTEM_PROMPT
    assert "set owner to null" in SYSTEM_PROMPT
    assert "set due to null" in SYSTEM_PROMPT
    assert "Do not convert a weekday" in SYSTEM_PROMPT
    assert "evidence string copied verbatim" in SYSTEM_PROMPT


def test_user_prompt_repeats_the_rule_and_embeds_only_the_supplied_notes() -> None:
    notes = LoadedNotes(
        path=Path("sprint-planning.md"),
        source="sprint-planning.md",
        text="Alex Rivera will ship the staging deploy by 2026-03-14.\n",
    )
    prompt = build_user_prompt(notes)
    assert _FORBIDDEN in prompt
    assert "Alex Rivera will ship the staging deploy by 2026-03-14." in prompt
    assert "owner is a person's name copied from the notes, or null" in prompt
    assert "Do not resolve \"Friday\" to a calendar date." in prompt
    assert "Do not include an attendees field." in prompt
    assert "sprint-planning.md" in prompt
    assert "Blake" not in prompt
