from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from src.pln.assistente import Assistente
from src.pln.config import FRASE_ABSTENCAO, NIVEL_CONFIANCA_BAIXA
from src.pln.estado import EstadoOperacional


class FakeRetriever:
    def __init__(self, chunks: list[dict[str, Any]]) -> None:
        self.chunks = chunks
        self.consultas: list[str] = []
        self.estados: list[EstadoOperacional | None] = []

    def buscar(
        self, pergunta: str, estado: EstadoOperacional | None = None
    ) -> list[dict[str, Any]]:
        self.consultas.append(pergunta)
        self.estados.append(estado)
        return self.chunks


class FakeCompletionClient:
    def __init__(self, resposta: str) -> None:
        self.resposta = resposta
        self.chamadas: list[tuple[str, list[dict[str, str]]]] = []

    def complete(self, model_id: str, messages: list[dict[str, str]]) -> str:
        self.chamadas.append((model_id, messages))
        return self.resposta


def _chunk(score: float = 9.0, pagina: int = 13, secao: str = "4.1") -> dict[str, Any]:
    return {
        "id": f"chunk-{pagina}-{secao}",
        "pagina": pagina,
        "pagina_fim": pagina,
        "secao": secao,
        "secao_titulo": "Sistema de Ventilação",
        "texto": "O motor W22 possui sistema de ventilação descrito no manual.",
        "score_denso": 0.9,
        "score_rerank": 1.0,
        "score_rerank_bruto": score,
        "score_final": 1.0,
    }


def _estado() -> EstadoOperacional:
    return EstadoOperacional(
        "Motor W22",
        datetime(2026, 8, 22, 12, tzinfo=timezone.utc),
        (),
        "normal",
        True,
    )


def test_abstencao_nao_chama_llm_quando_score_fica_abaixo_do_limiar() -> None:
    retriever = FakeRetriever([_chunk(-4.0)])
    cliente = FakeCompletionClient("não deve ser usado")
    assistente = Assistente(retriever, cliente)

    resposta = assistente.responder("Qual é o grau de proteção?")

    assert resposta.abstencao is True
    assert resposta.texto.startswith(FRASE_ABSTENCAO)
    assert resposta.fontes == []
    assert resposta.confianca == NIVEL_CONFIANCA_BAIXA
    assert cliente.chamadas == []


def test_confianca_calculada_substitui_a_declarada_pelo_modelo() -> None:
    retriever = FakeRetriever(
        [_chunk(10.0), _chunk(9.0, pagina=14), _chunk(8.5, pagina=15)]
    )
    cliente = FakeCompletionClient("Dado do manual [p. 13, seç. 4.1].\nConfiança: Alta (95 %)")
    assistente = Assistente(retriever, cliente)

    resposta = assistente.responder("Qual é o grau de proteção do motor W22?")

    assert resposta.confianca == "Alta"
    assert resposta.texto.endswith("Confiança: Alta")
    assert "95 %" not in resposta.texto


def test_citacao_de_pagina_fora_do_contexto_e_sinalizada() -> None:
    retriever = FakeRetriever([_chunk()])
    cliente = FakeCompletionClient("Dado do manual [p. 99, seç. 4.1].")
    assistente = Assistente(retriever, cliente)

    resposta = assistente.responder("Qual é o grau de proteção do motor W22?")

    assert resposta.citou is True
    assert resposta.citacao_invalida is True
    assert resposta.fontes == []


def test_pergunta_de_seguimento_reusa_a_pergunta_anterior_na_busca() -> None:
    retriever = FakeRetriever([_chunk()])
    cliente = FakeCompletionClient("Informação do manual.")
    assistente = Assistente(retriever, cliente)
    pergunta_anterior = "Quais verificações o manual recomenda para o motor W22?"
    pergunta_seguimento = "E quais as causas desse problema?"

    assistente.responder(pergunta_anterior)
    assistente.responder(pergunta_seguimento)

    assert retriever.consultas[0] == pergunta_anterior
    assert retriever.consultas[1] == f"{pergunta_anterior} {pergunta_seguimento}"


@pytest.mark.parametrize(
    "pergunta_seguimento",
    ("E o que essa proteção significa?", "E o que esse grau significa?"),
    ids=("essa", "esse"),
)
def test_seguimento_com_essa_ou_esse_reusa_a_pergunta_anterior(
    pergunta_seguimento: str,
) -> None:
    retriever = FakeRetriever([_chunk()])
    cliente = FakeCompletionClient("Informação do manual.")
    assistente = Assistente(retriever, cliente)
    pergunta_anterior = "Qual é o grau de proteção do motor WEG W22?"

    assistente.responder(pergunta_anterior)
    assistente.responder(pergunta_seguimento)

    assert retriever.consultas[-1] == f"{pergunta_anterior} {pergunta_seguimento}"


def test_pergunta_curta_reusa_a_pergunta_anterior_na_busca() -> None:
    retriever = FakeRetriever([_chunk()])
    cliente = FakeCompletionClient("Informação do manual.")
    assistente = Assistente(retriever, cliente)
    pergunta_anterior = "Quais dados o manual apresenta para monitorar a corrente elétrica?"
    pergunta_seguimento = "E quais valores?"

    assistente.responder(pergunta_anterior)
    assistente.responder(pergunta_seguimento)

    assert retriever.consultas[-1] == f"{pergunta_anterior} {pergunta_seguimento}"


def test_estado_e_enviado_ao_retriever_e_marcado_como_dado_confiavel() -> None:
    retriever = FakeRetriever([_chunk()])
    cliente = FakeCompletionClient("Informação do manual.")
    assistente = Assistente(retriever, cliente)
    estado = _estado()

    resposta = assistente.responder("Qual é o grau de proteção do motor W22?", estado)
    mensagens = cliente.chamadas[0][1]

    assert retriever.estados == [estado]
    assert "dado confiável do sistema" in mensagens[0]["content"]
    assert estado.texto() in mensagens[-1]["content"]
    assert resposta.estado_texto == estado.texto()


def test_historico_do_prompt_fica_limitado_a_tres_turnos() -> None:
    retriever = FakeRetriever([_chunk()])
    cliente = FakeCompletionClient("Informação do manual.")
    assistente = Assistente(retriever, cliente)
    perguntas = [f"Quais dados técnicos existem sobre o tópico {indice} do manual?" for indice in range(5)]

    for pergunta in perguntas:
        assistente.responder(pergunta)

    mensagens_quinto_turno = cliente.chamadas[4][1]
    conteudo_historico = " ".join(item["content"] for item in mensagens_quinto_turno)

    assert perguntas[0] not in conteudo_historico
    assert perguntas[1] in conteudo_historico
    assert perguntas[3] in conteudo_historico


def test_resposta_sem_citacoes_usa_os_chunks_recuperados_como_fontes() -> None:
    retriever = FakeRetriever([_chunk()])
    cliente = FakeCompletionClient("O manual descreve o motor W22.")
    assistente = Assistente(retriever, cliente)

    resposta = assistente.responder("Qual é o grau de proteção do motor W22?")

    assert resposta.citou is False
    assert resposta.fontes == [
        {
            "pagina": 13,
            "secao": "4.1",
            "secao_titulo": "Sistema de Ventilação",
            "chunk_id": "chunk-13-4.1",
        }
    ]


def test_reiniciar_limpa_a_memoria_de_conversa() -> None:
    retriever = FakeRetriever([_chunk()])
    cliente = FakeCompletionClient("Informação do manual.")
    assistente = Assistente(retriever, cliente)
    pergunta_anterior = "Quais verificações o manual recomenda para o motor W22?"

    assistente.responder(pergunta_anterior)
    assistente.reiniciar()
    assistente.responder("E quais as causas desse problema?")

    assert retriever.consultas[-1] == "E quais as causas desse problema?"
    assert pergunta_anterior not in " ".join(
        item["content"] for item in cliente.chamadas[-1][1]
    )
