"""Prompts for extraction. The program, not the model, drops anything the notes do not support."""

from __future__ import annotations

from meeting_actions.notes import LoadedNotes

SYSTEM_PROMPT = """You extract action items, decisions, and open questions from meeting notes the user supplies.

Rules:
- Do not fabricate attendees, owners, deadlines, or decisions that are not grounded in the notes text.
- Do not invent a person, a date, or a decision to fill a gap.
- If the notes do not name an owner for a task, set owner to null. Never guess. "someone", "we", "the team", "TBD", and "everyone" are not owners.
- If the notes do not state a due date or deadline, set due to null. Never guess.
- A due value must be copied from the notes. Do not convert a weekday or "next week" into a calendar date that the notes do not contain.
- Do not add attendees. There is no attendees field.
- Every action, decision, and open question must include an evidence string copied verbatim from the notes. If you cannot quote the notes, omit the item.
- When owner is not null, that exact name must appear in the evidence quote.
- When due is not null, that exact due text must appear in the evidence quote.
- Do not add tasks, decisions, or questions that the notes do not state.
- Return a single JSON object and nothing else.
"""

_SCHEMA = """{
  "actions": [
    {
      "task": "Short task wording taken from the notes. No invented detail.",
      "owner": null,
      "due": null,
      "evidence": "verbatim quote from the notes that states this task"
    }
  ],
  "decisions": [
    {
      "text": "What was decided, taken from the notes.",
      "evidence": "verbatim quote that states the decision"
    }
  ],
  "open_questions": [
    {
      "text": "The question, taken from the notes.",
      "evidence": "verbatim quote that states the question"
    }
  ]
}"""


def build_user_prompt(notes: LoadedNotes) -> str:
    """Ask the model to extract structure. The only legal facts are inside the notes block."""
    return f"""TASK: meeting-notes

Extract action items, decisions, and open questions from the notes below.
The file name is {notes.source}. Do not invent a title, attendee list, owner, or date from the file name.

Return a JSON object with this shape:
{_SCHEMA}

Rules for this task:
- Do not fabricate attendees, owners, deadlines, or decisions that are not grounded in the notes text.
- owner is a person's name copied from the notes, or null when the notes do not name one. Use null for unassigned. Do not write the word "unassigned".
- due is a date or deadline phrase copied from the notes, or null when the notes do not state one. Use null for no due date. Do not resolve "Friday" to a calendar date.
- evidence must be a contiguous quote from the notes. Paraphrases are not evidence.
- If a section has nothing grounded, return an empty list for it.
- Do not include an attendees field.

NOTES
<<<
{notes.text}>>>
"""
