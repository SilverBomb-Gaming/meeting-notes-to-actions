"""Markdown checklist and JSON for one extraction."""

from __future__ import annotations

import json

from meeting_actions.models import MeetingExtraction
from meeting_actions.notes import LoadedNotes


def render_markdown(document: MeetingExtraction) -> str:
    """A checklist. Missing owners and due dates are labeled, not filled in."""
    lines = [f"# Actions from {document.source}", "", "## Action items", ""]
    if document.actions:
        for item in document.actions:
            lines.append(f"- [ ] {item.task} — {_owner_label(item.owner)} — {_due_label(item.due)}")
    else:
        lines.append("_No action items found in the notes._")
    lines.extend(["", "## Decisions", ""])
    if document.decisions:
        for item in document.decisions:
            lines.append(f"- {item.text}")
    else:
        lines.append("_No decisions found in the notes._")
    lines.extend(["", "## Open questions", ""])
    if document.open_questions:
        for item in document.open_questions:
            lines.append(f"- {item.text}")
    else:
        lines.append("_No open questions found in the notes._")
    lines.append("")
    return "\n".join(lines)


def render_json(document: MeetingExtraction) -> str:
    """JSON with null owner and due when the notes did not state them.

    ``evidence`` is the quote the extractor kept. Markdown omits it so the
    checklist stays pasteable.
    """
    payload = {
        "source": document.source,
        "actions": [
            {"task": item.task, "owner": item.owner, "due": item.due, "evidence": item.evidence}
            for item in document.actions
        ],
        "decisions": [{"text": item.text, "evidence": item.evidence} for item in document.decisions],
        "open_questions": [{"text": item.text, "evidence": item.evidence} for item in document.open_questions],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def render_normalized(notes: LoadedNotes) -> str:
    """The notes after newline cleanup. No extraction and no model call."""
    return f"# Normalized notes: {notes.source}\n\n{notes.text}"


def render_document(document: MeetingExtraction, output_format: str) -> str:
    if output_format == "json":
        return render_json(document)
    return render_markdown(document)


def _owner_label(owner: str | None) -> str:
    return owner if owner else "unassigned"


def _due_label(due: str | None) -> str:
    return f"due {due}" if due else "no due date"
