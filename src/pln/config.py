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
# Mantido em 0,15: no dev o hit@4 é 5/5 com 0, 0,05, 0,15 e 0,3, então não há evidência para mudá-lo.
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
# Calibrado só no dev (5 perguntas dentro + 5 fora do escopo): o maior score bruto fora do escopo é 0,41 e a
# pergunta dentro do escopo que fica abaixo do limiar pontua -3,91; 2,0 é o limiar mediano da faixa viável
# (0,5 a 3,5 na grade), a que mais se afasta das duas fronteiras. O hit@4 do dev é 5/5 para qualquer peso.
LIMIAR_ABSTENCAO = 2.0
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

AVALIACAO_RAG_FILE = DATA_DIR / "avaliacao_rag.json"
JUIZ_CALIBRACAO_FILE = DATA_DIR / "juiz_calibracao.json"
AVALIACAO_RECUPERACAO_OUTPUT_FILE = OUTPUT_DIR / "avaliacao_recuperacao.json"
AVALIACAO_RESPOSTAS_OUTPUT_FILE = OUTPUT_DIR / "avaliacao_respostas.json"
JUIZ_CALIBRACAO_OUTPUT_FILE = OUTPUT_DIR / "juiz_calibracao.json"
CENARIOS_FILE = DATA_DIR / "cenarios.json"
CENARIOS_OUTPUT_FILE = OUTPUT_DIR / "cenarios.json"
LIMITES_OUTPUT_FILE = OUTPUT_DIR / "limites.json"
# Regras de escolha do episódio e tipos de turno dos cenários (valores lidos de data/cenarios.json).
REGRA_MAIOR_SEVERIDADE = "maior_severidade"
REGRA_MENOR_VALOR = "menor_valor"
REGRA_JANELA_CALMA = "janela_calma"
TURNO_NATURAL = "natural"
TURNO_SEGUIMENTO = "seguimento"
TURNO_FORA_ESCOPO = "fora_escopo"
TURNO_CONTRADICAO = "contradicao_estado"
TURNO_EXTERNO = "conhecimento_externo"
TURNOS_POR_CENARIO = (TURNO_NATURAL, TURNO_SEGUIMENTO, TURNO_FORA_ESCOPO)
TURNOS_ADVERSARIAIS = (TURNO_CONTRADICAO, TURNO_EXTERNO)
IDS_CENARIOS = ("eletrica", "mecanica", "preventiva")
SPLIT_CENARIO = "cenario"
CATEGORIAS_LIMITE = ("fora_escopo", "alucinacao", "corpus", "metodo", "dados")
ORIGEM_RESPOSTAS = "avaliacao_respostas"
ORIGEM_CENARIOS = "cenarios"
ORIGEM_CALIBRACAO = "juiz_calibracao"
ORIGEM_DADOS = "dados"
ORIGENS_EVIDENCIA = (ORIGEM_RESPOSTAS, ORIGEM_CENARIOS, ORIGEM_CALIBRACAO, ORIGEM_DADOS)
ESCOPO_DENTRO = "dentro"
ESCOPO_FORA = "fora"
ESPERADO_ABSTENCAO = "abstencao"
CATEGORIAS_AVALIACAO = ("elétrica", "mecânica", "preventiva", "especificação")
PERGUNTAS_DENTRO_ESCOPO = 20
PERGUNTAS_FORA_ESCOPO = 5
PERGUNTAS_DENTRO_DEV = 5
KS_AVALIACAO = (1, 4)
CRITERIO_PAGINA = "pagina"
CRITERIO_ESTRITO = "estrita"
# Cenários sintéticos de estado: (prefixo da grandeza sem acento, severidade do primeiro alerta que casa).
ESTADOS_AVALIACAO = {
    "temperatura_critico": ("temperatura", "critico"),
    "corrente_critico": ("corrente", "critico"),
    "vibracao_critico": ("vibra", "critico"),
}
GRADE_LIMIAR_ABSTENCAO = (-4.0, -3.0, -2.0, -1.0, 0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0)
GRADE_PESO_ESTADO = (0.0, 0.05, 0.15, 0.3)

ROTULO_SUSTENTADA = "SUSTENTADA"
ROTULO_EXTERNA = "EXTERNA"
ROTULO_CONTRADIZ = "CONTRADIZ"
ROTULO_META = "META"
ROTULOS_AFIRMACAO = (ROTULO_SUSTENTADA, ROTULO_EXTERNA, ROTULO_CONTRADIZ, ROTULO_META)
COBERTURA_COBRE = "COBRE"
COBERTURA_PARCIAL = "PARCIAL"
COBERTURA_NAO_COBRE = "NAO_COBRE"
PONTOS_COBERTURA = {COBERTURA_COBRE: 1.0, COBERTURA_PARCIAL: 0.5, COBERTURA_NAO_COBRE: 0.0}
GUARDA_NUMERO = "guarda_numero"
GUARDA_MARCADOR = "guarda_marcador"
GUARDA_JUIZ_INVALIDO = "juiz_invalido"
PADRAO_ROTULO_AFIRMACAO = r"(?<![A-Z_])(SUSTENTADA|EXTERNA|CONTRADIZ|META)(?![A-Z_])"
PADRAO_ROTULO_COBERTURA = r"(?<![A-Z_])(NAO[ _]COBRE|PARCIAL|COBRE)(?![A-Z_])"
PADRAO_NUMERO_AFIRMACAO = r"(?<![A-Za-zÀ-ÿ\d])\d+(?:[.,]\d+)*"
PADRAO_MILHAR = r"\d{1,3}(?:\.\d{3})+"
PADRAO_COLCHETES = r"\[[^\]]*\]"
PADRAO_DIVISAO_FRASES = r"(?<=[.!?])\s+(?=[A-ZÀ-Þ0-9])"
PADRAO_MARCADOR_LISTA = r"^\s*(?:[-*•]|\d+[.)])\s+"
MARCADORES_CONHECIMENTO_EXTERNO = (
    "conhecimento geral",
    "conhecimento externo",
    "conhecimento previo",
    "nao consta",
    "nao esta no contexto",
    "nao esta no manual",
    "nao ha informacao",
    "nao ha mencao",
    "fora do contexto",
    "em geral",
    "de modo geral",
    "normalmente",
    "geralmente",
    "tipicamente",
    "usualmente",
    "comumente",
)
PROMPT_JUIZ_AFIRMACAO = (
    "Você é um verificador rigoroso de fidelidade. Receberá um CONTEXTO (trechos de um manual) e uma AFIRMAÇÃO. "
    "Classifique a afirmação com UM rótulo, considerando SOMENTE o CONTEXTO: "
    "SUSTENTADA: o contexto afirma ou implica diretamente a afirmação. "
    "EXTERNA: a afirmação não está no contexto, mesmo que seja verdadeira ou de conhecimento comum; "
    "inclui função, causa, material, valor ou procedimento que o contexto não traz. "
    "CONTRADIZ: o contexto afirma algo incompatível com a afirmação. "
    "META: não é afirmação factual sobre o motor (saudação, aviso, organização da resposta). "
    "Na dúvida entre SUSTENTADA e EXTERNA, responda EXTERNA. Responda apenas com o rótulo."
)
PROMPT_JUIZ_COBERTURA = (
    "Você avalia se uma RESPOSTA atende à PERGUNTA, comparando-a com a REFERÊNCIA correta. "
    "COBRE: a resposta traz a informação central da referência. "
    "PARCIAL: a resposta traz só parte da informação central ou mistura com informação irrelevante. "
    "NAO_COBRE: a resposta não traz a informação central, ou se recusa a responder. "
    "Responda apenas com COBRE, PARCIAL ou NAO_COBRE."
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
