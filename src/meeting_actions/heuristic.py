"""Line-oriented extraction used when the model is not called.

A line becomes an action only when it is marked as work: a checkbox, a TODO or
Action prefix, or a person who will, should, or needs to do something. Prose
stays prose. Owner and due date are copied from that line, or from an Owner
or Due line directly underneath. If neither is there, the fields stay empty.
"""

from __future__ import annotations

import re

from meeting_actions.models import ActionItem, Decision, MeetingExtraction, OpenQuestion
from meeting_actions.notes import LoadedNotes, normalize_ws

_CHECKBOX = re.compile(r"^(?:[-*]|\d+[.)])\s+\[[ xX]\]\s+(?P<text>.+)$")
_BULLET = re.compile(r"^(?:[-*]|\d+[.)])\s+")
_ACTION_PREFIX = re.compile(
    r"^(?:action(?:\s+item)?|todo)\s*[:\-]\s*(?P<text>.+)$",
    re.IGNORECASE,
)
_DECISION = re.compile(
    r"^(?:decision\s*[:\-]\s*(?P<labeled>.+)|we\s+(?:decided|agreed)(?:\s+that)?\s+(?P<agreed>.+))$",
    re.IGNORECASE,
)
_QUESTION_PREFIX = re.compile(
    r"^(?:open\s+question|question|q)\s*[:\-]\s*(?P<text>.+)$",
    re.IGNORECASE,
)
_OWNER_LINE = re.compile(r"^owner\s*[:\-]\s*(?P<name>.+)$", re.IGNORECASE)
_DUE_LINE = re.compile(r"^(?:due|deadline)\s*[:\-]\s*(?P<due>.+)$", re.IGNORECASE)
_NAME_WILL = re.compile(
    r"^(?P<owner>[A-Z][A-Za-z'.-]+(?:\s+[A-Z][A-Za-z'.-]+){0,2})\s+"
    r"(?:will|shall|should|must|needs to|need to|to)\s+(?P<task>.+)$"
)
_NAME_COLON = re.compile(
    r"^(?P<owner>[A-Z][A-Za-z'.-]+(?:\s+[A-Z][A-Za-z'.-]+){0,2})\s*[:\u2014\-]\s+(?P<task>.+)$"
)
_INLINE_OWNER = re.compile(
    r"\bowner\s*[:\-]\s*(?P<name>[A-Z][A-Za-z'.-]+(?:\s+[A-Z][A-Za-z'.-]+){0,2})",
    re.IGNORECASE,
)
_AT_OWNER = re.compile(r"(?<![\w.])@(?P<name>[A-Za-z][\w-]{1,40})")
_ISO = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_MONTH_DAY = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{1,2}(?:,\s*\d{4})?\b",
    re.IGNORECASE,
)
_DAY_MONTH = re.compile(
    r"\b\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)(?:\s+\d{4})?\b",
    re.IGNORECASE,
)
_DUE_PHRASE = re.compile(
    r"\b(?:due|by|before|deadline)\s+"
    r"(?P<due>"
    r"\d{4}-\d{2}-\d{2}"
    r"|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{1,2}(?:,\s*\d{4})?"
    r"|\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)(?:\s+\d{4})?"
    r"|(?:Mon|Tue(?:s)?|Wed(?:nes)?|Thu(?:rs)?|Fri|Sat(?:ur)?|Sun)(?:day)?"
    r"|(?:end of|next)\s+[A-Za-z]+"
    r"|\d{1,2}/\d{1,2}(?:/\d{2,4})?"
    r")\b",
    re.IGNORECASE,
)
_NOT_DECIDED = re.compile(
    r"\b(?:not decided|no decision|did not decide|didn't decide)\b",
    re.IGNORECASE,
)
_NO_OWNER_CLAUSE = re.compile(
    r"[.,;]?\s*(?:no owner(?:\s+in the room)?|owner tbd|unassigned)\.?\s*$",
    re.IGNORECASE,
)

_NOT_A_PERSON = {
    "we",
    "the",
    "someone",
    "somebody",
    "anyone",
    "anybody",
    "everybody",
    "everyone",
    "team",
    "they",
    "you",
    "our",
    "their",
    "action",
    "todo",
    "note",
    "notes",
    "decision",
    "question",
    "owner",
    "due",
    "deadline",
    "unassigned",
    "tbd",
    "none",
    "unknown",
    "random",
    "attendees",
}
_CALENDAR = {
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
}


def extract_heuristic(notes: LoadedNotes) -> MeetingExtraction:
    """Build a document from explicit lines only. Does not call a model."""
    actions: list[ActionItem] = []
    decisions: list[Decision] = []
    questions: list[OpenQuestion] = []
    pending: ActionItem | None = None

    for raw_line in notes.text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            pending = None
            continue
        body = _without_bullet(stripped)

        owner_line = _OWNER_LINE.fullmatch(body)
        if owner_line:
            if pending is not None and pending.owner is None:
                name = owner_line.group("name").strip().rstrip(".")
                if valid_owner(name):
                    pending.owner = name
                    pending.evidence = _append_evidence(pending.evidence, stripped)
            continue

        due_line = _DUE_LINE.fullmatch(body)
        if due_line:
            if pending is not None and pending.due is None:
                raw_due = due_line.group("due").strip()
                due = extract_due(raw_due) or extract_due(f"due {raw_due}")
                if due:
                    pending.due = due
                    pending.evidence = _append_evidence(pending.evidence, stripped)
            continue

        decision = _parse_decision(body, stripped)
        if decision is not None:
            decisions.append(decision)
            pending = None
            continue

        action = _parse_action_line(stripped, body)
        if action is not None:
            actions.append(action)
            pending = action
            continue

        question = _parse_question(body, stripped)
        if question is not None:
            questions.append(question)
            pending = None
            continue

        pending = None

    return MeetingExtraction(
        source=notes.source,
        actions=_dedupe(actions, lambda item: item.task),
        decisions=_dedupe(decisions, lambda item: item.text),
        open_questions=_dedupe(questions, lambda item: item.text),
    )


def extract_due(text: str) -> str | None:
    """Return a date or deadline phrase that is literally in ``text``, or None."""
    iso = _ISO.search(text)
    if iso:
        return iso.group(0)
    month = _MONTH_DAY.search(text)
    if month:
        return month.group(0)
    day_month = _DAY_MONTH.search(text)
    if day_month:
        return day_month.group(0)
    phrase = _DUE_PHRASE.search(text)
    if phrase:
        return phrase.group("due")
    return None


def valid_owner(name: str) -> bool:
    """True when ``name`` looks like a person, not a role, weekday, or filler word."""
    cleaned = name.strip().strip(".,;:")
    parts = cleaned.split()
    if not parts or len(parts) > 3:
        return False
    if parts[0].casefold() in _NOT_A_PERSON:
        return False
    if len(parts) == 1 and parts[0].casefold() in _CALENDAR:
        return False
    for part in parts:
        if part.casefold() in _NOT_A_PERSON:
            return False
        if not re.fullmatch(r"[A-Za-z][A-Za-z'.-]{1,}", part):
            return False
    return True


def _parse_action_line(stripped: str, body: str) -> ActionItem | None:
    checkbox = _CHECKBOX.match(stripped)
    if checkbox:
        return _build_action(checkbox.group("text"), stripped)
    prefix = _ACTION_PREFIX.match(body)
    if prefix:
        return _build_action(prefix.group("text"), stripped)
    will = _NAME_WILL.match(body)
    if will and valid_owner(will.group("owner")):
        return _build_action(body, stripped)
    if _BULLET.match(stripped):
        colon = _NAME_COLON.match(body)
        if colon and valid_owner(colon.group("owner")):
            return _build_action(body, stripped)
    return None


def _build_action(text: str, evidence: str) -> ActionItem | None:
    owner = _owner_from_text(text)
    working = text.strip()
    due = extract_due(working)
    task = _clean_task(working, owner, due)
    if len(normalize_ws(task)) < 3:
        return None
    return ActionItem(task=_sentence_case(task), owner=owner, due=due, evidence=evidence.strip())


def _owner_from_text(text: str) -> str | None:
    inline = _INLINE_OWNER.search(text)
    if inline and valid_owner(inline.group("name")):
        return inline.group("name").strip()
    colon = _NAME_COLON.match(text)
    if colon and valid_owner(colon.group("owner")):
        return colon.group("owner").strip()
    will = _NAME_WILL.match(text)
    if will and valid_owner(will.group("owner")):
        return will.group("owner").strip()
    at = _AT_OWNER.search(text)
    if at and valid_owner(at.group("name")):
        return at.group("name").strip()
    return None


def _clean_task(text: str, owner: str | None, due: str | None) -> str:
    task = text.strip()
    if owner:
        task = re.sub(rf"^{re.escape(owner)}\s*(?::|\u2014|-)\s+", "", task, count=1)
        task = re.sub(
            rf"^{re.escape(owner)}\s+(?:will|shall|should|must|needs to|need to|to)\s+",
            "",
            task,
            count=1,
            flags=re.IGNORECASE,
        )
        task = re.sub(
            rf"\bowner\s*[:\-]\s*{re.escape(owner)}\b\.?",
            "",
            task,
            count=1,
            flags=re.IGNORECASE,
        )
    task = re.sub(
        r"\b(?:due|deadline)\s*[:\-]\s*\S+(?:\s+\S+){0,4}",
        "",
        task,
        flags=re.IGNORECASE,
    )
    if due:
        task = re.sub(
            rf"\b(?:due|by|before|deadline)\s+{re.escape(due)}\b",
            "",
            task,
            count=1,
            flags=re.IGNORECASE,
        )
    task = _NO_OWNER_CLAUSE.sub("", task)
    task = re.sub(r"\s{2,}", " ", task)
    task = task.strip(" \t-—:.")
    return task


def _parse_decision(body: str, evidence: str) -> Decision | None:
    match = _DECISION.match(body)
    if match is None or _NOT_DECIDED.search(body):
        return None
    text = (match.group("labeled") or match.group("agreed") or "").strip()
    text = re.sub(r"^to\s+", "", text, count=1, flags=re.IGNORECASE).rstrip(".")
    if len(normalize_ws(text)) < 8:
        return None
    return Decision(text=_sentence_case(text), evidence=evidence.strip())


def _parse_question(body: str, evidence: str) -> OpenQuestion | None:
    prefixed = _QUESTION_PREFIX.match(body)
    if prefixed:
        text = prefixed.group("text").strip()
    elif body.endswith("?"):
        text = body.strip()
    else:
        return None
    text = text.strip().strip('"').strip()
    if not text.endswith("?"):
        text = text.rstrip(".") + "?"
    if len(normalize_ws(text)) < 8:
        return None
    return OpenQuestion(text=_sentence_case(text), evidence=evidence.strip())


def _without_bullet(stripped: str) -> str:
    return _BULLET.sub("", stripped, count=1)


def _append_evidence(evidence: str, line: str) -> str:
    if line in evidence:
        return evidence
    return f"{evidence}\n{line}"


def _sentence_case(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return stripped
    return stripped[0].upper() + stripped[1:]


def _dedupe(items: list, key) -> list:  # type: ignore[no-untyped-def]
    seen: set[str] = set()
    kept: list = []
    for item in items:
        marker = normalize_ws(key(item))
        if not marker or marker in seen:
            continue
        seen.add(marker)
        kept.append(item)
    return kept
