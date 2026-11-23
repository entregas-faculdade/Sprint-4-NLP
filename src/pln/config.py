"""Shared paths, model identifiers, and operational settings for alert generation."""

from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = DATA_DIR / "saida"
CSV_FILE = DATA_DIR / "dados-w22.csv"
ACTIVE_ASSETS_FILE = DATA_DIR / "active_assets.json"
DATA_VARIABLES_FILE = DATA_DIR / "data_variables.json"
SENSORS_FILE = DATA_DIR / "sensores.json"
ALERT_TESTS_FILE = DATA_DIR / "alertas_teste.json"
ALERTS_OUTPUT_FILE = OUTPUT_DIR / "alertas.json"
LLM_CACHE_FILE = OUTPUT_DIR / "cache_llm.jsonl"
REQUIREMENTS_FILE = ROOT_DIR / "requirements.txt"

GAP_MAX_MIN = 60
MIN_LEITURAS_LEVE = 3
SEGUNDOS_POR_MINUTO = 60
MINUTOS_POR_HORA = 60
MAX_PALAVRAS_ALERTA = 60
MAX_PALAVRAS_PARAFRASE_ADICIONAIS = 14
PRECISAO_DECIMAIS = 2
SEQUENCIA_ID_DIGITOS = 4
TIMEOUT_REQUISICAO_SEGUNDOS = 30
MAX_TENTATIVAS_REQUISICAO = 3
BACKOFF_REQUISICAO_SEGUNDOS = 0.5
MAX_TENTATIVAS_REDACAO = 2
SEMENTE_LLM = 17
TEMPERATURA_LLM = 0
URL_OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"

# Qwen3 tem suporte multilíngue, instrução consistente e preço baixo por token.
MODELO_REDATOR = "qwen/qwen3-30b-a3b-instruct-2507"
# Mistral Small 3.2 é compacto, multilíngue e econômico para rotular eventos.
MODELO_CLASSIFICADOR = "mistralai/mistral-small-3.2-24b-instruct"
# Llama 3.3 70B oferece cobertura multilíngue para a geração prevista no pipeline.
MODELO_GERADOR = "meta-llama/llama-3.3-70b-instruct"
# Gemma 3 12B cobre mais de 140 idiomas com custo baixo para julgar respostas.
MODELO_JUIZ = "google/gemma-3-12b-it"

TERMOS_PROIBIDOS = (
    "devido a",
    "causado por",
    "causada por",
    "provavelmente",
    "provável",
    "poderá falhar",
    "poderá",
    "irá",
    "ira",
    "tende a",
    "em breve",
    "falha iminente",
    "vida útil",
    "causa raiz",
    "diagnóstico",
    "prognóstico",
    "desgaste",
    "desbalanceamento",
    "ruptura",
    "queima do enrolamento",
)

VOCABULARIO_PARAFRASE_PERMITIDO = (
    "a",
    "ao",
    "aos",
    "as",
    "às",
    "com",
    "de",
    "do",
    "da",
    "dos",
    "das",
    "durante",
    "e",
    "em",
    "entre",
    "há",
    "ha",
    "no",
    "na",
    "nos",
    "nas",
    "o",
    "os",
    "para",
    "por",
    "um",
    "uma",
    "chegou",
    "atingiu",
    "episódio",
    "episodio",
    "durou",
    "período",
    "periodo",
    "intervalo",
    "última",
    "ultima",
    "últimas",
    "ultimas",
    "último",
    "ultimo",
    "últimos",
    "ultimos",
)


def _read_active_asset() -> dict[str, Any]:
    with ACTIVE_ASSETS_FILE.open(encoding="utf-8") as active_assets_file:
        assets = json.load(active_assets_file)
    if len(assets) != 1:
        raise ValueError("Era esperado exatamente um ativo em active_assets.json.")
    return assets[0]


ACTIVE_ASSET = MappingProxyType(_read_active_asset())
ACTIVE_ASSET_ID = str(ACTIVE_ASSET["id"])
ACTIVE_ASSET_NAME = str(ACTIVE_ASSET["name"])
ACTIVE_ASSET_LOCATION = str(ACTIVE_ASSET["location"])


def _model_family(model_id: str) -> str:
    model_name = model_id.split("/", maxsplit=1)[-1]
    return model_name.split("-", maxsplit=1)[0]


if _model_family(MODELO_JUIZ) == _model_family(MODELO_GERADOR):
    raise RuntimeError("MODELO_JUIZ e MODELO_GERADOR precisam pertencer a famílias diferentes.")
