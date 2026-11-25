from __future__ import annotations

import os
import unicodedata
from pathlib import Path
from typing import Any

import pytest

from src.pln.config import NOVO
from src.pln.rag import Pagina, Retriever, chunk_novo, criar_retriever, extrair_paginas

pytestmark = pytest.mark.modelos


def _modelos_em_cache() -> bool:
    cache_configurado = os.environ.get("HF_HOME")
    cache_raiz = Path(cache_configurado) if cache_configurado else Path.home() / ".cache" / "huggingface"
    pasta_hub = cache_raiz / "hub"
    nomes_modelos = (
        "models--intfloat--multilingual-e5-base",
        "models--cross-encoder--mmarco-mMiniLMv2-L12-H384-v1",
    )
    return all((pasta_hub / nome).is_dir() for nome in nomes_modelos)


@pytest.fixture(scope="module")
def paginas_catalogo() -> list[Pagina]:
    return extrair_paginas()


@pytest.fixture(scope="module")
def retriever_modelos(paginas_catalogo: list[Pagina]) -> Retriever:
    return criar_retriever(chunk_novo(paginas_catalogo), NOVO)


def _normalizar(texto: str) -> str:
    decomposed = unicodedata.normalize("NFKD", texto.casefold())
    sem_acentos = "".join(caractere for caractere in decomposed if not unicodedata.combining(caractere))
    return " ".join(sem_acentos.split())


def _texto_extraido_da_pagina(pagina: Pagina) -> str:
    linhas_tabela = [linha for tabela in pagina.tabelas for linha in tabela.linhas]
    return " ".join((pagina.texto, pagina.texto_original, *linhas_tabela))


def _paginas_com_conceito(paginas: list[Pagina], conceito: str) -> set[int]:
    conceito_normalizado = _normalizar(conceito)
    return {
        pagina.pagina
        for pagina in paginas
        if conceito_normalizado in _normalizar(_texto_extraido_da_pagina(pagina))
    }


def _resultado_evidenciado_no_pdf(
    resultado: dict[str, Any], conceito: str, paginas_relevantes: set[int]
) -> bool:
    pagina_inicio = resultado.get("pagina")
    pagina_fim = resultado.get("pagina_fim")
    texto = resultado.get("texto")
    if not isinstance(pagina_inicio, int) or not isinstance(pagina_fim, int) or not isinstance(texto, str):
        return False
    if _normalizar(conceito) not in _normalizar(texto):
        return False
    return any(pagina_inicio <= pagina <= pagina_fim for pagina in paginas_relevantes)


@pytest.mark.skipif(not _modelos_em_cache(), reason="Os modelos multilíngues não estão baixados no cache local.")
@pytest.mark.parametrize(
    ("pergunta", "conceito"),
    (
        ("Qual é a classe de isolamento?", "classe de isolamento"),
        ("Qual é o grau de proteção?", "grau de protecao"),
    ),
)
def test_modelos_multilingues_recuperam_conceito_comprovado_no_pdf(
    pergunta: str,
    conceito: str,
    retriever_modelos: Retriever,
    paginas_catalogo: list[Pagina],
) -> None:
    resultados = retriever_modelos.buscar(pergunta, k_final=NOVO.k_final)
    paginas_relevantes = _paginas_com_conceito(paginas_catalogo, conceito)

    assert len(resultados) == NOVO.k_final
    assert paginas_relevantes
    assert any(_resultado_evidenciado_no_pdf(resultado, conceito, paginas_relevantes) for resultado in resultados)
