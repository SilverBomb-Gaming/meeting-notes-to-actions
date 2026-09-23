"""Ollama is the default. The OpenAI-compatible path is opt-in and mocked."""

from __future__ import annotations

import json

import httpx
import pytest

from meeting_actions.errors import LLMError
from meeting_actions.llm import OpenAICompatibleClient, OllamaClient, build_client


def _clear_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "MEETING_ACTIONS_PROVIDER",
        "MEETING_ACTIONS_TIMEOUT",
        "OLLAMA_BASE_URL",
        "OLLAMA_MODEL",
        "OLLAMA_NUM_CTX",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)


def test_default_client_is_local_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_provider_env(monkeypatch)
    client = build_client()
    assert isinstance(client, OllamaClient)
    assert client.base_url == "http://127.0.0.1:11434"
    assert client.model == "llama3.2"
    client.close()


def test_ollama_complete_posts_json_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "{\"actions\": []}"}})

    client = OllamaClient(
        base_url="http://127.0.0.1:11434",
        model="llama3.2",
        timeout=5,
        num_ctx=8192,
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    content = client.complete(system="system rules", user="notes")
    client.close()
    assert content == "{\"actions\": []}"
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["model"] == "llama3.2"
    assert body["format"] == "json"
    assert body["messages"][0] == {"role": "system", "content": "system rules"}


def test_openai_compatible_client_sends_bearer_token() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "{\"actions\": []}"}}]},
        )

    client = OpenAICompatibleClient(
        base_url="http://127.0.0.1:1234/v1",
        api_key="test-key",
        model="local-model",
        timeout=5,
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    content = client.complete(system="system rules", user="notes")
    client.close()
    assert content == "{\"actions\": []}"
    assert captured["url"] == "http://127.0.0.1:1234/v1/chat/completions"
    assert captured["auth"] == "Bearer test-key"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["response_format"] == {"type": "json_object"}
    assert body["model"] == "local-model"


def test_openai_provider_requires_a_key_for_api_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("MEETING_ACTIONS_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    with pytest.raises(LLMError, match="OPENAI_API_KEY"):
        build_client()


def test_provider_model_and_timeout_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("MEETING_ACTIONS_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    monkeypatch.setenv("OPENAI_MODEL", "from-env")
    client = build_client(model="from-flag")
    assert isinstance(client, OpenAICompatibleClient)
    assert client.model == "from-flag"
    client.close()

    monkeypatch.setenv("MEETING_ACTIONS_PROVIDER", "nope")
    with pytest.raises(LLMError, match="ollama' or 'openai"):
        build_client()

    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("MEETING_ACTIONS_TIMEOUT", "0")
    with pytest.raises(LLMError, match="MEETING_ACTIONS_TIMEOUT"):
        build_client()

    monkeypatch.setenv("MEETING_ACTIONS_TIMEOUT", "30")
    monkeypatch.setenv("OLLAMA_NUM_CTX", "100")
    with pytest.raises(LLMError, match="OLLAMA_NUM_CTX"):
        build_client()


def test_ollama_connection_errors_do_not_leak_a_traceback() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    client = OllamaClient(
        base_url="http://127.0.0.1:11434",
        model="llama3.2",
        timeout=1,
        num_ctx=8192,
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(LLMError, match="Could not reach Ollama"):
        client.complete(system="s", user="u")
    client.close()
