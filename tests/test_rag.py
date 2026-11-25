from __future__ import annotations

import re
import sys
import unicodedata
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence
from uuid import uuid4

import pytest

from src.pln.alertas import Alerta
from src.pln.config import CHUNK_MAX, LEGADO, NOVO
from src.pln.estado import construir_estado_operacional
from src.pln.rag import (
    Chunk,
    DependenciasRAG,
    Pagina,
    chunk_legado,
    chunk_novo,
    criar_retriever,
    extrair_paginas,
    carregar_termos_estado,
)


class FakeTable:
    def __init__(self) -> None:
        self.bbox = (10.0, 40.0, 95.0, 90.0)
        self.header = SimpleNamespace(names=["Característica", "Valor"])

    def extract(self) -> list[list[str | None]]:
        return [
            ["Característica", "Valor"],
            ["Grau de proteção", "IPW55"],
        ]


class FakePage:
    def __init__(self, include_footer: bool = True) -> None:
        self.tabela = FakeTable()
        self.blocos = [
            (0, 0, 50, 10, "www.weg.net"),
            (0, 20, 100, 30, "4.1 Sistema de Ventilação"),
            (10, 40, 95, 90, "Grau de proteção IPW55"),
            (0, 100, 110, 110, "Motor Elétrico Trifásico W22 | 13"),
            (0, 112, 90, 120, "www.weg.net/w22"),
        ]
        if not include_footer:
            self.blocos = self.blocos[1:3]

    def get_text(self, option: str = "text", sort: bool = False) -> Any:
        if option == "blocks":
            return self.blocos
        return "www.weg.net\n4.1 Sistema de Ventilação\nMotor Elétrico Trifásico W22 | 13"

    def find_tables(self, use_layout: bool) -> Any:
        assert not use_layout
        return SimpleNamespace(tables=[self.tabela])


class FakeDocument:
    def __init__(self, paginas: Sequence[FakePage]) -> None:
        self.paginas = paginas
        self.fechado = False

    def __iter__(self):
        return iter(self.paginas)

    def __len__(self) -> int:
        return len(self.paginas)

    def close(self) -> None:
        self.fechado = True


class FakeEmbedding:
    def __init__(self) -> None:
        self.textos_codificados: list[str] = []

    def encode(self, sentences: Sequence[str]) -> list[list[float]]:
        self.textos_codificados.extend(sentences)
        return [[1.0, float(len(sentence))] for sentence in sentences]


class FakeReranker:
    def predict(self, pairs: Sequence[tuple[str, str]]) -> list[float]:
        return [0.9, 0.8, 0.79, 0.1][: len(pairs)]


class FakeCollection:
    def __init__(self) -> None:
        self.documentos = ["Documento 1", "Documento 2", "Documento 3", "Documento 4"]
        self.metadados = [
            {"pagina": 13, "pagina_fim": 13, "secao": "4.1", "secao_titulo": "Sistema de Ventilação"},
            {"pagina": 25, "pagina_fim": 25, "secao": "8", "secao_titulo": "Tensão / Frequência"},
            {"pagina": 37, "pagina_fim": 37, "secao": "11", "secao_titulo": "Proteção Térmica do Motor"},
            {"pagina": 46, "pagina_fim": 46, "secao": "17", "secao_titulo": "Dados Mecânicos"},
        ]

    def add(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        self.indexados = (ids, documents, embeddings, metadatas)

    def query(self, query_embeddings: list[list[float]], n_results: int) -> dict[str, Any]:
        return {
            "ids": [[f"chunk-{indice}" for indice in range(1, n_results + 1)]],
            "documents": [self.documentos[:n_results]],
            "metadatas": [self.metadados[:n_results]],
            "distances": [[0.05, 0.1, 0.2, 0.3][:n_results]],
        }


class FakeVectorClient:
    def __init__(self) -> None:
        self.colecao = FakeCollection()
        self.configuracoes: list[tuple[str, dict[str, str]]] = []

    def create_collection(self, name: str, metadata: dict[str, str]) -> FakeCollection:
        self.configuracoes.append((name, metadata))
        return self.colecao


def _normalizar(texto: str) -> str:
    decomposed = unicodedata.normalize("NFKD", texto.casefold())
    sem_marcas = "".join(caractere for caractere in decomposed if not unicodedata.combining(caractere))
    return " ".join(sem_marcas.split())


def _paginas_com_texto(paginas: Sequence[Pagina], texto: str) -> set[int]:
    texto_normalizado = _normalizar(texto)
    return {
        pagina.pagina
        for pagina in paginas
        if texto_normalizado
        in _normalizar(
            " ".join(
                [pagina.texto_original]
                + [linha for tabela in pagina.tabelas for linha in tabela.linhas]
            )
        )
    }


def _chunk_cobre_pagina(chunk: Chunk, pagina: int) -> bool:
    return (
        chunk.pagina is not None
        and chunk.pagina_fim is not None
        and chunk.pagina <= pagina <= chunk.pagina_fim
    )


def _criar_alerta_corrente(inicio: datetime) -> Alerta:
    fim = inicio + timedelta(minutes=5)
    return Alerta(
        id="A-0042",
        ativo="WEG W22 (fábrica)",
        sensor_id="sensor-1",
        grandeza="Corrente elétrica por fase",
        unidade="A",
        severidade="critico",
        inicio=inicio,
        fim=fim,
        duracao_min=5.0,
        n_leituras=3,
        valor_max=160.0,
        valor_medio=150.0,
        limiar_nominal=125.0,
        limiar_alerta=140.0,
        limiar_critico=160.0,
        desvio_abs=35.0,
        desvio_pct=28.0,
        ids_leitura=("L-1", "L-2", "L-3"),
    )


def test_extracao_remove_cabecalho_e_serializa_tabela(tmp_path: Path) -> None:
    arquivo = tmp_path / "catalogo.pdf"
    arquivo.touch()
    documento = FakeDocument([FakePage()])

    paginas = extrair_paginas(arquivo, lambda _: documento)

    assert paginas[0].pagina == 13
    assert "www.weg.net" not in paginas[0].texto
    assert paginas[0].tabelas[0].linhas == (
        "Característica: Grau de proteção; Valor: IPW55",
    )
    assert documento.fechado is True


def test_capa_sem_pagina_impressa_usa_indice_fisico(tmp_path: Path) -> None:
    arquivo = tmp_path / "catalogo.pdf"
    arquivo.touch()

    paginas = extrair_paginas(arquivo, lambda _: FakeDocument([FakePage(include_footer=False)]))

    assert paginas[0].pagina == 1


def test_pagina_interna_sem_numero_impresso_e_rejeitada(tmp_path: Path) -> None:
    arquivo = tmp_path / "catalogo.pdf"
    arquivo.touch()
    documento = FakeDocument(
        [FakePage(include_footer=False), FakePage(include_footer=False), FakePage()]
    )

    with pytest.raises(ValueError, match="número impresso"):
        extrair_paginas(arquivo, lambda _: documento)

    assert documento.fechado is True


def test_chunk_novo_preserva_secao_pagina_limite_e_isolamento() -> None:
    texto_longo = " ".join(["Ventilação reduz o ruído do motor."] * 90)
    pagina_sumario = Pagina(
        7,
        "4 Ventilação ........ 13\n4.1 Sistema de Ventilação ........ 13\n4.2 Dados Elétricos ........ 13",
        "",
    )
    pagina = Pagina(
        13,
        f"4.1 Sistema de Ventilação\n{texto_longo}\n4.2 Dados Elétricos\n"
        "Tensão nominal do motor deve ser verificada antes da partida e da operação segura.",
        "",
    )

    chunks = chunk_novo([pagina_sumario, pagina])
    chunks_4_1 = [chunk for chunk in chunks if chunk.secao == "4.1"]
    chunks_4_2 = [chunk for chunk in chunks if chunk.secao == "4.2"]

    assert len(chunks_4_1) > 1
    assert chunks_4_2
    assert all(len(chunk.texto) <= CHUNK_MAX for chunk in chunks)
    assert all(chunk.pagina == 13 and chunk.pagina_fim == 13 for chunk in chunks)
    assert all(chunk.secao_titulo and chunk.secao for chunk in chunks)
    assert all("4.2 Dados Elétricos" not in chunk.texto for chunk in chunks_4_1)


def test_chunk_legado_mantem_paragrafos_sem_metadados() -> None:
    chunks = chunk_legado("Parágrafo antigo.\n\nSegundo parágrafo.")

    assert len(chunks) == 1
    assert chunks[0].texto == "Parágrafo antigo.\n\nSegundo parágrafo."
    assert chunks[0].pagina is None
    assert chunks[0].secao is None
    assert LEGADO.k_final == 2


def test_pdf_real_preserva_pagina_13_secao_4_1_e_metadados(paginas_catalogo: list[Pagina]) -> None:
    assert len(paginas_catalogo) == 52
    pagina_13 = next(pagina for pagina in paginas_catalogo if pagina.pagina == 13)
    chunks = chunk_novo(paginas_catalogo)

    assert "4.1" in pagina_13.texto
    assert any(chunk.pagina == 13 and chunk.secao == "4.1" for chunk in chunks)
    assert all(1 <= chunk.pagina <= 52 for chunk in chunks if chunk.pagina is not None)
    assert all(chunk.pagina and chunk.secao and chunk.secao_titulo for chunk in chunks)
    assert all(len(chunk.texto) <= CHUNK_MAX for chunk in chunks)


def test_pdf_real_usa_titulos_da_hierarquia_do_sumario(paginas_catalogo: list[Pagina]) -> None:
    chunks = chunk_novo(paginas_catalogo)
    titulos_invalidos = [
        chunk.secao_titulo
        for chunk in chunks
        if "..." in chunk.secao_titulo
        or chunk.secao_titulo.startswith("-")
        or not chunk.secao_titulo[0].isupper()
    ]

    assert titulos_invalidos == []
    assert all(int(chunk.secao.split(".")[0]) <= 22 for chunk in chunks)
    assert all(chunk.pagina >= 8 for chunk in chunks if chunk.secao == "1")
    assert all(chunk.secao_titulo == "Versões Disponíveis" for chunk in chunks if chunk.secao == "1")
    assert not any("........" in chunk.texto for chunk in chunks)
    assert not any(
        chunk.secao_titulo in {"- Valores para esforços radiais", "não possuem olhal de"}
        for chunk in chunks
    )


def test_pdf_real_serializa_tabelas_legiveis_sem_colunas_genericas(
    paginas_catalogo: list[Pagina],
) -> None:
    chunks = chunk_novo(paginas_catalogo)
    chunks_com_coluna_generica = [
        chunk for chunk in chunks if re.search(r"\bColuna \d+\b", chunk.texto)
    ]
    paginas_com_protecao = _paginas_com_texto(paginas_catalogo, "Grau de proteção")
    paginas_com_carcaca = _paginas_com_texto(paginas_catalogo, "Carcaça 200")
    paginas_com_conjugado = _paginas_com_texto(paginas_catalogo, "Conjugado Nominal")

    assert 24 in paginas_com_protecao
    assert paginas_com_carcaca
    assert 37 in paginas_com_conjugado
    assert any(
        "Grau de proteção" in chunk.texto and _chunk_cobre_pagina(chunk, 24)
        for chunk in chunks
    )
    assert any(
        "Carcaça 200" in chunk.texto
        and any(_chunk_cobre_pagina(chunk, pagina) for pagina in paginas_com_carcaca)
        for chunk in chunks
    )
    assert any(
        "Conjugado Nominal" in chunk.texto
        and "Conjugado de Partida" in chunk.texto
        and "Corrente Nominal" in chunk.texto
        and _chunk_cobre_pagina(chunk, 37)
        for chunk in chunks
    )
    assert any("Classe de Isolamento" in chunk.texto for chunk in chunks)
    assert len(chunks_com_coluna_generica) / len(chunks) < 0.10


def test_secoes_alvo_ocorrem_no_pdf_sem_excesso_de_cobertura(paginas_catalogo: list[Pagina]) -> None:
    chunks = chunk_novo(paginas_catalogo)
    termos_estado = carregar_termos_estado()
    titulos = [_normalizar(chunk.secao_titulo or "") for chunk in chunks]
    secoes_alvo = {secao for item in termos_estado.values() for secao in item.secoes_alvo}
    coberturas = {
        secao: sum(titulo == _normalizar(secao) for titulo in titulos) / len(chunks)
        for secao in secoes_alvo
    }

    assert all(cobertura > 0 for cobertura in coberturas.values())
    assert all(cobertura <= 0.25 for cobertura in coberturas.values())


def test_presets_mantem_k_distintos_do_legado_e_do_novo() -> None:
    assert (LEGADO.k_busca, LEGADO.k_final) == (5, 2)
    assert NOVO.k_busca >= 20
    assert (NOVO.k_busca, NOVO.k_final) != (LEGADO.k_busca, LEGADO.k_final)


def test_todos_os_termos_de_estado_ocorrem_no_pdf(paginas_catalogo: list[Pagina]) -> None:
    termos = carregar_termos_estado()
    texto_catalogo = _normalizar(
        " ".join(
            [pagina.texto for pagina in paginas_catalogo]
            + [linha for pagina in paginas_catalogo for tabela in pagina.tabelas for linha in tabela.linhas]
        )
    )

    ausentes = [termo for item in termos.values() for termo in item.termos_consulta if _normalizar(termo) not in texto_catalogo]

    assert ausentes == []


def test_retriever_expande_consulta_e_aplica_boost_de_secao() -> None:
    embedding = FakeEmbedding()
    cliente = FakeVectorClient()
    colecao = cliente.colecao
    dependencias = DependenciasRAG(embedding, FakeReranker(), cliente)
    chunks = [Chunk(f"chunk-{indice}", 13, 13, "4.1", "Sistema de Ventilação", f"Passagem {indice}") for indice in range(1, 5)]
    retriever = criar_retriever(chunks, NOVO, dependencias)
    instante = datetime(2026, 8, 22, 12, tzinfo=timezone.utc)
    estado = construir_estado_operacional([_criar_alerta_corrente(instante)], instante)
    pergunta = "Quais dados elétricos são relevantes?"

    sem_estado = retriever.buscar(pergunta, estado=None)
    sem_estado_repetido = retriever.buscar(pergunta, estado=None)
    com_estado = retriever.buscar(pergunta, estado=estado)

    assert sem_estado == sem_estado_repetido
    assert sem_estado[0]["id"] == "chunk-1"
    assert com_estado[0]["id"] == "chunk-2"
    assert embedding.textos_codificados[-1].startswith("query: " + pergunta)
    assert "corrente nominal" in embedding.textos_codificados[-1]
    assert all(item["score_final"] == item["score_rerank"] for item in sem_estado)
    assert com_estado[0]["score_final"] > com_estado[0]["score_rerank"]
    assert cliente.configuracoes[0][1] == {"hnsw:space": "cosine"}
    assert colecao.indexados[3][0]["pagina"] == 13


def test_retriever_preserva_score_bruto_e_score_normalizado() -> None:
    dependencias = DependenciasRAG(FakeEmbedding(), FakeReranker(), FakeVectorClient())
    chunks = [
        Chunk(f"chunk-{indice}", 13, 13, "4.1", "Sistema de Ventilação", f"Passagem {indice}")
        for indice in range(1, 5)
    ]
    retriever = criar_retriever(chunks, NOVO, dependencias)

    resultados = retriever.buscar("Consultar o manual do motor W22")

    assert [item["score_rerank_bruto"] for item in resultados] == [0.9, 0.8, 0.79, 0.1]
    assert [item["score_rerank"] for item in resultados] == pytest.approx(
        [1.0, 0.875, 0.8625, 0.0]
    )


def test_importacao_rag_nao_carrega_clientes_de_modelo() -> None:
    assert "chromadb" not in sys.modules
    assert "sentence_transformers" not in sys.modules


def test_chromadb_real_indexa_e_consulta_chunks_com_metadados_correspondentes() -> None:
    import chromadb

    nome_colecao = f"teste-rag-{uuid4().hex}"
    preset = replace(NOVO, colecao=nome_colecao)
    chunks = [
        Chunk("chroma-1", 11, 11, "2.1", "Dados elétricos", "Documento associado à página 11"),
        Chunk("chroma-2", 22, 22, "4.2", "Proteção térmica", "Documento associado à página 22"),
        Chunk("chroma-3", 33, 33, "7.3", "Dados mecânicos", "Documento associado à página 33"),
    ]
    dependencias = DependenciasRAG(
        embedding=FakeEmbedding(),
        reranker=FakeReranker(),
        cliente_vetorial=chromadb.EphemeralClient(),
        termos_estado={},
    )
    retriever = criar_retriever(chunks, preset, dependencias)

    resultados = retriever.buscar("Consultar dados técnicos", k_busca=3, k_final=3)

    esperados = {
        chunk.id: (chunk.texto, chunk.pagina, chunk.pagina_fim, chunk.secao, chunk.secao_titulo)
        for chunk in chunks
    }
    obtidos = {
        item["id"]: (
            item["texto"],
            item["pagina"],
            item["pagina_fim"],
            item["secao"],
            item["secao_titulo"],
        )
        for item in resultados
    }

    assert len(resultados) == 3
    assert obtidos == esperados


def test_chromadb_real_indexa_e_consulta_chunks_sem_metadados() -> None:
    import chromadb

    nome_colecao = f"teste-rag-{uuid4().hex}"
    preset = replace(LEGADO, colecao=nome_colecao)
    chunks = [Chunk(f"legado-{indice}", None, None, None, None, f"Documento legado {indice}") for indice in range(1, 4)]
    dependencias = DependenciasRAG(
        embedding=FakeEmbedding(),
        reranker=FakeReranker(),
        cliente_vetorial=chromadb.EphemeralClient(),
        termos_estado={},
    )
    retriever = criar_retriever(chunks, preset, dependencias)

    resultados = retriever.buscar("Consultar documentos legados", k_busca=3, k_final=3)

    assert {item["id"]: item["texto"] for item in resultados} == {chunk.id: chunk.texto for chunk in chunks}
    assert all(item["pagina"] is None and item["secao"] is None for item in resultados)


@pytest.fixture(scope="module")
def paginas_catalogo() -> list[Pagina]:
    return extrair_paginas()
