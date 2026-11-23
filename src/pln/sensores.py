"""Load and validate the canonical sensor catalog against its source JSON files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from src.pln.config import (
    ACTIVE_ASSETS_FILE,
    ACTIVE_ASSET_ID,
    DATA_VARIABLES_FILE,
    SENSORS_FILE,
)

SEVERIDADES = ("leve", "moderado", "critico")


@dataclass(frozen=True)
class Sensor:
    """Canonical sensor metadata and the actions allowed for each severity."""

    variable_id: str
    grandeza: str
    unidade: str
    limiares: Mapping[str, float] | None
    acoes_padrao: Mapping[str, str]


def _read_json(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as json_file:
            return json.load(json_file)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Não foi possível carregar o arquivo de dados: {path.name}.") from error


def _validate_sources(
    sensor_document: dict[str, Any],
    assets: list[dict[str, Any]],
    variables: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, float]]:
    if len(assets) != 1 or assets[0].get("id") != sensor_document.get("active_asset_id"):
        raise ValueError("O ativo de sensores.json não corresponde a active_assets.json.")
    source_variables = {variable["id"]: variable for variable in variables}
    thresholds = assets[0].get("applied_thresholds", {})
    if not isinstance(thresholds, dict):
        raise ValueError("Os limiares de active_assets.json precisam ser um objeto.")
    return assets[0], source_variables, thresholds


def _validated_thresholds(
    variable_id: str,
    sensor_entry: dict[str, Any],
    source_thresholds: dict[str, Any],
) -> Mapping[str, float] | None:
    recorded = sensor_entry.get("limiares")
    expected = source_thresholds.get(variable_id)
    if recorded != expected:
        raise ValueError(f"Os limiares do sensor {variable_id} divergem de active_assets.json.")
    if expected is None:
        return None
    if set(expected) != {"nominal", "warning", "critical"}:
        raise ValueError(f"O sensor {variable_id} não possui os três limiares esperados.")
    return MappingProxyType({key: float(value) for key, value in expected.items()})


def _build_sensor(
    sensor_entry: dict[str, Any],
    source_variables: dict[str, dict[str, Any]],
    source_thresholds: dict[str, Any],
) -> Sensor:
    variable_id = sensor_entry.get("variable_id")
    if variable_id not in source_variables:
        raise ValueError(f"O sensor {variable_id} não existe em data_variables.json.")
    if sensor_entry.get("descricao_origem") != source_variables[variable_id].get("description"):
        raise ValueError(f"A descrição do sensor {variable_id} diverge de data_variables.json.")
    actions = sensor_entry.get("acoes_padrao", {})
    if set(actions) != set(SEVERIDADES) or not all(actions.values()):
        raise ValueError(f"As ações do sensor {variable_id} estão incompletas.")
    return Sensor(
        variable_id=variable_id,
        grandeza=str(sensor_entry["grandeza"]),
        unidade=str(sensor_entry["unidade"]),
        limiares=_validated_thresholds(variable_id, sensor_entry, source_thresholds),
        acoes_padrao=MappingProxyType({key: str(value) for key, value in actions.items()}),
    )


def carregar_sensores(
    sensors_file: Path = SENSORS_FILE,
    active_assets_file: Path = ACTIVE_ASSETS_FILE,
    variables_file: Path = DATA_VARIABLES_FILE,
) -> dict[str, Sensor]:
    """Return canonical sensor records after cross-checking all source files."""
    sensor_document = _read_json(sensors_file)
    assets = _read_json(active_assets_file)
    variables = _read_json(variables_file)
    if sensor_document.get("active_asset_id") != ACTIVE_ASSET_ID:
        raise ValueError("O ativo de sensores.json diverge do ativo configurado.")
    _, source_variables, source_thresholds = _validate_sources(sensor_document, assets, variables)
    entries = sensor_document.get("sensors", [])
    if not isinstance(entries, list):
        raise ValueError("O catálogo de sensores precisa conter uma lista.")
    sensors = {
        entry["variable_id"]: _build_sensor(entry, source_variables, source_thresholds)
        for entry in entries
    }
    if len(sensors) != len(entries) or set(sensors) != set(source_variables):
        raise ValueError("sensores.json precisa mapear todas as variáveis de data_variables.json.")
    if set(source_thresholds) != {key for key, sensor in sensors.items() if sensor.limiares is not None}:
        raise ValueError("Os sensores com limiares divergem de active_assets.json.")
    return sensors
