"""Turn loaded notes into a grounded extraction.

The model path asks for JSON, then the guard drops anything the notes do not
support. Unusable model output falls back to the heuristic. A provider failure
is not swallowed: that still raises LLMError.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from meeting_actions.errors import LLMError
from meeting_actions.guard import apply_guard
from meeting_actions.heuristic import extract_heuristic
from meeting_actions.llm import LLMClient
from meeting_actions.models import ActionItem, Decision, LLMExtraction, MeetingExtraction, OpenQuestion
from meeting_actions.notes import LoadedNotes
from meeting_actions.prompts import SYSTEM_PROMPT, build_user_prompt

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


@dataclass
class ExtractionResult:
    document: MeetingExtraction
    warnings: list[str]


def extract_notes(
    notes: LoadedNotes,
    *,
    client: LLMClient | None,
    use_llm: bool,
) -> ExtractionResult:
    """Extract with the model, or with the heuristic when ``use_llm`` is false."""
    if not use_llm:
        document, warnings = apply_guard(extract_heuristic(notes), notes.text)
        return ExtractionResult(document=document, warnings=warnings)
    if client is None:
        raise LLMError("No model client was configured.")

    raw = client.complete(system=SYSTEM_PROMPT, user=build_user_prompt(notes))
    try:
        parsed = parse_llm_output(raw)
    except ValueError:
        document, warnings = apply_guard(extract_heuristic(notes), notes.text)
        warnings.insert(0, "Model output was not usable JSON. Fell back to heuristic extraction.")
        return ExtractionResult(document=document, warnings=warnings)

    drafted = _from_llm(parsed, notes.source)
    document, warnings = apply_guard(drafted, notes.text)
    if _is_empty(document):
        fallback, fallback_warnings = apply_guard(extract_heuristic(notes), notes.text)
        if not _is_empty(fallback):
            if _model_offered_items(parsed):
                reason = "No grounded items remained after checks. Fell back to heuristic extraction."
            else:
                reason = "Model returned no items. Fell back to heuristic extraction."
            warnings.append(reason)
            warnings.extend(fallback_warnings)
            return ExtractionResult(document=fallback, warnings=warnings)
    return ExtractionResult(document=document, warnings=warnings)


def parse_llm_output(raw: str) -> LLMExtraction:
    """Parse a JSON object, including one wrapped in a markdown fence."""
    text = raw.strip()
    if text.startswith("```"):
        text = _FENCE.sub("", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("Model output was not JSON.") from None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError("Model output was not JSON.") from exc
    if not isinstance(data, dict):
        raise ValueError("Model output was not a JSON object.")
    return LLMExtraction.model_validate(data)


def _from_llm(parsed: LLMExtraction, source: str) -> MeetingExtraction:
    actions: list[ActionItem] = []
    for action in parsed.actions:
        if not action.task or not action.evidence:
            continue
        try:
            actions.append(
                ActionItem(task=action.task, owner=action.owner, due=action.due, evidence=action.evidence)
            )
        except ValueError:
            continue
    decisions = [
        Decision(text=item.text, evidence=item.evidence) for item in parsed.decisions if item.text and item.evidence
    ]
    questions = [
        OpenQuestion(text=item.text, evidence=item.evidence)
        for item in parsed.open_questions
        if item.text and item.evidence
    ]
    return MeetingExtraction(
        source=source,
        actions=actions,
        decisions=decisions,
        open_questions=questions,
    )


def _model_offered_items(parsed: LLMExtraction) -> bool:
    return bool(parsed.actions or parsed.decisions or parsed.open_questions)


def _is_empty(document: MeetingExtraction) -> bool:
    return not document.actions and not document.decisions and not document.open_questions
