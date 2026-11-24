"""Build deterministic operational reports with resolvable alert and reading references."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from statistics import mean
from typing import Any, Mapping, Sequence

from rouge_score.rouge_scorer import RougeScorer

from src.pln.alertas import Alerta
from src.pln.config import (
    CLASSES_SEVERIDADE_RELATORIO,
    DIAS_PERIODO_SEMANAL,
    LIMIAR_TENDENCIA_PCT,
    MAX_ALERTAS_RELATORIO,
    MAX_PALAVRAS_RELATORIO,
    PERIODO_DIARIO,
    PERIODO_SEMANAL,
    PRECISAO_RELATORIO,
    PRECISAO_TENDENCIA_PCT,
    SECOES_RELATORIO,
    SEVERIDADE_ADJETIVO_FEMININO,
    SEVERIDADE_EXIBICAO,
    TERMOS_PROIBIDOS,
)
from src.pln.sensores import Sensor, carregar_sensores

ReportAlert = Alerta | Mapping[str, Any]
REPORT_NUMBER_PATTERN = re.compile(r"(?<![\w-])[+-]?\d+(?:[.,]\d+)*(?!\w)", re.UNICODE)
REFERENCE_PATTERN = re.compile(
    r"\[ref: (?:(?P<alert>A-\d{4}) \| ids: (?P<ids>[\w,-]+)|período \| sensor (?P<sensor>[\w-]+))\]$"
)
SEVERITY_PRIORITY = {"leve": 1, "moderado": 2, "critico": 3}
SEVERITY_PLURALS = {"leve": "leves", "moderado": "moderados", "critico": "críticos"}


@dataclass(frozen=True)
class ReportEvaluationContext:
    alertas: Sequence[ReportAlert]
    leituras: Sequence[Mapping[str, Any]]
    periodo: str


def gerar_relatorio(
    alertas: Sequence[ReportAlert], periodo: str, leituras: Sequence[Mapping[str, Any]]
) -> str:
    """Render the five fixed sections for the latest daily or weekly data window."""
    if periodo not in (PERIODO_DIARIO, PERIODO_SEMANAL):
        raise ValueError("O período precisa ser diario ou semanal.")
    if not leituras:
        raise ValueError("O relatório precisa de ao menos uma leitura para definir o período.")
    period_start, period_end = _period_window(periodo, leituras, alertas)
    period_readings = _filter_readings(leituras, period_start, period_end)
    period_alerts = _filter_alerts(alertas, period_start, period_end)
    sensors = carregar_sensores()
    risk_alerts = _risk_alerts(period_alerts)
    sections = (
        ("Resumo", _summary_lines(period_alerts, period_readings, sensors)),
        ("Alertas emitidos", _alert_lines(period_alerts, period_readings, sensors)),
        ("Sensores em risco", _risk_lines(risk_alerts, period_readings, sensors)),
        ("Tendências", _trend_lines(period_readings, sensors)),
        ("Ações padrão (ação padrão; não é diagnóstico)", _action_lines(risk_alerts, period_readings, sensors)),
    )
    return "\n\n".join(f"{heading}\n" + "\n".join(lines) for heading, lines in sections)


def _period_window(
    period: str,
    readings: Sequence[Mapping[str, Any]],
    alerts: Sequence[ReportAlert],
) -> tuple[datetime, datetime]:
    reading_dates = {_reading_timestamp(reading).date() for reading in readings}
    latest_date = max(reading_dates)
    if period == PERIODO_DIARIO:
        alert_dates = {
            _as_datetime(_field(alert, "inicio")).date()
            for alert in alerts
            if _as_datetime(_field(alert, "inicio")).date() in reading_dates
        }
        if not alert_dates:
            raise ValueError("Não há dia com leituras e alerta para o relatório diário.")
        latest_date = max(alert_dates)
    days = 1 if period == PERIODO_DIARIO else DIAS_PERIODO_SEMANAL
    start_date = latest_date - timedelta(days=days - 1)
    start = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end = datetime.combine(latest_date, time.max, tzinfo=timezone.utc)
    return start, end


def _field(record: ReportAlert | Mapping[str, Any], name: str) -> Any:
    if isinstance(record, Mapping):
        return record[name]
    return getattr(record, name)


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _reading_timestamp(reading: Mapping[str, Any]) -> datetime:
    return _as_datetime(reading["timestamp"])


def _filter_readings(
    readings: Sequence[Mapping[str, Any]], start: datetime, end: datetime
) -> list[Mapping[str, Any]]:
    return [reading for reading in readings if start <= _reading_timestamp(reading) <= end]


def _filter_alerts(
    alerts: Sequence[ReportAlert], start: datetime, end: datetime
) -> list[ReportAlert]:
    return [alert for alert in alerts if start <= _as_datetime(_field(alert, "inicio")) <= end]


def _sensor_reading_groups(
    readings: Sequence[Mapping[str, Any]],
) -> dict[str, list[Mapping[str, Any]]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for reading in readings:
        groups[str(reading["variable_id"])].append(reading)
    return dict(groups)


def _sensor_alert_groups(alerts: Sequence[ReportAlert]) -> dict[str, list[ReportAlert]]:
    groups: dict[str, list[ReportAlert]] = defaultdict(list)
    for alert in alerts:
        groups[str(_field(alert, "sensor_id"))].append(alert)
    return dict(groups)


def _severity_counts(alerts: Sequence[ReportAlert], sensor_id: str) -> Counter[str]:
    return Counter(
        str(_field(alert, "severidade"))
        for alert in alerts
        if str(_field(alert, "sensor_id")) == sensor_id
    )


def _summary_lines(
    alerts: Sequence[ReportAlert], readings: Sequence[Mapping[str, Any]], sensors: Mapping[str, Sensor]
) -> list[str]:
    lines = []
    for sensor_id in sorted(_sensor_reading_groups(readings)):
        counts = _severity_counts(alerts, sensor_id)
        sensor = sensors[sensor_id]
        counts_text = ", ".join(_format_severity_count(counts, severity) for severity in CLASSES_SEVERIDADE_RELATORIO)
        lines.append(f"{sensor.grandeza}: {counts_text} no período {_aggregate_reference(sensor_id)}")
    return lines


def _format_severity_count(counts: Counter[str], severity: str) -> str:
    count = counts[severity]
    label = SEVERIDADE_EXIBICAO[severity]
    plural = SEVERITY_PLURALS[severity] if count != 1 else label
    return f"{count} {plural}"


def _alert_lines(
    alerts: Sequence[ReportAlert], readings: Sequence[Mapping[str, Any]], sensors: Mapping[str, Sensor]
) -> list[str]:
    if not alerts:
        return [
            f"Nenhum alerta foi emitido para {sensors[sensor_id].grandeza} no período {_aggregate_reference(sensor_id)}"
            for sensor_id in sorted(_sensor_reading_groups(readings))
        ]
    ranked = sorted(alerts, key=lambda alert: (-SEVERITY_PRIORITY[str(_field(alert, "severidade"))], _as_datetime(_field(alert, "inicio")), str(_field(alert, "id"))))
    return [_render_alert_sentence(alert, sensors) for alert in ranked[:MAX_ALERTAS_RELATORIO]]


def _render_alert_sentence(alert: ReportAlert, sensors: Mapping[str, Sensor]) -> str:
    alert_id = str(_field(alert, "id"))
    sensor_id = str(_field(alert, "sensor_id"))
    severity = str(_field(alert, "severidade"))
    peak = _format_number(float(_field(alert, "valor_max")))
    unit = str(_field(alert, "unidade"))
    readings = ",".join(str(item) for item in _field(alert, "ids_leitura"))
    return (
        f"Alerta de severidade {SEVERIDADE_ADJETIVO_FEMININO[severity]} para {sensors[sensor_id].grandeza}: pico {peak} {unit} "
        f"{_alert_reference(alert_id, readings)}"
    )


def _risk_alerts(alerts: Sequence[ReportAlert]) -> dict[str, ReportAlert]:
    risks: dict[str, ReportAlert] = {}
    for alert in alerts:
        severity = str(_field(alert, "severidade"))
        if SEVERITY_PRIORITY[severity] < SEVERITY_PRIORITY["moderado"]:
            continue
        sensor_id = str(_field(alert, "sensor_id"))
        current = risks.get(sensor_id)
        if current is None or SEVERITY_PRIORITY[severity] > SEVERITY_PRIORITY[str(_field(current, "severidade"))]:
            risks[sensor_id] = alert
    return risks


def _risk_lines(
    risks: Mapping[str, ReportAlert],
    readings: Sequence[Mapping[str, Any]],
    sensors: Mapping[str, Sensor],
) -> list[str]:
    sensor_ids = sorted(_sensor_reading_groups(readings))
    if not risks:
        return [f"Sem alerta moderado ou crítico para {sensors[sensor_id].grandeza} no período {_aggregate_reference(sensor_id)}" for sensor_id in sensor_ids]
    overall = max((str(_field(alert, "severidade")) for alert in risks.values()), key=SEVERITY_PRIORITY.get)
    return [
        f"{sensors[sensor_id].grandeza} em risco, severidade {SEVERIDADE_ADJETIVO_FEMININO[str(_field(alert, 'severidade'))]}; severidade geral do ativo {SEVERIDADE_ADJETIVO_FEMININO[overall]} {_aggregate_reference(sensor_id)}"
        for sensor_id, alert in sorted(risks.items())
    ]


def _trend_lines(
    readings: Sequence[Mapping[str, Any]],
    sensors: Mapping[str, Sensor],
) -> list[str]:
    groups = _sensor_reading_groups(readings)
    lines = []
    for sensor_id, sensor_readings in sorted(groups.items()):
        trend = _trend_values(sensor_readings)
        if trend is None:
            continue
        difference, percentage = trend
        if abs(percentage) < LIMIAR_TENDENCIA_PCT:
            description = "estável"
        else:
            description = f"variação {_signed_number(difference)} {sensor_readings[0].get('unit', sensors[sensor_id].unidade)} ({_format_percentage(percentage)} %)"
        lines.append(f"{sensors[sensor_id].grandeza}: {description} {_aggregate_reference(sensor_id)}")
    return lines or _no_trend_line(readings, sensors)


def _trend_values(readings: Sequence[Mapping[str, Any]]) -> tuple[float, float] | None:
    ordered = sorted(readings, key=_reading_timestamp)
    midpoint = len(ordered) // 2
    if midpoint == 0 or midpoint == len(ordered):
        return None
    first_values = [float(reading["value"]) for reading in ordered[:midpoint]]
    second_values = [float(reading["value"]) for reading in ordered[midpoint:]]
    first_average = mean(first_values)
    difference = mean(second_values) - first_average
    if first_average == 0:
        return (difference, 0.0) if difference == 0 else None
    return difference, difference / abs(first_average) * 100


def _no_trend_line(
    readings: Sequence[Mapping[str, Any]], sensors: Mapping[str, Sensor]
) -> list[str]:
    sensor_ids = sorted(_sensor_reading_groups(readings))
    return [
        f"Sem duas metades de leituras para comparar em {sensors[sensor_id].grandeza} {_aggregate_reference(sensor_id)}"
        for sensor_id in sensor_ids
    ]


def _action_lines(
    risks: Mapping[str, ReportAlert],
    readings: Sequence[Mapping[str, Any]],
    sensors: Mapping[str, Sensor],
) -> list[str]:
    if not risks:
        return [f"Ação padrão não indicada para {sensors[sensor_id].grandeza} no período {_aggregate_reference(sensor_id)}" for sensor_id in sorted(_sensor_reading_groups(readings))]
    return [
        f"{sensors[sensor_id].grandeza}: {sensors[sensor_id].acoes_padrao[str(_field(alert, 'severidade'))]} {_alert_reference(str(_field(alert, 'id')), ','.join(str(item) for item in _field(alert, 'ids_leitura')))}"
        for sensor_id, alert in sorted(risks.items())
    ]


def _aggregate_reference(sensor_id: str) -> str:
    return f"[ref: período | sensor {sensor_id}]"


def _alert_reference(alert_id: str, reading_ids: str) -> str:
    return f"[ref: {alert_id} | ids: {reading_ids}]"


def _format_number(value: float) -> str:
    return f"{value:,.{PRECISAO_RELATORIO}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _signed_number(value: float) -> str:
    formatted = _format_number(value)
    return f"+{formatted}" if value >= 0 else formatted


def _format_percentage(value: float) -> str:
    formatted = f"{value:.{PRECISAO_TENDENCIA_PCT}f}".replace(".", ",")
    return f"+{formatted}" if value >= 0 else formatted


def _sentence_lines(text: str) -> list[str]:
    headings = tuple(section.casefold() for section in SECOES_RELATORIO)
    return [line.strip() for line in text.splitlines() if line.strip() and not line.strip().casefold().startswith(headings)]


def verificar_relatorio(
    texto: str, alertas: Sequence[ReportAlert], leituras: Sequence[Mapping[str, Any]]
) -> list[str]:
    """Reject unreferenced sentences, unresolved citations, invented numbers, and banned claims."""
    if not isinstance(texto, str) or not texto.strip():
        return ["O relatório está vazio."]
    violations = _required_sections_violations(texto)
    alerts_by_id = {str(_field(alert, "id")): alert for alert in alertas}
    reading_by_id = {str(reading["id"]): reading for reading in leituras}
    for sentence in _sentence_lines(texto):
        reference = REFERENCE_PATTERN.search(sentence)
        if reference is None:
            violations.append(f"Frase sem referência resolvível: {sentence}")
            continue
        cited_numbers = _resolve_reference(reference, alerts_by_id, reading_by_id, leituras)
        if cited_numbers is None:
            violations.append(f"Referência não resolvida: {reference.group(0)}")
            continue
        body = sentence[: reference.start()]
        violations.extend(_sentence_violations(body, cited_numbers))
    return violations


def _required_sections_violations(text: str) -> list[str]:
    missing = [section for section in SECOES_RELATORIO if not re.search(rf"(?im)^{re.escape(section)}\b", text)]
    return [f"Seção ausente: {section}" for section in missing]


def _resolve_reference(
    reference: re.Match[str],
    alerts_by_id: Mapping[str, ReportAlert],
    readings_by_id: Mapping[str, Mapping[str, Any]],
    readings: Sequence[Mapping[str, Any]],
) -> set[str] | None:
    alert_id = reference.group("alert")
    if alert_id:
        alert = alerts_by_id.get(alert_id)
        if alert is None:
            return None
        reading_ids = reference.group("ids").split(",")
        if not reading_ids or any(identifier not in readings_by_id for identifier in reading_ids):
            return None
        if not set(reading_ids).issubset(set(str(item) for item in _field(alert, "ids_leitura"))):
            return None
        return _alert_number_tokens(alert)
    sensor_id = reference.group("sensor")
    if not any(str(reading.get("variable_id")) == sensor_id for reading in readings):
        return None
    return _aggregate_number_tokens(sensor_id, list(alerts_by_id.values()), readings)


def _sentence_violations(body: str, allowed_numbers: set[str]) -> list[str]:
    violations = []
    normalized = body.casefold()
    for term in TERMOS_PROIBIDOS:
        if re.search(rf"\b{re.escape(term)}\b", normalized):
            violations.append(f"Termo proibido: {term}")
    invented = [number for number in REPORT_NUMBER_PATTERN.findall(body) if number not in allowed_numbers]
    violations.extend(f"Número não permitido: {number}" for number in invented)
    return violations


def _alert_number_tokens(alert: ReportAlert) -> set[str]:
    fields = ("duracao_min", "n_leituras", "valor_max", "valor_medio", "limiar_nominal", "limiar_alerta", "limiar_critico", "desvio_abs", "desvio_pct")
    values = [float(_field(alert, field)) for field in fields]
    return _formatted_number_tokens(values)


def _aggregate_number_tokens(
    sensor_id: str,
    alerts: Sequence[ReportAlert],
    readings: Sequence[Mapping[str, Any]],
) -> set[str]:
    sensor_readings = [reading for reading in readings if str(reading.get("variable_id")) == sensor_id]
    sensor_alerts = [alert for alert in alerts if str(_field(alert, "sensor_id")) == sensor_id]
    allowed: set[str] = set()
    for period in (PERIODO_DIARIO, PERIODO_SEMANAL):
        start, end = _period_window(period, readings, alerts)
        period_readings = _filter_readings(sensor_readings, start, end)
        period_alerts = _filter_alerts(sensor_alerts, start, end)
        counts = Counter(str(_field(alert, "severidade")) for alert in period_alerts)
        allowed.update(str(counts[severity]) for severity in CLASSES_SEVERIDADE_RELATORIO)
        trend = _trend_values(period_readings)
        if trend:
            allowed.update(REPORT_NUMBER_PATTERN.findall(_signed_number(trend[0])))
            allowed.update(REPORT_NUMBER_PATTERN.findall(_format_percentage(trend[1])))
    return allowed


def _formatted_number_tokens(values: Sequence[float]) -> set[str]:
    return {token for value in values for token in REPORT_NUMBER_PATTERN.findall(_format_number(value))}


def avaliar_relatorio(
    texto: str,
    referencia: str,
    contexto: ReportEvaluationContext,
) -> dict[str, Any]:
    """Return ROUGE-1/2/L and the precision, clarity, utility, and traceability checks."""
    alertas = contexto.alertas
    leituras = contexto.leituras
    violations = verificar_relatorio(texto, alertas, leituras)
    sentences = _sentence_lines(texto)
    traceability_rate = _traceability_rate(texto, sentences, alertas, leituras)
    return {
        "rouge": _rouge_scores(referencia, texto),
        "checklist": {
            "precisao": not violations,
            "clareza": _clear_report(texto, sentences),
            "utilidade": _risk_actions_present(alertas, texto, leituras, contexto.periodo),
            "rastreabilidade": traceability_rate == 1.0,
        },
        "violacoes": violations,
        "frases_rastreaveis_pct": traceability_rate * 100,
    }


def _rouge_scores(reference: str, generated: str) -> dict[str, float]:
    scorer = RougeScorer(("rouge1", "rouge2", "rougeL"), tokenizer=AccentPreservingTokenizer())
    scores = scorer.score(reference, generated)
    return {metric: scores[metric].fmeasure for metric in ("rouge1", "rouge2", "rougeL")}


class AccentPreservingTokenizer:
    """Tokenize report text with the same accent-preserving rule used by the notebook."""

    def tokenize(self, text: str) -> list[str]:
        return re.findall(r"\w+", text.lower(), flags=re.UNICODE)


def _clear_report(text: str, sentences: Sequence[str]) -> bool:
    headings_present = all(re.search(rf"(?im)^{re.escape(section)}\b", text) for section in SECOES_RELATORIO)
    return headings_present and bool(sentences) and all(
        len(re.findall(r"\w+", REFERENCE_PATTERN.sub("", line), flags=re.UNICODE)) <= MAX_PALAVRAS_RELATORIO
        for line in sentences
    )


def _risk_actions_present(
    alerts: Sequence[ReportAlert],
    text: str,
    readings: Sequence[Mapping[str, Any]],
    period: str,
) -> bool:
    sensors = carregar_sensores()
    start, end = _period_window(period, readings, alerts)
    risk_alerts = _risk_alerts(_filter_alerts(alerts, start, end))
    return all(
        sensors[sensor_id].acoes_padrao[str(_field(alert, "severidade"))] in text
        for sensor_id, alert in risk_alerts.items()
    )


def _traceability_rate(
    text: str,
    sentences: Sequence[str],
    alerts: Sequence[ReportAlert],
    readings: Sequence[Mapping[str, Any]],
) -> float:
    if not sentences:
        return 0.0
    alerts_by_id = {str(_field(alert, "id")): alert for alert in alerts}
    readings_by_id = {str(reading["id"]): reading for reading in readings}
    resolved = sum(_sentence_resolves(sentence, alerts_by_id, readings_by_id, readings) for sentence in sentences)
    return resolved / len(sentences)


def _sentence_resolves(
    sentence: str,
    alerts_by_id: Mapping[str, ReportAlert],
    readings_by_id: Mapping[str, Mapping[str, Any]],
    readings: Sequence[Mapping[str, Any]],
) -> bool:
    reference = REFERENCE_PATTERN.search(sentence)
    if reference is None:
        return False
    allowed = _resolve_reference(reference, alerts_by_id, readings_by_id, readings)
    if allowed is None:
        return False
    return not _sentence_violations(sentence[:reference.start()], allowed)
