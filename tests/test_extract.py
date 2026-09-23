"""Model output is parsed, grounded, or replaced by the heuristic."""

from __future__ import annotations

import json

from meeting_actions.extract import extract_notes
from meeting_actions.notes import load_notes
from meeting_actions.prompts import SYSTEM_PROMPT


class FakeClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[tuple[str, str]] = []
        self.closed = False

    def complete(self, *, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.content

    def close(self) -> None:
        self.closed = True


def test_grounded_model_json_is_kept(tmp_path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("Alex will file the report by 2026-05-01.\n", encoding="utf-8")
    notes = load_notes(path)
    client = FakeClient(
        json.dumps(
            {
                "actions": [
                    {
                        "task": "File the report",
                        "owner": "Alex",
                        "due": "2026-05-01",
                        "evidence": "Alex will file the report by 2026-05-01.",
                    }
                ],
                "decisions": [],
                "open_questions": [],
            }
        )
    )
    result = extract_notes(notes, client=client, use_llm=True)
    assert result.warnings == []
    assert result.document.actions[0].owner == "Alex"
    assert result.document.actions[0].due == "2026-05-01"
    assert SYSTEM_PROMPT in client.calls[0][0]
    assert "Alex will file the report by 2026-05-01." in client.calls[0][1]


def test_invented_items_fall_back_to_the_heuristic(tmp_path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("- Alex Rivera will file the report by 2026-05-01.\n", encoding="utf-8")
    notes = load_notes(path)
    client = FakeClient(
        json.dumps(
            {
                "attendees": ["Blake"],
                "actions": [
                    {
                        "task": "Book the offsite venue",
                        "owner": "Blake",
                        "due": "2099-01-01",
                        "evidence": "Alex Rivera will file the report by 2026-05-01.",
                    }
                ],
            }
        )
    )
    result = extract_notes(notes, client=client, use_llm=True)
    assert any("Fell back to heuristic extraction." in warning for warning in result.warnings)
    action = result.document.actions[0]
    assert action.task == "File the report"
    assert action.owner == "Alex Rivera"
    assert action.due == "2026-05-01"
    assert "Blake" not in action.task
    assert action.due != "2099-01-01"


def test_unusable_json_falls_back_without_calling_out_to_a_network(tmp_path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("TODO: capture the incident timeline\n", encoding="utf-8")
    notes = load_notes(path)
    client = FakeClient("I invented a deadline of tomorrow for Jordan.")
    result = extract_notes(notes, client=client, use_llm=True)
    assert result.warnings[0] == "Model output was not usable JSON. Fell back to heuristic extraction."
    assert result.document.actions[0].task == "Capture the incident timeline"
    assert result.document.actions[0].owner is None
    assert result.document.actions[0].due is None


def test_empty_model_object_falls_back_when_the_heuristic_finds_work(tmp_path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("TODO: capture the incident timeline\n", encoding="utf-8")
    client = FakeClient(json.dumps({"actions": [], "decisions": [], "open_questions": []}))
    result = extract_notes(load_notes(path), client=client, use_llm=True)
    assert result.warnings[0] == "Model returned no items. Fell back to heuristic extraction."
    assert result.document.actions[0].task == "Capture the incident timeline"
    assert result.document.actions[0].owner is None


def test_empty_model_object_stays_empty_when_nothing_is_marked(tmp_path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("We talked about the weather and then adjourned.\n", encoding="utf-8")
    client = FakeClient(json.dumps({"actions": [], "decisions": [], "open_questions": []}))
    result = extract_notes(load_notes(path), client=client, use_llm=True)
    assert result.warnings == []
    assert result.document.actions == []
    assert result.document.decisions == []
    assert result.document.open_questions == []


def test_no_llm_does_not_need_a_client(tmp_path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("TODO: capture the incident timeline\n", encoding="utf-8")
    result = extract_notes(load_notes(path), client=None, use_llm=False)
    assert result.document.actions[0].owner is None
    assert result.warnings == []
