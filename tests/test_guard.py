"""Invented owners, dates, and decisions do not survive the grounding check."""

from __future__ import annotations

from meeting_actions.guard import apply_guard
from meeting_actions.models import ActionItem, Decision, MeetingExtraction, OpenQuestion

NOTES = (
    "Alex will file the report by 2026-05-01.\n"
    "We decided to ship on Friday.\n"
    "Who owns the pager next week?\n"
)


def _document() -> MeetingExtraction:
    return MeetingExtraction(
        source="notes.md",
        actions=[
            ActionItem(
                task="File the report",
                owner="Blake",
                due="2099-01-01",
                evidence="Alex will file the report by 2026-05-01.",
            ),
            ActionItem(
                task="Book the offsite venue",
                owner="Alex",
                due="Friday",
                evidence="We should book a venue downtown.",
            ),
            ActionItem(
                task="Who owns the pager next week",
                owner="someone",
                due=None,
                evidence="Who owns the pager next week?",
            ),
        ],
        decisions=[
            Decision(text="Hire a new vendor", evidence="We decided to hire a new vendor."),
            Decision(text="Ship on Friday", evidence="We decided to ship on Friday."),
        ],
        open_questions=[
            OpenQuestion(text="What about the budget?", evidence="What about the budget?"),
            OpenQuestion(text="Who owns the pager next week?", evidence="Who owns the pager next week?"),
        ],
    )


def test_guard_clears_invented_owner_and_date_and_drops_ungrounded_items() -> None:
    document, warnings = apply_guard(_document(), NOTES)
    assert [(item.task, item.owner, item.due) for item in document.actions] == [
        ("File the report", None, None),
        ("Who owns the pager next week", None, None),
    ]
    assert [item.text for item in document.decisions] == ["Ship on Friday"]
    assert [item.text for item in document.open_questions] == ["Who owns the pager next week?"]
    warning_text = " ".join(warnings)
    assert "Blake" in warning_text
    assert "2099-01-01" in warning_text
    assert "book the offsite venue" in warning_text
    assert "hire a new vendor" in warning_text
    assert "budget" in warning_text
    assert "someone" in warning_text


def test_a_quote_that_says_not_decided_is_not_a_decision() -> None:
    notes = "maybe we should rewrite the whole platform someday? not decided.\n"
    document = MeetingExtraction(
        source="notes.txt",
        decisions=[
            Decision(
                text="Rewrite the whole platform someday",
                evidence="maybe we should rewrite the whole platform someday? not decided.",
            )
        ],
    )
    guarded, warnings = apply_guard(document, notes)
    assert guarded.decisions == []
    assert any("not decided" in warning for warning in warnings)


def test_grounded_owner_and_due_are_kept_when_the_quote_contains_them() -> None:
    document = MeetingExtraction(
        source="notes.md",
        actions=[
            ActionItem(
                task="File the report",
                owner="Alex",
                due="2026-05-01",
                evidence="Alex will file the report by 2026-05-01.",
            )
        ],
    )
    guarded, warnings = apply_guard(document, NOTES)
    assert guarded.actions[0].owner == "Alex"
    assert guarded.actions[0].due == "2026-05-01"
    assert warnings == []
