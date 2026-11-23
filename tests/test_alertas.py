"""Unit tests for severity bands, episodes, traceability, and alert verification."""

from __future__ import annotations

import json
import shutil
from dataclasses import fields
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.pln.alertas import (
    Alerta,
    NUMBER_PATTERN,
    _allowed_number_tokens,
    _format_number,
    _format_timestamp,
    classificar_severidade,
    detectar_episodios,
    gerar_template,
    carregar_leituras,
    verificar_texto,
    verificar_clareza,
)
from src.pln.config import (
    ACTIVE_ASSET_ID,
    ACTIVE_ASSETS_FILE,
    ALERT_TESTS_FILE,
    DATA_VARIABLES_FILE,
    SENSORS_FILE,
)
from src.pln.sensores import carregar_sensores

SENSORS = carregar_sensores()
TEST_CASES = json.loads(ALERT_TESTS_FILE.read_text(encoding="utf-8"))["casos"]


@pytest.mark.parametrize(
    ("threshold", "expected"),
    (("nominal", "leve"), ("warning", "moderado"), ("critical", "critico")),
)
def test_severity_boundaries_are_inclusive(threshold: str, expected: str) -> None:
    thresholds = SENSORS[next(iter(SENSORS))].limiares
    assert thresholds is not None
    assert classificar_severidade(thresholds[threshold], thresholds) == expected


def test_value_below_nominal_is_normal() -> None:
    thresholds = SENSORS[next(iter(SENSORS))].limiares
    assert thresholds is not None
    assert classificar_severidade(thresholds["nominal"] - 0.01, thresholds) == "normal"


def _reading(reading_id: str, value: float, minutes: int, variable_id: str) -> dict[str, object]:
    timestamp = datetime(2026, 6, 11, 10, tzinfo=timezone.utc) + timedelta(minutes=minutes)
    return {
        "id": reading_id,
        "asset_id": ACTIVE_ASSET_ID,
        "variable_id": variable_id,
        "value": value,
        "timestamp": timestamp.isoformat(),
    }


def test_episode_joins_gap_of_sixty_minutes_and_breaks_afterward() -> None:
    variable_id = next(key for key, sensor in SENSORS.items() if sensor.grandeza.startswith("Temperatura do enrolamento"))
    readings = [_reading("r1", 90, 0, variable_id), _reading("r2", 91, 60, variable_id), _reading("r3", 92, 121, variable_id)]
    alerts = detectar_episodios(readings, SENSORS)
    assert [alert.ids_leitura for alert in alerts] == [("r1", "r2"), ("r3",)]
    assert alerts[0].duracao_min == 60


def test_normal_reading_breaks_an_episode() -> None:
    variable_id = next(key for key, sensor in SENSORS.items() if sensor.grandeza.startswith("Temperatura do enrolamento"))
    readings = [_reading("r1", 90, 0, variable_id), _reading("r2", 70, 30, variable_id), _reading("r3", 91, 60, variable_id)]
    assert [alert.ids_leitura for alert in detectar_episodios(readings, SENSORS)] == [("r1",), ("r3",)]


def test_short_light_episode_is_dropped_and_three_readings_are_kept() -> None:
    variable_id = next(key for key, sensor in SENSORS.items() if sensor.grandeza.startswith("Temperatura do enrolamento"))
    short_episode = [_reading("r1", 80, 0, variable_id), _reading("r2", 81, 30, variable_id)]
    valid_episode = _reading_set(variable_id, (80, 81, 82))
    assert detectar_episodios(short_episode, SENSORS) == []
    assert len(detectar_episodios(valid_episode, SENSORS)) == 1


def _reading_set(variable_id: str, values: tuple[float, ...]) -> list[dict[str, object]]:
    return [_reading(f"valid-{index}", value, index * 30, variable_id) for index, value in enumerate(values)]


def test_episode_severity_is_the_highest_reading_severity() -> None:
    variable_id = next(key for key, sensor in SENSORS.items() if sensor.grandeza.startswith("Temperatura do enrolamento"))
    readings = [_reading("r1", 80, 0, variable_id), _reading("r2", 90, 30, variable_id), _reading("r3", 110, 60, variable_id)]
    alert = detectar_episodios(readings, SENSORS)[0]
    assert alert.severidade == "critico"
    assert alert.valor_max == 110


def test_real_alert_reading_ids_exist_in_the_source_csv() -> None:
    readings = carregar_leituras()
    source_ids = {str(reading["id"]) for reading in readings}
    alerts = detectar_episodios(readings, SENSORS)
    assert alerts
    assert all(set(alert.ids_leitura).issubset(source_ids) for alert in alerts)


def test_alert_contains_the_complete_traceability_contract() -> None:
    alert = detectar_episodios(carregar_leituras(), SENSORS)[0]
    assert isinstance(alert, Alerta)
    assert {field.name for field in fields(Alerta)} == {
        "id",
        "ativo",
        "sensor_id",
        "grandeza",
        "unidade",
        "severidade",
        "inicio",
        "fim",
        "duracao_min",
        "n_leituras",
        "valor_max",
        "valor_medio",
        "limiar_nominal",
        "limiar_alerta",
        "limiar_critico",
        "desvio_abs",
        "desvio_pct",
        "ids_leitura",
        "origem_texto",
    }
    assert alert.id.startswith("A-")
    assert alert.sensor_id in SENSORS
    assert alert.inicio <= alert.fim
    assert alert.duracao_min >= 0
    assert alert.n_leituras == len(alert.ids_leitura)
    assert alert.limiar_nominal < alert.limiar_alerta < alert.limiar_critico


def test_templates_use_severity_specific_tone() -> None:
    by_severity = {}
    for case in TEST_CASES:
        if case["descartar"]:
            continue
        alert = detectar_episodios(case["leituras"], SENSORS)[0]
        by_severity.setdefault(alert.severidade, gerar_template(alert))
    assert "acompanhe a" in by_severity["leve"]
    assert "programe inspeção da" in by_severity["moderado"]
    assert "verifique com urgência a" in by_severity["critico"]


def test_all_nine_reference_templates_meet_the_notebook_clarity_check() -> None:
    valid_cases = [case for case in TEST_CASES if not case["descartar"]]
    assert len(valid_cases) == 9
    for case in valid_cases:
        alert = detectar_episodios(case["leituras"], SENSORS)[0]
        assert verificar_clareza(gerar_template(alert), alert), case["caso"]


def test_verifiers_normalize_narrow_no_break_space_the_same_way() -> None:
    alert = _sample_alert()
    template = gerar_template(alert)
    regular_measurement = f"{_format_number(alert.valor_max)} {alert.unidade}"
    narrow_measurement = f"{_format_number(alert.valor_max)}\u202f{alert.unidade}"
    text = template.replace(regular_measurement, narrow_measurement)

    assert narrow_measurement in text
    assert verificar_clareza(text, alert) is verificar_clareza(template, alert) is True
    assert verificar_texto(text, alert) == verificar_texto(template, alert) == []


@pytest.mark.parametrize(
    "untrusted_text",
    (
        " O valor adicional é +30 °C.",
        " O limite informado foi de 100 °C.",
        " Provavelmente o equipamento falhará.",
        " O alerta ocorreu devido a rolamento.",
    ),
)
def test_verifier_rejects_invented_numbers_and_claims(untrusted_text: str) -> None:
    alert = _sample_alert()
    assert verificar_texto(gerar_template(alert) + untrusted_text, alert)


def test_verifier_rejects_a_changed_default_action() -> None:
    case = next(case for case in TEST_CASES if case["caso"] == "moderado-limite-warning")
    alert = detectar_episodios(case["leituras"], SENSORS)[0]
    action = SENSORS[alert.sensor_id].acoes_padrao[alert.severidade]
    text = gerar_template(alert).replace(action, "Substitua o sensor.")
    assert any(item.codigo == "acao_alterada" for item in verificar_texto(text, alert))


def test_verifier_rejects_unmodeled_words_without_numbers() -> None:
    alert = _sample_alert()
    text = gerar_template(alert) + " Verifique também os rolamentos e a lubrificação."
    violations = verificar_texto(text, alert)
    assert any(item.codigo == "conteudo_nao_sustentado" for item in violations)


def test_verifier_accepts_reordered_sentences_with_the_same_facts() -> None:
    alert = _sample_alert()
    sentences = gerar_template(alert).split(". ")
    reordered_text = ". ".join(reversed(sentences))
    assert verificar_texto(reordered_text, alert) == []


def test_verifier_accepts_a_faithful_rewrite_with_new_connectives() -> None:
    alert, paraphrase = _faithful_current_paraphrase()
    assert verificar_texto(paraphrase, alert) == []


def test_verifier_rejects_extra_content_after_a_faithful_rewrite() -> None:
    alert, paraphrase = _faithful_current_paraphrase()
    text = paraphrase + " Verifique também os rolamentos e a lubrificação."
    violations = verificar_texto(text, alert)
    assert any(item.codigo == "conteudo_nao_sustentado" for item in violations)


def test_verifier_rejects_a_changed_action_after_a_faithful_rewrite() -> None:
    alert, paraphrase = _faithful_current_paraphrase()
    action = SENSORS[alert.sensor_id].acoes_padrao[alert.severidade]
    changed_text = paraphrase.replace(action, "Substitua o sensor.")
    violations = verificar_texto(changed_text, alert)
    assert any(item.codigo == "acao_alterada" for item in violations)


def test_verifier_limits_additional_paraphrase_vocabulary() -> None:
    alert, paraphrase = _faithful_current_paraphrase()
    text = paraphrase + (" e" * 15)
    violations = verificar_texto(text, alert)
    assert any(item.codigo == "parafrase_excessiva" for item in violations)


def test_template_uses_lowercase_quantity_and_accurate_utc_times() -> None:
    variable_id = next(key for key, sensor in SENSORS.items() if sensor.grandeza.startswith("Temperatura do enrolamento"))
    readings = [
        _reading("short-start", 80, 0, variable_id),
        _reading("short-middle", 81, 0, variable_id),
        _reading("short-end", 82, 0, variable_id),
    ]
    readings[1]["timestamp"] = "2026-06-11T10:00:15+00:00"
    readings[2]["timestamp"] = "2026-06-11T10:00:30+00:00"
    alert = detectar_episodios(readings, SENSORS)[0]
    text = gerar_template(alert)
    assert alert.inicio < alert.fim
    assert "; acompanhe a temperatura" in text
    assert "menos de um minuto" in text
    assert "no instante registrado" not in text
    assert "10:00 UTC" in text
    assert "10:00:30 UTC" in text


def test_reference_numbers_are_supported_by_each_alert_case() -> None:
    for case in TEST_CASES:
        if case["descartar"]:
            continue
        alert = detectar_episodios(case["leituras"], SENSORS)[0]
        reference_numbers = set(NUMBER_PATTERN.findall(case["resumo_referencia"]))
        unsupported_numbers = reference_numbers - _allowed_number_tokens(alert)
        assert not unsupported_numbers, f"{case['caso']}: {sorted(unsupported_numbers)}"


def test_verifier_accepts_all_nine_reference_templates() -> None:
    valid_cases = [case for case in TEST_CASES if not case["descartar"]]
    assert len(valid_cases) >= 9
    for case in valid_cases:
        alerts = detectar_episodios(case["leituras"], SENSORS)
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.severidade == case["severidade_esperada"]
        assert verificar_texto(gerar_template(alert), alert) == []


def test_sensor_thresholds_must_match_the_active_asset_file(tmp_path: Path) -> None:
    sensors_path = tmp_path / "sensores.json"
    assets_path = tmp_path / "active_assets.json"
    variables_path = tmp_path / "data_variables.json"
    shutil.copyfile(SENSORS_FILE, sensors_path)
    shutil.copyfile(ACTIVE_ASSETS_FILE, assets_path)
    shutil.copyfile(DATA_VARIABLES_FILE, variables_path)
    sensor_document = json.loads(sensors_path.read_text(encoding="utf-8"))
    sensor_document["sensors"][0]["limiares"]["nominal"] += 1
    sensors_path.write_text(json.dumps(sensor_document), encoding="utf-8")
    with pytest.raises(ValueError, match="divergem"):
        carregar_sensores(sensors_path, assets_path, variables_path)


def _sample_alert() -> Alerta:
    case = next(case for case in TEST_CASES if case["caso"] == "leve-temperatura")
    return detectar_episodios(case["leituras"], SENSORS)[0]


def _faithful_current_paraphrase() -> tuple[Alerta, str]:
    sensor = next(sensor for sensor in SENSORS.values() if sensor.grandeza == "Corrente elétrica por fase")
    readings = [
        _reading("paraphrase-r0", 128.0, 0, sensor.variable_id),
        _reading("paraphrase-r1", 129.48, 30, sensor.variable_id),
        _reading("paraphrase-r2", 129.2, 60, sensor.variable_id),
    ]
    alert = detectar_episodios(readings, SENSORS)[0]
    action = sensor.acoes_padrao[alert.severidade]
    paraphrase = (
        f"No ativo {alert.ativo} há um alerta leve: a {alert.grandeza.casefold()} chegou a pico "
        f"{_format_number(alert.valor_max)} {alert.unidade}, com desvio +{_format_number(alert.desvio_abs)} "
        f"{alert.unidade} acima do nominal {_format_number(alert.limiar_nominal)} {alert.unidade}. "
        f"O episódio durou uma hora, entre {_format_timestamp(alert.inicio)} e {_format_timestamp(alert.fim)}. "
        f"{action}"
    )
    return alert, paraphrase
