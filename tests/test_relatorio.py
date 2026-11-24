"""Tests for report periods, traceable claims, and factuality checks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from src.pln.config import ACTIVE_ASSET_ID, PERIODO_DIARIO, PERIODO_SEMANAL
from src.pln.relatorio import ReportEvaluationContext, avaliar_relatorio, gerar_relatorio, verificar_relatorio
from src.pln.sensores import carregar_sensores


@pytest.fixture
def report_inputs() -> tuple[Any, Any, Any]:
    sensor = next(item for item in carregar_sensores().values() if item.grandeza.startswith("Vibração no mancal"))
    start = datetime(2026, 8, 22, 5, 0, tzinfo=timezone.utc)
    readings = [
        _reading("reading-outside-window", sensor.variable_id, 78.29, datetime(2026, 8, 16, 8, 0, tzinfo=timezone.utc)),
        _reading("reading-1", sensor.variable_id, 4.6, start),
        _reading("reading-2", sensor.variable_id, 4.8, start + timedelta(minutes=10)),
        _reading("reading-3", sensor.variable_id, 4.7, start + timedelta(minutes=20)),
        _reading("reading-4", sensor.variable_id, 1.48, datetime(2026, 8, 23, 8, 0, tzinfo=timezone.utc)),
        _reading("reading-5", sensor.variable_id, 1.52, datetime(2026, 8, 23, 9, 0, tzinfo=timezone.utc)),
        _reading("reading-6", sensor.variable_id, 1.6, datetime(2026, 8, 23, 9, 46, tzinfo=timezone.utc)),
    ]
    alerts = [{
        "id": "A-0012",
        "ativo": "Teste (Sorocaba)",
        "sensor_id": sensor.variable_id,
        "grandeza": sensor.grandeza,
        "unidade": sensor.unidade,
        "severidade": "critico",
        "inicio": start,
        "fim": start + timedelta(minutes=20),
        "duracao_min": 20,
        "n_leituras": 3,
        "valor_max": 4.8,
        "valor_medio": 4.7,
        "limiar_nominal": 1.5,
        "limiar_alerta": 2.8,
        "limiar_critico": 4.5,
        "desvio_abs": 3.3,
        "desvio_pct": 220,
        "ids_leitura": ["reading-1", "reading-2", "reading-3"],
    }]
    return alerts, readings, sensor


def _reading(identifier: str, sensor_id: str, value: float, timestamp: datetime) -> dict[str, object]:
    return {
        "id": identifier,
        "asset_id": ACTIVE_ASSET_ID,
        "variable_id": sensor_id,
        "value": value,
        "timestamp": timestamp,
    }


def test_report_daily_uses_last_day_with_alert_and_weekly_keeps_last_data_day(report_inputs: Any) -> None:
    alerts, readings, sensor = report_inputs

    daily = gerar_relatorio(alerts, PERIODO_DIARIO, readings)
    weekly = gerar_relatorio(alerts, PERIODO_SEMANAL, readings)

    assert "[ref: A-0012 | ids: reading-1,reading-2,reading-3]" in daily
    assert f"{sensor.grandeza}: estável" in daily
    assert "[ref: A-0012 | ids: reading-1,reading-2,reading-3]" in weekly
    assert "Sensores em risco" in weekly
    assert "variação +0,08 mm/s (+5,4 %)" not in daily


def test_daily_report_requires_a_data_day_with_an_alert(report_inputs: Any) -> None:
    _, readings, _ = report_inputs

    with pytest.raises(ValueError, match="dia com leituras e alerta"):
        gerar_relatorio([], PERIODO_DIARIO, readings)


def test_deterministic_reports_pass_their_verifier(report_inputs: Any) -> None:
    alerts, readings, _ = report_inputs

    for period in (PERIODO_DIARIO, PERIODO_SEMANAL):
        report = gerar_relatorio(alerts, period, readings)

        assert verificar_relatorio(report, alerts, readings) == []


def test_report_rejects_a_sentence_without_a_reference(report_inputs: Any) -> None:
    alerts, readings, _ = report_inputs
    report = gerar_relatorio(alerts, PERIODO_SEMANAL, readings).replace("[ref: A-0012 | ids: reading-1,reading-2,reading-3]", "", 1)

    violations = verificar_relatorio(report, alerts, readings)

    assert any("Frase sem referência" in violation for violation in violations)


def test_report_rejects_an_unresolvable_reference(report_inputs: Any) -> None:
    alerts, readings, _ = report_inputs
    report = gerar_relatorio(alerts, PERIODO_SEMANAL, readings).replace("A-0012", "A-9999")

    violations = verificar_relatorio(report, alerts, readings)

    assert any("Referência não resolvida" in violation for violation in violations)


def test_report_rejects_an_invented_number(report_inputs: Any) -> None:
    alerts, readings, _ = report_inputs
    report = gerar_relatorio(alerts, PERIODO_DIARIO, readings).replace("no período [ref:", "no período 999999 [ref:", 1)

    violations = verificar_relatorio(report, alerts, readings)

    assert any("Número não permitido: 999999" == violation for violation in violations)


def test_report_rejects_raw_reading_value_in_aggregate_sentence(report_inputs: Any) -> None:
    alerts, readings, sensor = report_inputs
    report = gerar_relatorio(alerts, PERIODO_SEMANAL, readings)
    reference = f"[ref: período | sensor {sensor.variable_id}]"
    trend_line = next(line for line in report.splitlines() if "variação" in line and reference in line)
    injected_line = trend_line.replace(reference, f"com máxima de 78,29 °C {reference}", 1)
    injected = report.replace(trend_line, injected_line, 1)

    violations = verificar_relatorio(injected, alerts, readings)

    assert "Número não permitido: 78,29" in violations


def test_trend_lines_only_describe_numeric_variation_or_stability(report_inputs: Any) -> None:
    alerts, readings, _ = report_inputs
    report = gerar_relatorio(alerts, PERIODO_DIARIO, readings)
    trend_section = report.split("Tendências\n", maxsplit=1)[1].split("\n\nAções padrão", maxsplit=1)[0]

    assert "estável" in trend_section
    assert "porque" not in trend_section.casefold()
    assert "poderá" not in trend_section.casefold()
    assert verificar_relatorio(report, alerts, readings) == []

    weekly_report = gerar_relatorio(alerts, PERIODO_SEMANAL, readings)
    weekly_trends = weekly_report.split("Tendências\n", maxsplit=1)[1].split("\n\nAções padrão", maxsplit=1)[0]
    assert "variação -3,17 mm/s (-67,4 %)" in weekly_trends


def test_weekly_report_includes_risk_action_and_traceability_checklist(report_inputs: Any) -> None:
    alerts, readings, sensor = report_inputs
    report = gerar_relatorio(alerts, PERIODO_SEMANAL, readings)
    reference = "Resumo\nUm alerta crítico de vibração apareceu na semana."

    context = ReportEvaluationContext(alerts, readings, PERIODO_SEMANAL)
    result = avaliar_relatorio(report, reference, context)

    assert "não é diagnóstico" in report
    assert sensor.acoes_padrao["critico"] in report
    assert result["checklist"] == {
        "precisao": True,
        "clareza": True,
        "utilidade": True,
        "rastreabilidade": True,
    }
    assert result["frases_rastreaveis_pct"] == pytest.approx(100)
    assert set(result["rouge"]) == {"rouge1", "rouge2", "rougeL"}


@pytest.mark.parametrize(
    ("severity", "feminine_adjective"),
    (("leve", "leve"), ("moderado", "moderada"), ("critico", "crítica")),
)
def test_alert_severity_agrees_with_feminine_noun(
    report_inputs: Any,
    severity: str,
    feminine_adjective: str,
) -> None:
    alerts, readings, _ = report_inputs
    alerts[0]["severidade"] = severity

    report = gerar_relatorio(alerts, PERIODO_DIARIO, readings)

    assert f"Alerta de severidade {feminine_adjective}" in report


@pytest.mark.parametrize(
    ("severity", "feminine_adjective"),
    (("moderado", "moderada"), ("critico", "crítica")),
)
def test_risk_severity_agrees_with_feminine_noun(
    report_inputs: Any,
    severity: str,
    feminine_adjective: str,
) -> None:
    alerts, readings, _ = report_inputs
    alerts[0]["severidade"] = severity

    report = gerar_relatorio(alerts, PERIODO_SEMANAL, readings)

    assert f"severidade {feminine_adjective}; severidade geral do ativo {feminine_adjective}" in report
