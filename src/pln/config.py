"""Shared paths, model identifiers, and operational settings for alert generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT_DIR / ".env"
NOMES_VARIAVEL_CHAVE = ("OPENROUTER_API_KEY", "OPEN-ROUTER-API-KEY")
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = DATA_DIR / "saida"
CSV_FILE = DATA_DIR / "dados-w22.csv"
ACTIVE_ASSETS_FILE = DATA_DIR / "active_assets.json"
DATA_VARIABLES_FILE = DATA_DIR / "data_variables.json"
SENSORS_FILE = DATA_DIR / "sensores.json"
ALERT_TESTS_FILE = DATA_DIR / "alertas_teste.json"
ALERTS_OUTPUT_FILE = OUTPUT_DIR / "alertas.json"
EVENTS_FILE = DATA_DIR / "eventos_rotulados.json"
REPORT_REFERENCE_FILE = DATA_DIR / "relatorio_referencia.json"
CLASSIFICATION_OUTPUT_FILE = OUTPUT_DIR / "classificacao.json"
DAILY_REPORT_OUTPUT_FILE = OUTPUT_DIR / "relatorio_diario.json"
WEEKLY_REPORT_OUTPUT_FILE = OUTPUT_DIR / "relatorio_semanal.json"
LLM_CACHE_FILE = OUTPUT_DIR / "cache_llm.jsonl"
REQUIREMENTS_FILE = ROOT_DIR / "requirements.txt"
PDF_CATALOGO_FILE = ROOT_DIR / "docs" / "WEG-w22-motor-eletrico-trifasico-brochure.pdf"
TERMOS_ESTADO_FILE = DATA_DIR / "termos_estado.json"

CHUNK_MAX = 900
CHUNK_OVERLAP = 100
CHUNK_MIN = 40
CHUNK_LEGADO_MAX = 1000
TABLE_CAPTION_MAX_GAP = 40
K_BUSCA_LEGADO = 5
K_BUSCA_NOVO = 20
K_BUSCA = K_BUSCA_NOVO
K_FINAL = 4
K_FINAL_LEGADO = 2
K_FINAL_NOVO = K_FINAL
PESO_ESTADO = 0.15
CHROMA_COLLECTION_LEGADO = "weg_w22_legado"
CHROMA_COLLECTION_NOVO = "weg_w22_multilingual"
CHROMA_DISTANCE_KEY = "hnsw:space"
CHROMA_DISTANCE_COSINE = "cosine"
PREFIXO_QUERY_NOVO = "query: "
PREFIXO_PASSAGE_NOVO = "passage: "
MODELO_EMBEDDING_LEGADO = "all-MiniLM-L6-v2"
MODELO_EMBEDDING_NOVO = "intfloat/multilingual-e5-base"
MODELO_RERANKER_LEGADO = "cross-encoder/ms-marco-MiniLM-L-6-v2"
MODELO_RERANKER_NOVO = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"


@dataclass(frozen=True)
class PresetRAG:
    """All model and retrieval settings for one reproducible RAG preset."""

    nome: str
    colecao: str
    modelo_embedding: str
    modelo_reranker: str
    chunk_max: int
    chunk_overlap: int
    k_busca: int
    k_final: int
    prefixo_query: str
    prefixo_passage: str
    usa_estado: bool
    peso_estado: float


LEGADO = PresetRAG(
    nome="LEGADO",
    colecao=CHROMA_COLLECTION_LEGADO,
    modelo_embedding=MODELO_EMBEDDING_LEGADO,
    modelo_reranker=MODELO_RERANKER_LEGADO,
    chunk_max=CHUNK_LEGADO_MAX,
    chunk_overlap=0,
    k_busca=K_BUSCA_LEGADO,
    k_final=K_FINAL_LEGADO,
    prefixo_query="",
    prefixo_passage="",
    usa_estado=False,
    peso_estado=0.0,
)
NOVO = PresetRAG(
    nome="NOVO",
    colecao=CHROMA_COLLECTION_NOVO,
    modelo_embedding=MODELO_EMBEDDING_NOVO,
    modelo_reranker=MODELO_RERANKER_NOVO,
    chunk_max=CHUNK_MAX,
    chunk_overlap=CHUNK_OVERLAP,
    k_busca=K_BUSCA_NOVO,
    k_final=K_FINAL_NOVO,
    prefixo_query=PREFIXO_QUERY_NOVO,
    prefixo_passage=PREFIXO_PASSAGE_NOVO,
    usa_estado=True,
    peso_estado=PESO_ESTADO,
)

CATEGORIAS_EVENTO = (
    "manutenção corretiva",
    "manutenção preventiva",
    "anomalia elétrica",
    "anomalia mecânica",
    "operação normal",
)
CRITERIOS_CATEGORIA_EVENTO = {
    "manutenção corretiva": "Intervenção não planejada para reparar ou substituir um componente após uma ocorrência.",
    "manutenção preventiva": "Inspeção, limpeza, lubrificação ou ajuste planejado antes de uma falha registrada.",
    "anomalia elétrica": "Evento observado em corrente, tensão, conexão, isolamento ou proteção elétrica.",
    "anomalia mecânica": "Evento observado em vibração, ruído, rotação, eixo, acoplamento ou suporte mecânico.",
    "operação normal": "Registro sem ocorrência ou desvio observado durante a operação do motor.",
}
# Lexicon terms were selected from the two dev examples per category only.
LEXICO_CLASSIFICACAO = {
    "manutenção corretiva": ("os corretiva", "reparo emergencial", "trocado", "troca"),
    "manutenção preventiva": ("inspeção programada", "plano de inspeção", "calendário de revisão", "lubrificação"),
    "anomalia elétrica": ("corrente por fase", "alarme no terminal", "tensão oscilou", "aquecimento no conector"),
    "anomalia mecânica": ("vibração no mancal", "ruído metálico", "folga no acoplamento", "eixo oscilou"),
    "operação normal": ("operação estável", "carga regular", "leituras dentro", "sem ocorrência", "próxima do padrão"),
}

SPLIT_DEV = "dev"
SPLIT_TESTE = "teste"
ORIGEM_ALERTA = "derivado_de_alerta"
ORIGEM_SINTETICA = "sintetico"
EVENTOS_POR_CATEGORIA = 12
EVENTOS_DEV_POR_CATEGORIA = 2
EVENTOS_TESTE_POR_CATEGORIA = 10
MIN_EVENTOS_DERIVADOS_DE_ALERTA = 6
PERIODO_DIARIO = "diario"
PERIODO_SEMANAL = "semanal"
DIAS_PERIODO_SEMANAL = 7
MAX_ALERTAS_RELATORIO = 5
LIMIAR_TENDENCIA_PCT = 5.0
PRECISAO_RELATORIO = 2
PRECISAO_TENDENCIA_PCT = 1
MAX_PALAVRAS_RELATORIO = 30
CLASSES_SEVERIDADE_RELATORIO = ("leve", "moderado", "critico")
SEVERIDADE_EXIBICAO = {"leve": "leve", "moderado": "moderado", "critico": "crítico"}
SEVERIDADE_ADJETIVO_FEMININO = {"leve": "leve", "moderado": "moderada", "critico": "crítica"}
SECOES_RELATORIO = (
    "Resumo",
    "Alertas emitidos",
    "Sensores em risco",
    "Tendências",
    "Ações padrão",
)

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

MEMORIA_TURNOS = 3
LIMIAR_PALAVRAS_CONSULTA = 6
LIMIAR_ABSTENCAO = -2.9
MARGEM_ABSTENCAO = 0.1
NIVEL_CONFIANCA_BAIXA = "Baixa"
FAIXAS_CONFIANCA = {
    "Alta": {"score_minimo": 8.0, "chunks_minimos": 3},
    "Média": {"score_minimo": 0.0, "chunks_minimos": 1},
}
FRASE_ABSTENCAO = "Não encontrei informações suficientes no manual do motor WEG W22 para responder a essa pergunta."
TEXTO_ESTADO_AUSENTE = "Nenhum estado operacional foi informado."
MARCADOR_ESTADO_OPERACIONAL = "ESTADO OPERACIONAL"
MARCADOR_CONTEXTO_MANUAL = "CONTEXTO DO MANUAL"
MARCADOR_PERGUNTA = "PERGUNTA"
MARCADOR_CONFIANCA = "Confiança:"
ANAFORES_ASSISTENTE = (
    "desse", "dessa", "desses", "dessas",
    "esse", "essa", "esses", "essas",
    "este", "esta", "estes", "estas", "isto",
    "deste", "desta", "destes", "destas",
    "nesse", "nessa", "nesses", "nessas",
    "neste", "nesta", "nestes", "nestas", "nisto",
    "aquele", "aquela", "aqueles", "aquelas", "aquilo",
    "daquele", "daquela", "daqueles", "daquelas",
    "naquele", "naquela", "naqueles", "naquelas",
    "isso", "ele", "ela", "eles", "elas",
)
PADRAO_CITACAO_ASSISTENTE = r"\[p\.\s*(?P<pagina>\d+),\s*seç\.\s*(?P<secao>[^\]]+)\]"
PADRAO_LINHA_CONFIANCA = r"(?im)^\s*Confiança:\s*.*$"
PROMPT_SISTEMA_ASSISTENTE = (
    "Você é um assistente técnico especialista em motores elétricos WEG W22. "
    "Responda somente com informações presentes no bloco CONTEXTO DO MANUAL. "
    "Cite cada afirmação factual usando [p. <página>, seç. <seção>] e use apenas páginas e seções presentes no contexto. "
    "Não use conhecimento externo e não invente números. "
    "Trate o bloco ESTADO OPERACIONAL como dado confiável do sistema; não reinterprete nem conteste seus valores ou severidades. "
    f"Se o contexto do manual não sustentar a resposta, responda exatamente: {FRASE_ABSTENCAO} "
    "Termine com uma linha Confiança: <Alta|Média|Baixa>."
)

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
