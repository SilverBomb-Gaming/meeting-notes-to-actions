"""Action items, decisions, and open questions extracted from notes."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

_EMPTY_MARKERS = {
    "",
    "null",
    "none",
    "n/a",
    "na",
    "unassigned",
    "tbd",
    "unknown",
    "no due date",
    "no owner",
    "unspecified",
}


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        raise ValueError("expected a string or null.")
    text = str(value).strip()
    if text.casefold() in _EMPTY_MARKERS:
        return None
    return text


class ActionItem(BaseModel):
    """One task grounded in the notes. A missing owner or due date stays null."""

    model_config = ConfigDict(extra="forbid")

    task: str = Field(min_length=1)
    owner: str | None = None
    due: str | None = None
    evidence: str = Field(min_length=1)

    @field_validator("task", "evidence", mode="before")
    @classmethod
    def _strip_required(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("owner", "due", mode="before")
    @classmethod
    def _strip_optional(cls, value: object) -> str | None:
        return _optional_text(value)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    evidence: str = Field(min_length=1)

    @field_validator("text", "evidence", mode="before")
    @classmethod
    def _strip(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()


class OpenQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    evidence: str = Field(min_length=1)

    @field_validator("text", "evidence", mode="before")
    @classmethod
    def _strip(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()


class MeetingExtraction(BaseModel):
    """The document this program renders. The model does not choose the file name."""

    model_config = ConfigDict(extra="forbid")

    source: str
    actions: list[ActionItem] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)


class LLMAction(BaseModel):
    """One action object from the model. Extra keys, including attendees, are ignored."""

    model_config = ConfigDict(extra="ignore")

    task: str = ""
    owner: str | None = None
    due: str | None = None
    evidence: str = ""

    @field_validator("task", "evidence", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("owner", "due", mode="before")
    @classmethod
    def _strip_optional(cls, value: object) -> str | None:
        return _optional_text(value)


class LLMDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str = ""
    evidence: str = ""

    @field_validator("text", "evidence", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()


class LLMQuestion(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str = ""
    evidence: str = ""

    @field_validator("text", "evidence", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()


class LLMExtraction(BaseModel):
    """JSON object requested from the model. Unknown keys are ignored."""

    model_config = ConfigDict(extra="ignore")

    actions: list[LLMAction] = Field(default_factory=list)
    decisions: list[LLMDecision] = Field(default_factory=list)
    open_questions: list[LLMQuestion] = Field(default_factory=list)

    @field_validator("actions", "decisions", "open_questions", mode="before")
    @classmethod
    def _coerce_list(cls, value: object) -> list[object]:
        if value is None:
            return []
        if isinstance(value, dict):
            return [value]
        if not isinstance(value, list):
            raise ValueError("expected a list.")
        return value
