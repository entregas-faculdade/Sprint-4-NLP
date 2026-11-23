"""Classify sensor deviations and render traceable, deterministic alert episodes."""

from __future__ import annotations

import csv
import math
import re
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.pln.config import (
    ACTIVE_ASSET_ID,
    ACTIVE_ASSET_LOCATION,
    ACTIVE_ASSET_NAME,
    CSV_FILE,
    GAP_MAX_MIN,
    MAX_PALAVRAS_ALERTA,
    MAX_PALAVRAS_PARAFRASE_ADICIONAIS,
    MIN_LEITURAS_LEVE,
    MINUTOS_POR_HORA,
    PRECISAO_DECIMAIS,
    SEGUNDOS_POR_MINUTO,
    SEQUENCIA_ID_DIGITOS,
    VOCABULARIO_PARAFRASE_PERMITIDO,
)
from src.pln.sensores import Sensor, carregar_sensores

NUMBER_PATTERN = re.compile(r"(?<![\w])[+-]?\d+(?:[.,]\d+)*(?!\w)", re.UNICODE)
REQUIRED_CSV_FIELDS = {"id", "asset_id", "variable_id", "value", "timestamp"}


@dataclass(frozen=True)
class Alerta:
    """Episode facts that may be used in an alert narrative."""

    id: str
    ativo: str
    sensor_id: str
    grandeza: str
    unidade: str
    severidade: str
    inicio: datetime
    fim: datetime
    duracao_min: float
    n_leituras: int
    valor_max: float
    valor_medio: float
    limiar_nominal: float
    limiar_alerta: float
    limiar_critico: float
    desvio_abs: float
    desvio_pct: float
    ids_leitura: tuple[str, ...]
    origem_texto: str = "template"


@dataclass(frozen=True)
class Violacao:
    """A reason why text contains unsupported or missing alert information."""

    codigo: str
    mensagem: str
    trecho: str = ""


def classificar_severidade(valor: float, limiares: Mapping[str, float]) -> str:
    """Classify a value using inclusive lower boundaries for each alert band."""
    required_thresholds = {"nominal", "warning", "critical"}
    if not required_thresholds.issubset(limiares):
        raise ValueError("Os limiares precisam conter nominal, warning e critical.")
    if not all(float(limiares[key]) < float(limiares[next_key]) for key, next_key in (("nominal", "warning"), ("warning", "critical"))):
        raise ValueError("Os limiares precisam estar em ordem crescente.")
    if valor < limiares["nominal"]:
        return "normal"
    if valor < limiares["warning"]:
        return "leve"
    if valor < limiares["critical"]:
        return "moderado"
    return "critico"


def carregar_leituras(csv_file: Path = CSV_FILE) -> list[dict[str, Any]]:
    """Load typed readings from the source CSV and reject incomplete rows."""
    try:
        with csv_file.open(encoding="utf-8-sig", newline="") as source_file:
            reader = csv.DictReader(source_file)
            if not REQUIRED_CSV_FIELDS.issubset(reader.fieldnames or []):
                raise ValueError("O CSV não possui as colunas exigidas pelo contrato de leitura.")
            return [_normalize_reading(row) for row in reader]
    except OSError as error:
        raise RuntimeError(f"Não foi possível ler o CSV {csv_file.name}.") from error


def _normalize_reading(reading: Mapping[str, Any]) -> dict[str, Any]:
    missing_fields = REQUIRED_CSV_FIELDS.difference(reading)
    if missing_fields:
        raise ValueError(f"Leitura sem campos obrigatórios: {', '.join(sorted(missing_fields))}.")
    try:
        value = float(reading["value"])
        timestamp = _parse_timestamp(reading["timestamp"])
    except (TypeError, ValueError) as error:
        raise ValueError("A leitura contém valor ou horário inválido.") from error
    if not reading["id"] or not reading["variable_id"] or not reading["asset_id"]:
        raise ValueError("A leitura contém identificador vazio.")
    if not math.isfinite(value):
        raise ValueError("A leitura contém um valor numérico não finito.")
    return {**reading, "value": value, "timestamp": timestamp}


def _parse_timestamp(value: Any) -> datetime:
    timestamp = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def _reading_severity(reading: Mapping[str, Any], sensor: Sensor) -> str:
    if sensor.limiares is None:
        return "normal"
    return classificar_severidade(float(reading["value"]), sensor.limiares)


def _partition_sensor_episodes(
    readings: list[dict[str, Any]], sensor: Sensor
) -> list[list[dict[str, Any]]]:
    episodes: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for reading in sorted(readings, key=lambda item: (item["timestamp"], item["id"])):
        severity = _reading_severity(reading, sensor)
        if severity == "normal":
            _append_episode(episodes, current)
            current = []
            continue
        if current and _gap_minutes(current[-1], reading) > GAP_MAX_MIN:
            _append_episode(episodes, current)
            current = []
        current.append(reading)
    _append_episode(episodes, current)
    return episodes


def _append_episode(
    episodes: list[list[dict[str, Any]]], current: list[dict[str, Any]]
) -> None:
    if current:
        episodes.append(current.copy())


def _gap_minutes(previous: Mapping[str, Any], following: Mapping[str, Any]) -> float:
    delta = following["timestamp"] - previous["timestamp"]
    return delta.total_seconds() / SEGUNDOS_POR_MINUTO


def _episode_severity(readings: list[dict[str, Any]], sensor: Sensor) -> str:
    priority = {"leve": 1, "moderado": 2, "critico": 3}
    return max((_reading_severity(reading, sensor) for reading in readings), key=priority.get)


def _build_alert(readings: list[dict[str, Any]], sensor: Sensor) -> Alerta | None:
    severity = _episode_severity(readings, sensor)
    if severity == "leve" and len(readings) < MIN_LEITURAS_LEVE:
        return None
    thresholds = sensor.limiares
    if thresholds is None:
        return None
    values = [float(reading["value"]) for reading in readings]
    start = readings[0]["timestamp"]
    end = readings[-1]["timestamp"]
    maximum = max(values)
    deviation = maximum - thresholds["nominal"]
    return Alerta(
        id="",
        ativo=f"{ACTIVE_ASSET_NAME} ({ACTIVE_ASSET_LOCATION})",
        sensor_id=sensor.variable_id,
        grandeza=sensor.grandeza,
        unidade=sensor.unidade,
        severidade=severity,
        inicio=start,
        fim=end,
        duracao_min=(end - start).total_seconds() / SEGUNDOS_POR_MINUTO,
        n_leituras=len(readings),
        valor_max=maximum,
        valor_medio=sum(values) / len(values),
        limiar_nominal=thresholds["nominal"],
        limiar_alerta=thresholds["warning"],
        limiar_critico=thresholds["critical"],
        desvio_abs=deviation,
        desvio_pct=(deviation / thresholds["nominal"] * 100) if thresholds["nominal"] else 0.0,
        ids_leitura=tuple(str(reading["id"]) for reading in readings),
    )


def detectar_episodios(
    leituras: Iterable[Mapping[str, Any]], sensores: Mapping[str, Sensor] | None = None
) -> list[Alerta]:
    """Group alerting readings by sensor and assign stable IDs by start time."""
    sensor_catalog = sensores if sensores is not None else carregar_sensores()
    grouped_readings: dict[str, list[dict[str, Any]]] = {}
    for source_reading in leituras:
        reading = _normalize_reading(source_reading)
        if reading["asset_id"] != ACTIVE_ASSET_ID:
            continue
        if reading["variable_id"] in sensor_catalog:
            grouped_readings.setdefault(reading["variable_id"], []).append(reading)
    alerts = _collect_alerts(grouped_readings, sensor_catalog)
    alerts.sort(key=lambda alert: (alert.inicio, alert.sensor_id, alert.ids_leitura))
    return [
        replace(alert, id=f"A-{index:0{SEQUENCIA_ID_DIGITOS}d}")
        for index, alert in enumerate(alerts, start=1)
    ]


def _collect_alerts(
    grouped_readings: Mapping[str, list[dict[str, Any]]], sensors: Mapping[str, Sensor]
) -> list[Alerta]:
    alerts: list[Alerta] = []
    for sensor_id, readings in grouped_readings.items():
        sensor = sensors[sensor_id]
        if sensor.limiares is None:
            continue
        for episode in _partition_sensor_episodes(readings, sensor):
            alert = _build_alert(episode, sensor)
            if alert is not None:
                alerts.append(alert)
    return alerts


def _format_number(value: float) -> str:
    formatted = f"{value:,.{PRECISAO_DECIMAIS}f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def _format_timestamp(value: datetime) -> str:
    timestamp = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    time_format = "%d/%m/%Y às %H:%M:%S" if timestamp.second or timestamp.microsecond else "%d/%m/%Y às %H:%M"
    return f"{timestamp.strftime(time_format)} UTC"


def _format_duration(duration_minutes: float) -> str:
    total_minutes = round(duration_minutes)
    hours, minutes = divmod(total_minutes, MINUTOS_POR_HORA)
    if hours == 1 and not minutes:
        return "na última hora"
    if hours > 1 and not minutes:
        return f"nas últimas {hours} horas"
    if not hours and minutes == 1:
        return "no último minuto"
    if not hours and minutes > 1:
        return f"nos últimos {minutes} minutos"
    if hours and minutes:
        hour_phrase = "1 hora" if hours == 1 else f"{hours} horas"
        minute_phrase = "1 minuto" if minutes == 1 else f"{minutes} minutos"
        return f"na janela de {hour_phrase} e {minute_phrase}"
    return "em menos de um minuto"


def _template_opening(severity: str, asset: str) -> str:
    if severity == "leve":
        return f"Alerta leve para o ativo {asset}; acompanhe a "
    if severity == "moderado":
        return f"Alerta moderado para o ativo {asset}; programe inspeção da "
    return f"Alerta crítico para o ativo {asset}; verifique com urgência a "


def _lowercase_initial(value: str) -> str:
    return f"{value[:1].lower()}{value[1:]}"


def _render_template(alerta: Alerta, sensor: Sensor) -> str:
    action = sensor.acoes_padrao[alerta.severidade]
    deviation = _format_number(alerta.desvio_abs)
    if alerta.desvio_abs >= 0:
        deviation = f"+{deviation}"
    return (
        f"{_template_opening(alerta.severidade, alerta.ativo)}{_lowercase_initial(alerta.grandeza)}: "
        f"pico {_format_number(alerta.valor_max)} {alerta.unidade}; desvio {deviation} {alerta.unidade} "
        f"acima do nominal {_format_number(alerta.limiar_nominal)} {alerta.unidade}. "
        f"{_format_duration(alerta.duracao_min).capitalize()}, entre {_format_timestamp(alerta.inicio)} "
        f"e {_format_timestamp(alerta.fim)}. {action}"
    )


def gerar_template(alerta: Alerta) -> str:
    """Render the deterministic narrative for a validated alert episode."""
    return _render_template(alerta, carregar_sensores()[alerta.sensor_id])


def verificar_clareza(texto: str, alerta: Alerta) -> bool:
    """Check that a short alert names the asset, quantity, peak, and UTC start."""
    normalized_text = texto.casefold()
    required_facts = (
        alerta.ativo,
        alerta.grandeza,
        f"{_format_number(alerta.valor_max)} {alerta.unidade}",
        _format_timestamp(alerta.inicio),
    )
    word_count = len(re.findall(r"\w+", texto, flags=re.UNICODE))
    return word_count <= MAX_PALAVRAS_ALERTA and all(
        fact.casefold() in normalized_text for fact in required_facts
    )


def _allowed_number_tokens(alerta: Alerta) -> set[str]:
    permitted_values = (
        alerta.valor_max,
        alerta.valor_medio,
        alerta.limiar_nominal,
        alerta.limiar_alerta,
        alerta.limiar_critico,
        alerta.desvio_abs,
        alerta.desvio_pct,
    )
    permitted = {token for value in permitted_values for token in NUMBER_PATTERN.findall(_format_number(value))}
    deviation = _format_number(alerta.desvio_abs)
    permitted.add(f"+{deviation}" if alerta.desvio_abs >= 0 else deviation)
    permitted.add(str(alerta.n_leituras))
    permitted.update(NUMBER_PATTERN.findall(_format_duration(alerta.duracao_min)))
    total_minutes = round(alerta.duracao_min)
    hours, minutes = divmod(total_minutes, MINUTOS_POR_HORA)
    if hours:
        permitted.add(str(hours))
    if minutes:
        permitted.add(str(minutes))
    for timestamp in (alerta.inicio, alerta.fim):
        permitted.update(NUMBER_PATTERN.findall(_format_timestamp(timestamp)))
    return permitted


def _mentions_unit(text: str, unit: str) -> bool:
    numeric_value = r"(?<!\w)[+-]?\d+(?:[.,]\d+)*"
    unit_pattern = rf"{numeric_value}\s*{re.escape(unit)}(?!\w)"
    return re.search(unit_pattern, text, flags=re.IGNORECASE) is not None


def _unsupported_references(text: str, alerta: Alerta) -> list[Violacao]:
    normalized = text.casefold()
    violations: list[Violacao] = []
    sensors = carregar_sensores()
    if alerta.ativo.casefold() not in normalized:
        violations.append(Violacao("ativo_ausente", "O texto omite o ativo do alerta.", alerta.ativo))
    if alerta.grandeza.casefold() not in normalized:
        violations.append(Violacao("grandeza_ausente", "O texto omite a grandeza do alerta.", alerta.grandeza))
    if not _mentions_unit(text, alerta.unidade):
        violations.append(Violacao("unidade_ausente", "O texto omite a unidade do alerta.", alerta.unidade))
    for sensor_id, sensor in sensors.items():
        if sensor_id != alerta.sensor_id and sensor.grandeza.casefold() in normalized:
            violations.append(Violacao("grandeza_nao_sustentada", "O texto menciona outra grandeza.", sensor.grandeza))
        if sensor.unidade.casefold() != alerta.unidade.casefold() and _mentions_unit(text, sensor.unidade):
            violations.append(Violacao("unidade_nao_sustentada", "O texto menciona outra unidade.", sensor.unidade))
    return violations


def _missing_episode_facts(text: str, alerta: Alerta) -> list[Violacao]:
    required_facts = (
        (_format_number(alerta.valor_max), "valor_max"),
        (f"+{_format_number(alerta.desvio_abs)}", "desvio_abs"),
        (_format_number(alerta.limiar_nominal), "limiar_nominal"),
        ("acima do nominal", "relacao_desvio_nominal"),
        (_format_timestamp(alerta.inicio), "inicio"),
        (_format_timestamp(alerta.fim), "fim"),
    )
    normalized = text.casefold()
    violations = [
        Violacao("fato_ausente", f"O texto omite o campo {field_name}.", fact)
        for fact, field_name in required_facts
        if fact.casefold() not in normalized
    ]
    if not _mentions_duration(normalized, alerta.duracao_min):
        violations.append(Violacao("fato_ausente", "O texto omite a duração do episódio.", _format_duration(alerta.duracao_min)))
    if not _mentions_peak(normalized):
        violations.append(Violacao("fato_ausente", "O texto omite a indicação do valor de pico."))
    return violations


def _duration_phrases(duration_minutes: float) -> tuple[str, ...]:
    total_minutes = round(duration_minutes)
    if total_minutes == 0:
        return ("menos de um minuto", "inferior a um minuto")
    hours, minutes = divmod(total_minutes, MINUTOS_POR_HORA)
    if hours:
        hour_phrase = "uma hora" if hours == 1 else f"{hours} horas"
        if minutes:
            minute_phrase = "um minuto" if minutes == 1 else f"{minutes} minutos"
            amount = f"{hour_phrase} e {minute_phrase}"
        else:
            amount = hour_phrase
    else:
        amount = "um minuto" if minutes == 1 else f"{minutes} minutos"
    return (
        _format_duration(duration_minutes),
        amount,
        f"durante {amount}",
        f"por {amount}",
        f"durou {amount}",
        f"episódio durou {amount}",
    )


def _mentions_duration(normalized_text: str, duration_minutes: float) -> bool:
    return any(phrase.casefold() in normalized_text for phrase in _duration_phrases(duration_minutes))


def _mentions_peak(normalized_text: str) -> bool:
    peak_phrases = ("pico", "valor máximo", "valor maximo", "máximo", "maximo")
    return any(phrase in normalized_text for phrase in peak_phrases)


def _mentions_severity(normalized_text: str, severity: str) -> bool:
    severity_labels = {
        "leve": ("alerta leve",),
        "moderado": ("alerta moderado",),
        "critico": ("alerta crítico", "alerta critico"),
    }
    return any(label in normalized_text for label in severity_labels.get(severity, ()))


def _mentions_measurement(text: str, value: float, unit: str) -> bool:
    number = re.escape(_format_number(value))
    measurement_pattern = rf"(?<!\w){number}\s*{re.escape(unit)}(?!\w)"
    return re.search(measurement_pattern, text, flags=re.IGNORECASE) is not None


def _number_violations(text: str, alerta: Alerta) -> list[Violacao]:
    permitted = _allowed_number_tokens(alerta)
    return [
        Violacao("numero_nao_permitido", "O texto contém um número fora dos dados do alerta.", number)
        for number in NUMBER_PATTERN.findall(text)
        if number not in permitted
    ]


def _prohibited_term_violations(text: str) -> list[Violacao]:
    from src.pln.config import TERMOS_PROIBIDOS

    violations = []
    for term in TERMOS_PROIBIDOS:
        if re.search(rf"\b{re.escape(term)}\b", text, flags=re.IGNORECASE):
            violations.append(Violacao("termo_proibido", "O texto contém diagnóstico, causa ou prognóstico.", term))
    return violations


def _unsupported_content_violations(text: str, alerta: Alerta, sensor: Sensor) -> list[Violacao]:
    template_tokens = Counter(re.findall(r"\w+", _render_template(alerta, sensor).casefold(), flags=re.UNICODE))
    text_tokens = Counter(re.findall(r"\w+", text.casefold(), flags=re.UNICODE))
    additional_tokens = text_tokens - template_tokens
    allowed_vocabulary = set(VOCABULARIO_PARAFRASE_PERMITIDO)
    unsupported_tokens = sorted(
        token for token, count in additional_tokens.items() if token not in allowed_vocabulary and count > 0
    )
    if unsupported_tokens:
        return [
            Violacao(
                "conteudo_nao_sustentado",
                "O texto contém vocabulário fora do template e da lista de paráfrase permitida.",
                ", ".join(unsupported_tokens),
            )
        ]
    additional_word_count = sum(additional_tokens.values())
    if additional_word_count > MAX_PALAVRAS_PARAFRASE_ADICIONAIS:
        return [
            Violacao(
                "parafrase_excessiva",
                "A paráfrase excede o limite de palavras adicionais permitido.",
                str(additional_word_count),
            )
        ]
    return []


def verificar_texto(texto: str, alerta: Alerta) -> list[Violacao]:
    """Reject unsupported numbers, references, prohibited claims, or changed actions."""
    if not texto.strip():
        return [Violacao("texto_vazio", "O texto do alerta está vazio.")]
    sensors = carregar_sensores()
    sensor = sensors.get(alerta.sensor_id)
    if sensor is None:
        return [Violacao("sensor_desconhecido", "O sensor do alerta não existe no catálogo.", alerta.sensor_id)]
    expected_action = sensor.acoes_padrao.get(alerta.severidade)
    normalized_text = re.sub(r"\s+", " ", texto.casefold())
    normalized_action = re.sub(r"\s+", " ", (expected_action or "").casefold())
    violations = _unsupported_references(texto, alerta)
    if not _mentions_severity(normalized_text, alerta.severidade):
        violations.append(Violacao("severidade_ausente", "O texto omite a severidade do alerta."))
    violations.extend(_missing_episode_facts(texto, alerta))
    violations.extend(_number_violations(texto, alerta))
    violations.extend(_prohibited_term_violations(texto))
    if not _mentions_measurement(texto, alerta.valor_max, alerta.unidade):
        violations.append(Violacao("valor_unidade_ausente", "O texto omite o valor máximo com sua unidade."))
    violations.extend(_unsupported_content_violations(texto, alerta, sensor))
    if not normalized_action or normalized_action not in normalized_text:
        violations.append(Violacao("acao_alterada", "O texto não contém a ação padrão do sensor.", expected_action or ""))
    return violations
