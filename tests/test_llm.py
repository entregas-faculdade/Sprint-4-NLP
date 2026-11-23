"""Unit tests for verified rewriting, retries, caching, and secret handling."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest
import requests

from src.pln.alertas import detectar_episodios, gerar_template
from src.pln.config import MODELO_REDATOR
from src.pln.llm import (
    OpenRouterClient,
    OpenRouterRequestError,
    redigir_alerta,
    redigir_alerta_com_fallback_api,
)
from src.pln.sensores import carregar_sensores


class FakeCompletionClient:
    def __init__(self, responses: list[str | Exception]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, list[dict[str, str]]]] = []

    def complete(self, model_id: str, messages: list[dict[str, str]]) -> str:
        self.calls.append((model_id, messages))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {"choices": [{"message": {"content": self.content}}]}


class FakeSession:
    def __init__(self, responses: list[FakeResponse | Exception]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _sample_alert():
    from datetime import datetime, timezone
    from src.pln.config import ACTIVE_ASSET_ID

    sensor = next(sensor for sensor in carregar_sensores().values() if sensor.grandeza.startswith("Temperatura do enrolamento"))
    readings = [
        {"id": f"llm-{index}", "asset_id": ACTIVE_ASSET_ID, "variable_id": sensor.variable_id,
         "value": 80 + index, "timestamp": datetime(2026, 6, 12, 10, index * 20, tzinfo=timezone.utc).isoformat()}
        for index in range(3)
    ]
    return detectar_episodios(readings, carregar_sensores())[0]


def test_unverified_number_returns_the_template() -> None:
    alert = _sample_alert()
    client = FakeCompletionClient([gerar_template(alert) + " Limite adicional de 100 °C."] * 2)
    text, result = redigir_alerta(alert, client)
    assert text == gerar_template(alert)
    assert result.origem_texto == "template"
    assert len(client.calls) == 2


def test_verified_rewrite_records_llm_origin() -> None:
    alert = _sample_alert()
    client = FakeCompletionClient([gerar_template(alert)])
    text, result = redigir_alerta(alert, client)
    assert text == gerar_template(alert)
    assert result.origem_texto == "llm"
    assert client.calls[0][0] == MODELO_REDATOR


def test_second_rewrite_includes_the_previous_violations() -> None:
    alert = _sample_alert()
    invented_response = gerar_template(alert) + " Limite adicional de 100 °C."
    client = FakeCompletionClient([invented_response, gerar_template(alert)])
    text, result = redigir_alerta(alert, client)
    retry_messages = client.calls[1][1]
    retry_context = "\n".join(message["content"] for message in retry_messages)
    assert text == gerar_template(alert)
    assert result.origem_texto == "llm"
    assert client.calls[0][1] != retry_messages
    assert "numero_nao_permitido" in retry_context
    assert "100" in retry_context


def test_api_failure_returns_the_template_and_reports_failure() -> None:
    alert = _sample_alert()
    client = FakeCompletionClient([OpenRouterRequestError("provider unavailable")])
    text, result, api_failed = redigir_alerta_com_fallback_api(alert, client)
    assert text == gerar_template(alert)
    assert result.origem_texto == "template"
    assert api_failed is True


def test_cache_avoids_the_second_request(tmp_path: Path) -> None:
    session = FakeSession([FakeResponse("Resposta fiel")])
    client = OpenRouterClient("cache-secret", session, tmp_path / "cache.jsonl")
    messages = [{"role": "user", "content": "Reescreva"}]
    assert client.complete(MODELO_REDATOR, messages) == "Resposta fiel"
    assert client.complete(MODELO_REDATOR, messages) == "Resposta fiel"
    assert len(session.calls) == 1
    assert session.calls[0]["json"]["temperature"] == 0


def test_retries_keep_the_same_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    session = FakeSession([requests.Timeout("temporário"), FakeResponse("Resposta fiel")])
    monkeypatch.setattr("src.pln.llm.time.sleep", lambda _: None)
    client = OpenRouterClient("retry-secret", session, tmp_path / "cache.jsonl")
    client.complete(MODELO_REDATOR, [{"role": "user", "content": "Reescreva"}])
    assert len(session.calls) == 2
    assert all(call["json"]["model"] == MODELO_REDATOR for call in session.calls)


def test_api_key_is_not_logged_or_written_to_cache(
    caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    test_value = "private-test-key"
    session = FakeSession([requests.Timeout("timeout") for _ in range(3)])
    client = OpenRouterClient(test_value, session, tmp_path / "cache.jsonl")
    with caplog.at_level(logging.DEBUG), pytest.raises(RuntimeError):
        client.complete(MODELO_REDATOR, [{"role": "user", "content": "Reescreva"}])
    output = capsys.readouterr()
    cache_text = (tmp_path / "cache.jsonl").read_text(encoding="utf-8") if (tmp_path / "cache.jsonl").exists() else ""
    assert test_value not in caplog.text
    assert test_value not in output.out + output.err
    assert test_value not in cache_text
