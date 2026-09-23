"""Schema: null owner and due are valid, and invented fields are ignored."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from meeting_actions.extract import parse_llm_output
from meeting_actions.models import ActionItem, LLMExtraction, MeetingExtraction


def test_action_allows_null_owner_and_due() -> None:
    item = ActionItem(task="File the report", owner=None, due=None, evidence="File the report.")
    assert item.owner is None
    assert item.due is None


def test_empty_owner_and_due_markers_become_null() -> None:
    item = ActionItem(
        task="File the report",
        owner="unassigned",
        due="no due date",
        evidence="File the report.",
    )
    assert item.owner is None
    assert item.due is None
    assert ActionItem.model_validate(
        {"task": "File the report", "owner": "TBD", "due": "n/a", "evidence": "File the report."}
    ).owner is None


def test_public_document_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        MeetingExtraction.model_validate({"source": "notes.md", "attendees": ["Alex"], "actions": []})


def test_llm_schema_ignores_attendees_and_keeps_nulls() -> None:
    parsed = parse_llm_output(
        """```json
        {
          "attendees": ["Blake", "The team"],
          "actions": [
            {"task": "File the report", "owner": null, "due": "null", "evidence": "File the report.", "priority": "P0"}
          ],
          "decisions": {"text": "Ship Friday.", "evidence": "We decided to ship Friday."},
          "open_questions": []
        }
        ```"""
    )
    assert isinstance(parsed, LLMExtraction)
    assert not hasattr(parsed, "attendees") or "attendees" not in parsed.model_fields
    assert parsed.actions[0].owner is None
    assert parsed.actions[0].due is None
    assert parsed.actions[0].task == "File the report"
    assert parsed.decisions[0].text == "Ship Friday."
    dumped = parsed.model_dump()
    assert "attendees" not in dumped


def test_llm_output_must_be_an_object() -> None:
    with pytest.raises(ValueError, match="JSON"):
        parse_llm_output("not json at all")
    with pytest.raises(ValueError, match="JSON object"):
        parse_llm_output("[1, 2, 3]")
