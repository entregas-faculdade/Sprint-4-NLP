"""Unit tests for verified rewriting, retries, caching, and secret handling."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import pytest
import requests

from src.pln.alertas import (
    detectar_episodios,
    gerar_template,
    verificar_clareza,
    verificar_texto,
)
from src.pln.config import (
    ALERT_TESTS_FILE,
    MAX_PALAVRAS_ALERTA,
    MODELO_REDATOR,
)
from src.pln.llm import (
    OpenRouterClient,
    OpenRouterRequestError,
    redigir_alerta,
    redigir_alerta_com_fallback_api,
    redigir_alerta_detalhado,
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


def test_faithful_rewrite_over_the_clarity_limit_falls_back() -> None:
    alert = _sample_alert()
    template = gerar_template(alert)
    long_candidate = template.replace(
        "entre ", "durante o período, no intervalo do episódio, entre ", 1
    )
    assert len(re.findall(r"\w+", long_candidate, flags=re.UNICODE)) > MAX_PALAVRAS_ALERTA
    assert verificar_texto(long_candidate, alert) == []
    assert not verificar_clareza(long_candidate, alert)
    client = FakeCompletionClient([long_candidate, long_candidate])

    result = redigir_alerta_detalhado(alert, client)

    assert result.origem_texto == "template"
    assert result.texto == template
    assert len(client.calls) == 2
    assert len(result.rascunhos_rejeitados) == 2
    assert all(
        any(violation.codigo == "clareza_reprovada" for violation in draft.violacoes)
        for draft in result.rascunhos_rejeitados
    )
    assert "clareza_reprovada" in "\n".join(message["content"] for message in client.calls[1][1])


def test_rejected_draft_and_violations_are_returned_without_an_extra_call() -> None:
    alert = _sample_alert()
    rejected_candidate = gerar_template(alert) + " Verifique também os rolamentos e a lubrificação."
    client = FakeCompletionClient([rejected_candidate, gerar_template(alert)])

    result = redigir_alerta_detalhado(alert, client)

    assert result.origem_texto == "llm"
    assert result.rascunhos_rejeitados[0].texto == rejected_candidate
    assert any(
        violation.codigo == "conteudo_nao_sustentado"
        for violation in result.rascunhos_rejeitados[0].violacoes
    )
    assert len(client.calls) == 2


def test_all_nine_reference_rewrites_return_clear_llm_text() -> None:
    cases = json.loads(ALERT_TESTS_FILE.read_text(encoding="utf-8"))["casos"]
    valid_cases = [case for case in cases if not case["descartar"]]
    assert len(valid_cases) == 9

    for case in valid_cases:
        alert = detectar_episodios(case["leituras"], carregar_sensores())[0]
        text, result = redigir_alerta(alert, FakeCompletionClient([gerar_template(alert)]))
        assert result.origem_texto == "llm", case["caso"]
        assert verificar_clareza(text, alert), case["caso"]


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
