"""A local .env fills in missing variables and does not override the environment."""

from __future__ import annotations

import os
from pathlib import Path

from meeting_actions.dotenv import load_dotenv


def test_existing_environment_wins(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OLLAMA_MODEL=from-file\n", encoding="utf-8")
    monkeypatch.setenv("OLLAMA_MODEL", "from-env")
    load_dotenv(env_file)
    assert os.environ["OLLAMA_MODEL"] == "from-env"


def test_fills_missing_values_and_strips_quotes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("MEETING_ACTIONS_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n\nMEETING_ACTIONS_PROVIDER=openai\nOPENAI_MODEL=\"gpt-4o-mini\"\n",
        encoding="utf-8",
    )
    load_dotenv(env_file)
    assert os.environ["MEETING_ACTIONS_PROVIDER"] == "openai"
    assert os.environ["OPENAI_MODEL"] == "gpt-4o-mini"
