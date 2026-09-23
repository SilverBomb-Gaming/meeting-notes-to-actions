"""CLI paths that must work with no Ollama process."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from meeting_actions.cli import app
from meeting_actions.errors import LLMError

ROOT = Path(__file__).resolve().parents[1]
RUNNER = CliRunner()


def test_version() -> None:
    result = RUNNER.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "meeting-actions 0.1.0" in result.stdout


def test_no_llm_markdown_on_the_clear_sample() -> None:
    result = RUNNER.invoke(
        app,
        ["extract", "--notes", str(ROOT / "samples" / "sprint-planning.md"), "--no-llm"],
    )
    assert result.exit_code == 0, result.stderr
    assert "# Actions from sprint-planning.md" in result.stdout
    assert "- [ ] Ship the staging deploy — Alex Rivera — due 2026-03-14" in result.stdout
    assert "- [ ] Write the rollback note — Sam Okonkwo — due Friday" in result.stdout
    assert "- [ ] Update the on-call roster — Priya Shah — due 2026-03-18" in result.stdout
    assert "Keep the staging cluster on the current image" in result.stdout
    assert "Who covers the pager if Sam is out next Monday?" in result.stdout
    assert "Blake" not in result.stdout


def test_no_llm_json_on_the_messy_sample() -> None:
    result = RUNNER.invoke(
        app,
        ["extract", "--notes", str(ROOT / "samples" / "messy-retro.txt"), "--no-llm", "--format", "json"],
    )
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["source"] == "messy-retro.txt"
    assert payload["actions"][0]["owner"] is None
    assert payload["actions"][0]["due"] is None
    assert payload["actions"][1]["owner"] is None
    assert "Jordan" not in result.stdout
    assert "attendees" not in payload


def test_out_writes_the_same_text(tmp_path: Path) -> None:
    destination = tmp_path / "actions.md"
    result = RUNNER.invoke(
        app,
        [
            "extract",
            "--notes",
            str(ROOT / "samples" / "sprint-planning.md"),
            "--no-llm",
            "--out",
            str(destination),
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert destination.read_text(encoding="utf-8") == result.stdout
    assert f"Wrote {destination}." in result.stderr


def test_dry_run_prints_normalized_notes_and_does_not_call_a_model(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args, **kwargs):
        raise AssertionError("dry-run must not build a model client")

    monkeypatch.setattr("meeting_actions.cli.build_client", fail)
    result = RUNNER.invoke(
        app,
        ["extract", "--notes", str(ROOT / "samples" / "sprint-planning.md"), "--dry-run"],
    )
    assert result.exit_code == 0, result.stderr
    assert result.stdout.startswith("# Normalized notes: sprint-planning.md\n")
    assert "Alex Rivera will ship the staging deploy by 2026-03-14." in result.stdout
    assert "## Action items" not in result.stdout


def test_dry_run_and_no_llm_together_are_rejected() -> None:
    result = RUNNER.invoke(
        app,
        ["extract", "--notes", str(ROOT / "samples" / "messy-retro.txt"), "--dry-run", "--no-llm"],
    )
    assert result.exit_code == 1
    assert "--dry-run" in result.stderr
    assert "--no-llm" in result.stderr


def test_pdf_is_rejected_without_a_model() -> None:
    result = RUNNER.invoke(app, ["extract", "--notes", "notes.pdf", "--no-llm"])
    assert result.exit_code == 1
    assert "PDF, DOCX, and audio" in result.stderr


def test_bad_format_is_rejected() -> None:
    result = RUNNER.invoke(
        app,
        ["extract", "--notes", str(ROOT / "samples" / "messy-retro.txt"), "--no-llm", "--format", "html"],
    )
    assert result.exit_code == 1
    assert "--format must be markdown or json." in result.stderr


def test_default_path_uses_the_model_client_and_drops_inventions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    notes = tmp_path / "notes.md"
    notes.write_text("Alex will file the report by 2026-05-01.\n", encoding="utf-8")

    class Fake:
        def __init__(self) -> None:
            self.closed = False

        def complete(self, *, system: str, user: str) -> str:
            assert "Do not fabricate attendees, owners, deadlines, or decisions" in system
            assert "Alex will file the report by 2026-05-01." in user
            return json.dumps(
                {
                    "actions": [
                        {
                            "task": "File the report",
                            "owner": "Blake",
                            "due": "2026-05-01",
                            "evidence": "Alex will file the report by 2026-05-01.",
                        }
                    ]
                }
            )

        def close(self) -> None:
            self.closed = True

    fake = Fake()
    monkeypatch.setattr("meeting_actions.cli.build_client", lambda provider, model: fake)
    result = RUNNER.invoke(app, ["extract", "--notes", str(notes), "--format", "json"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["actions"][0]["task"] == "File the report"
    assert payload["actions"][0]["owner"] is None
    assert payload["actions"][0]["due"] == "2026-05-01"
    assert "Blake" not in result.stdout
    assert "Cleared owner" in result.stderr
    assert fake.closed


def test_openai_without_a_key_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEETING_ACTIONS_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = RUNNER.invoke(
        app,
        ["extract", "--notes", str(ROOT / "samples" / "sprint-planning.md")],
    )
    assert result.exit_code == 2
    assert "OPENAI_API_KEY" in result.stderr


def test_provider_failure_exits_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    notes = tmp_path / "notes.md"
    notes.write_text("TODO: file the report\n", encoding="utf-8")

    class Fake:
        def complete(self, *, system: str, user: str) -> str:
            raise LLMError("Could not reach Ollama at http://127.0.0.1:11434.")

        def close(self) -> None:
            return None

    monkeypatch.setattr("meeting_actions.cli.build_client", lambda provider, model: Fake())
    result = RUNNER.invoke(app, ["extract", "--notes", str(notes)])
    assert result.exit_code == 2
    assert "Could not reach Ollama" in result.stderr
