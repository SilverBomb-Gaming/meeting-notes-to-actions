"""Drop model output that the notes do not support.

Owners and due dates that are not in the evidence quote are cleared. They are
not replaced with a guess. Items whose quote is not in the notes are removed.
"""

from __future__ import annotations

import re

from meeting_actions.models import ActionItem, Decision, MeetingExtraction, OpenQuestion
from meeting_actions.notes import normalize_ws

_MIN_QUOTE = 12
_DECISION_CUES = ("decided", "decision", "agreed", "agreement", "approved", "resolved", "settled")
_NEGATED_DECISION = re.compile(
    r"\b(?:not decided|no decision|did not decide|didn't decide)\b",
    re.IGNORECASE,
)
_AFFIRMATIVE_DECISION = re.compile(
    r"\b(?:we decided|we agreed|decision\s*[:\-]|agreed that|approved|resolved to|settled on)\b",
    re.IGNORECASE,
)
_CONTENT_STOP = {
    "that",
    "this",
    "with",
    "from",
    "into",
    "about",
    "your",
    "their",
    "there",
    "would",
    "could",
    "should",
    "have",
    "will",
    "they",
    "them",
    "were",
    "been",
    "also",
    "just",
    "still",
    "really",
    "because",
    "which",
    "where",
    "when",
    "what",
    "than",
    "then",
    "some",
    "more",
    "most",
    "other",
    "only",
    "over",
    "under",
    "after",
    "before",
    "until",
    "while",
    "those",
    "these",
    "such",
    "each",
    "every",
    "being",
    "doing",
}
_NOT_AN_OWNER = {
    "unassigned",
    "tbd",
    "n/a",
    "na",
    "none",
    "null",
    "unknown",
    "someone",
    "somebody",
    "anyone",
    "anybody",
    "everybody",
    "everyone",
    "we",
    "team",
    "the team",
    "our team",
    "the group",
    "all",
    "all of us",
}


def apply_guard(document: MeetingExtraction, notes_text: str) -> tuple[MeetingExtraction, list[str]]:
    """Return a copy that keeps only grounded items, plus warnings for what was removed."""
    warnings: list[str] = []
    actions: list[ActionItem] = []
    for item in document.actions:
        kept = _guard_action(item, notes_text, warnings)
        if kept is not None:
            actions.append(kept)
    decisions: list[Decision] = []
    for item in document.decisions:
        kept_decision = _guard_statement(
            kind="decision",
            text=item.text,
            evidence=item.evidence,
            notes_text=notes_text,
            warnings=warnings,
            cues=_DECISION_CUES,
        )
        if kept_decision is not None:
            decisions.append(Decision(text=item.text, evidence=item.evidence.strip()))
    questions: list[OpenQuestion] = []
    for item in document.open_questions:
        kept_question = _guard_statement(
            kind="open question",
            text=item.text,
            evidence=item.evidence,
            notes_text=notes_text,
            warnings=warnings,
            cues=("?", "question"),
        )
        if kept_question is not None:
            questions.append(OpenQuestion(text=item.text, evidence=item.evidence.strip()))
    return (
        MeetingExtraction(
            source=document.source,
            actions=actions,
            decisions=decisions,
            open_questions=questions,
        ),
        warnings,
    )


def _guard_action(item: ActionItem, notes_text: str, warnings: list[str]) -> ActionItem | None:
    label = _short(item.task)
    if not _quote_in_notes(item.evidence, notes_text):
        warnings.append(f"Dropped an action ({label}) because its evidence is not in the notes.")
        return None
    if not _supported(item.task, item.evidence):
        warnings.append(f"Dropped an action ({label}) because the task is not supported by its evidence quote.")
        return None
    owner = _grounded_owner(item.owner, item.evidence, notes_text, label, warnings)
    due = _grounded_due(item.due, item.evidence, notes_text, label, warnings)
    return ActionItem(task=item.task, owner=owner, due=due, evidence=item.evidence.strip())


def _guard_statement(
    *,
    kind: str,
    text: str,
    evidence: str,
    notes_text: str,
    warnings: list[str],
    cues: tuple[str, ...],
) -> str | None:
    label = _short(text)
    if not _quote_in_notes(evidence, notes_text):
        warnings.append(f"Dropped {_article(kind)} {kind} ({label}) because its evidence is not in the notes.")
        return None
    if not _supported(text, evidence):
        warnings.append(
            f"Dropped {_article(kind)} {kind} ({label}) because the text is not supported by its evidence quote."
        )
        return None
    if (
        kind == "decision"
        and _NEGATED_DECISION.search(evidence)
        and not _AFFIRMATIVE_DECISION.search(evidence)
    ):
        warnings.append(f"Dropped a decision ({label}) because the notes say it was not decided.")
        return None
    hay = normalize_ws(evidence)
    if not any(cue in hay or cue in evidence for cue in cues):
        warnings.append(f"Dropped {_article(kind)} {kind} ({label}) because the notes quote does not state one.")
        return None
    return text


def _grounded_owner(
    owner: str | None,
    evidence: str,
    notes_text: str,
    label: str,
    warnings: list[str],
) -> str | None:
    if owner is None:
        return None
    if owner.casefold() in _NOT_AN_OWNER:
        warnings.append(f"Cleared owner {owner!r} on {label} because that is not a named person.")
        return None
    if not _phrase_in(owner, notes_text) or not _phrase_in(owner, evidence):
        warnings.append(f"Cleared owner {owner!r} on {label} because that name is not in the notes quote.")
        return None
    return owner


def _grounded_due(
    due: str | None,
    evidence: str,
    notes_text: str,
    label: str,
    warnings: list[str],
) -> str | None:
    if due is None:
        return None
    if not _substring(due, notes_text) or not _substring(due, evidence):
        warnings.append(f"Cleared due date {due!r} on {label} because that date is not in the notes quote.")
        return None
    return due


def _quote_in_notes(evidence: str, notes_text: str) -> bool:
    quote = normalize_ws(evidence)
    if len(quote) < _MIN_QUOTE:
        return False
    return quote in normalize_ws(notes_text)


def _substring(phrase: str, text: str) -> bool:
    needle = normalize_ws(phrase)
    if not needle:
        return False
    return needle in normalize_ws(text)


def _phrase_in(phrase: str, text: str) -> bool:
    parts = phrase.split()
    if not parts:
        return False
    pattern = r"\b" + r"\s+".join(re.escape(part) for part in parts) + r"\b"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _supported(text: str, evidence: str) -> bool:
    words = [
        word
        for word in re.findall(r"[A-Za-z0-9']+", text.casefold())
        if len(word) >= 4 and word not in _CONTENT_STOP
    ]
    if not words:
        words = [word for word in re.findall(r"[A-Za-z0-9']+", text.casefold()) if len(word) >= 3]
    if not words:
        return False
    hay = normalize_ws(evidence)
    hits = sum(1 for word in words if word in hay)
    needed = max(1, -(-(len(words) * 6) // 10))  # ceil(0.6 * n)
    return hits >= needed


def _article(kind: str) -> str:
    return "an" if kind[:1].lower() in {"a", "e", "i", "o", "u"} else "a"


def _short(text: str) -> str:
    compact = normalize_ws(text)
    if len(compact) <= 80:
        return compact
    return compact[:77] + "..."
