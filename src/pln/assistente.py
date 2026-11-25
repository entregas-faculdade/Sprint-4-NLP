"""Generate troubleshooting answers grounded in retrieved WEG W22 passages."""

from __future__ import annotations

import logging
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from src.pln.config import (
    ANAFORES_ASSISTENTE,
    FAIXAS_CONFIANCA,
    FRASE_ABSTENCAO,
    LIMIAR_ABSTENCAO,
    LIMIAR_PALAVRAS_CONSULTA,
    MARCADOR_CONFIANCA,
    MARCADOR_CONTEXTO_MANUAL,
    MARCADOR_ESTADO_OPERACIONAL,
    MARCADOR_PERGUNTA,
    MEMORIA_TURNOS,
    MODELO_GERADOR,
    NIVEL_CONFIANCA_BAIXA,
    PADRAO_CITACAO_ASSISTENTE,
    PADRAO_LINHA_CONFIANCA,
    PROMPT_SISTEMA_ASSISTENTE,
    TEXTO_ESTADO_AUSENTE,
)
from src.pln.estado import EstadoOperacional
from src.pln.llm import create_openrouter_client

LOGGER = logging.getLogger(__name__)


class RetrieverPort(Protocol):
    """Public retrieval surface consumed by the assistant."""

    def buscar(
        self, pergunta: str, estado: EstadoOperacional | None = None
    ) -> list[dict[str, Any]]:
        """Return ranked manual passages with source metadata and scores."""


class CompletionClient(Protocol):
    """Chat completion boundary used by the assistant."""

    def complete(self, model_id: str, messages: list[dict[str, str]]) -> str:
        """Return a completion for the configured model and messages."""


@dataclass(frozen=True)
class Resposta:
    """Answer text and deterministic metadata for one troubleshooting turn."""

    texto: str
    fontes: list[dict[str, Any]]
    confianca: str
    abstencao: bool
    citacao_invalida: bool
    citou: bool
    modelo: str
    consulta_usada: str
    chunks: list[dict[str, Any]]
    estado_texto: str


class Assistente:
    """Retrieve manual evidence, abstain when weak, and rewrite supported answers."""

    def __init__(
        self, retriever: RetrieverPort, cliente_llm: CompletionClient | None = None
    ) -> None:
        self._retriever = retriever
        self._cliente = cliente_llm or create_openrouter_client()
        self._historico: list[dict[str, str]] = []

    def responder(
        self, pergunta: str, estado: EstadoOperacional | None = None
    ) -> Resposta:
        pergunta_atual = pergunta.strip()
        if not pergunta_atual:
            raise ValueError("A pergunta não pode estar vazia.")
        consulta = _consulta_com_memoria(pergunta_atual, self._historico)
        resultados = self._retriever.buscar(consulta, estado=estado)
        chunks = _validar_chunks(resultados)
        estado_texto = estado.texto() if estado is not None else TEXTO_ESTADO_AUSENTE
        if not _recuperacao_sustenta(chunks):
            resposta = _resposta_abstencao(consulta, chunks, estado_texto)
            self._guardar_turno(pergunta_atual, resposta.texto)
            return resposta
        confianca = _calcular_confianca(chunks)
        mensagens = _montar_mensagens(
            self._historico, chunks, estado_texto, pergunta_atual
        )
        texto_gerado = self._cliente.complete(MODELO_GERADOR, mensagens)
        if not texto_gerado.strip():
            raise ValueError("O gerador retornou uma resposta vazia.")
        texto_final = _substituir_confianca(texto_gerado, confianca)
        fontes, citou, citacao_invalida = _extrair_fontes(texto_final, chunks)
        resposta = Resposta(
            texto_final,
            fontes,
            confianca,
            False,
            citacao_invalida,
            citou,
            MODELO_GERADOR,
            consulta,
            chunks,
            estado_texto,
        )
        self._guardar_turno(pergunta_atual, resposta.texto)
        return resposta

    def reiniciar(self) -> None:
        """Clear the short-term conversation history."""
        self._historico.clear()

    def _guardar_turno(self, pergunta: str, resposta: str) -> None:
        self._historico.extend(
            ({"role": "user", "content": pergunta}, {"role": "assistant", "content": resposta})
        )
        limite = MEMORIA_TURNOS * 2
        self._historico = self._historico[-limite:] if limite else []


def _validar_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not chunks:
        return []
    copias = [dict(chunk) for chunk in chunks]
    for chunk in copias:
        if chunk.get("pagina") is None or not chunk.get("secao"):
            raise ValueError("O chunk recuperado não contém página e seção para citação.")
        _score_bruto(chunk)
    return copias


def _score_bruto(chunk: Mapping[str, Any]) -> float:
    try:
        score = float(chunk["score_rerank_bruto"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("O chunk recuperado não contém score_rerank_bruto válido.") from error
    if not math.isfinite(score):
        raise ValueError("O chunk recuperado contém score_rerank_bruto não finito.")
    return score


def _recuperacao_sustenta(chunks: list[dict[str, Any]]) -> bool:
    return bool(chunks) and _score_bruto(chunks[0]) >= LIMIAR_ABSTENCAO


def _calcular_confianca(chunks: list[dict[str, Any]]) -> str:
    melhor_score = _score_bruto(chunks[0])
    quantidade_sustentada = sum(
        _score_bruto(chunk) >= LIMIAR_ABSTENCAO for chunk in chunks
    )
    for nivel, faixa in FAIXAS_CONFIANCA.items():
        if (
            melhor_score >= faixa["score_minimo"]
            and quantidade_sustentada >= faixa["chunks_minimos"]
        ):
            return nivel
    return NIVEL_CONFIANCA_BAIXA


def _consulta_com_memoria(
    pergunta: str, historico: list[dict[str, str]]
) -> str:
    anterior = next(
        (item["content"] for item in reversed(historico) if item["role"] == "user"),
        None,
    )
    if anterior is None or not _precisa_contexto(pergunta):
        return pergunta
    return f"{anterior} {pergunta}"


def _precisa_contexto(pergunta: str) -> bool:
    if len(pergunta.split()) < LIMIAR_PALAVRAS_CONSULTA:
        return True
    pergunta_normalizada = pergunta.casefold()
    return any(
        re.search(rf"\b{re.escape(anafora)}\b", pergunta_normalizada)
        for anafora in ANAFORES_ASSISTENTE
    )


def _montar_mensagens(
    historico: list[dict[str, str]],
    chunks: list[dict[str, Any]],
    estado_texto: str,
    pergunta: str,
) -> list[dict[str, str]]:
    mensagens = [{"role": "system", "content": PROMPT_SISTEMA_ASSISTENTE}]
    limite = MEMORIA_TURNOS * 2
    if limite:
        mensagens.extend(historico[-limite:])
    mensagens.append(
        {
            "role": "user",
            "content": _montar_mensagem_usuario(chunks, estado_texto, pergunta),
        }
    )
    return mensagens


def _montar_mensagem_usuario(
    chunks: list[dict[str, Any]], estado_texto: str, pergunta: str
) -> str:
    contexto = "\n\n".join(
        f"[p. {chunk['pagina']}, seç. {chunk['secao']}] {chunk['texto']}"
        for chunk in chunks
    )
    return (
        f"{MARCADOR_ESTADO_OPERACIONAL}\n{estado_texto}\n\n"
        f"{MARCADOR_CONTEXTO_MANUAL}\n{contexto}\n\n"
        f"{MARCADOR_PERGUNTA}\n{pergunta}"
    )


def _substituir_confianca(texto: str, confianca: str) -> str:
    linha = f"{MARCADOR_CONFIANCA} {confianca}"
    if re.search(PADRAO_LINHA_CONFIANCA, texto):
        return re.sub(PADRAO_LINHA_CONFIANCA, linha, texto).strip()
    return f"{texto.rstrip()}\n{linha}"


def _extrair_fontes(
    texto: str, chunks: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], bool, bool]:
    citacoes = list(re.finditer(PADRAO_CITACAO_ASSISTENTE, texto))
    if not citacoes:
        return [_fonte(chunk) for chunk in chunks], False, False
    por_par: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for chunk in chunks:
        par = (int(chunk["pagina"]), str(chunk["secao"]).strip())
        por_par.setdefault(par, []).append(chunk)
    return _resolver_citacoes(citacoes, por_par)


def _resolver_citacoes(
    citacoes: list[re.Match[str]],
    por_par: dict[tuple[int, str], list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], bool, bool]:
    fontes: list[dict[str, Any]] = []
    fontes_incluidas: set[tuple[int, str, str]] = set()
    invalida = False
    for citacao in citacoes:
        par = (int(citacao.group("pagina")), citacao.group("secao").strip())
        candidatos = por_par.get(par)
        if not candidatos:
            invalida = True
            continue
        for chunk in candidatos:
            chave = (par[0], par[1], str(chunk["id"]))
            if chave not in fontes_incluidas:
                fontes.append(_fonte(chunk))
                fontes_incluidas.add(chave)
    if invalida:
        LOGGER.warning("O gerador citou página ou seção ausente dos chunks recuperados.")
    return fontes, True, invalida


def _fonte(chunk: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "pagina": int(chunk["pagina"]),
        "secao": str(chunk["secao"]),
        "secao_titulo": chunk.get("secao_titulo"),
        "chunk_id": str(chunk["id"]),
    }


def _resposta_abstencao(
    consulta: str, chunks: list[dict[str, Any]], estado_texto: str
) -> Resposta:
    texto = _substituir_confianca(FRASE_ABSTENCAO, NIVEL_CONFIANCA_BAIXA)
    return Resposta(
        texto,
        [],
        NIVEL_CONFIANCA_BAIXA,
        True,
        False,
        False,
        MODELO_GERADOR,
        consulta,
        chunks,
        estado_texto,
    )
