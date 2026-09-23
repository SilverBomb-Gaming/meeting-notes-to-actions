"""Expected failures. The CLI prints these without a traceback."""


class MeetingActionsError(Exception):
    """Base class for errors the user can act on."""


class UsageError(MeetingActionsError):
    """The command line or the notes file is not usable."""


class LLMError(MeetingActionsError):
    """The model provider could not complete a request."""
