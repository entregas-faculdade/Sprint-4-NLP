"""Extract, index, and retrieve W22 catalog passages with traceable metadata."""

from __future__ import annotations

import json
import math
import re
import textwrap
import unicodedata
from bisect import bisect_left, bisect_right
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from src.pln.config import (
    CHROMA_DISTANCE_COSINE,
    CHROMA_DISTANCE_KEY,
    CHUNK_MIN,
    LEGADO,
    NOVO,
    PDF_CATALOGO_FILE,
    PresetRAG,
    TABLE_CAPTION_MAX_GAP,
    TERMOS_ESTADO_FILE,
)
from src.pln.estado import EstadoOperacional

TOC_PATTERN = re.compile(
    r"^\s*(?P<numero>\d+(?:\.\d+)*)(?:\.)?\s+(?P<titulo>.+?)\s*\.{3,}\s*\d+\s*$"
)
SECTION_PATTERN = re.compile(
    r"^\s*(?P<numero>\d+(?:\.\d+)*)(?:\.\s*|\s+|(?=[A-ZÀ-Þ]))(?P<titulo>\S.*)$"
)
DOTTED_LEADER_PATTERN = re.compile(r"\.{3,}")
NOTE_ITEM_PATTERN = re.compile(r"^\s*\d+\s*[-–—]\s+")
SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")


class EmbeddingModel(Protocol):
    """Minimal sentence-embedding interface injected into the retriever."""

    def encode(self, sentences: Sequence[str]) -> Any:
        """Encode a batch of passages or queries into vectors."""


class Reranker(Protocol):
    """Minimal pair-scoring interface injected into the retriever."""

    def predict(self, pairs: Sequence[tuple[str, str]]) -> Any:
        """Return one relevance score for each question-passage pair."""


class VectorCollection(Protocol):
    """Collection surface used from ChromaDB or a deterministic fake."""

    def add(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """Store passages, vectors, identifiers, and optional metadata."""

    def query(self, query_embeddings: list[list[float]], n_results: int) -> Mapping[str, Any]:
        """Return nearest passages and their metadata and cosine distances."""


@dataclass(frozen=True)
class TabelaExtraida:
    """Serialized table rows and the caption found directly below the table."""

    linhas: tuple[str, ...]
    legenda: str
    posicao: float


@dataclass(frozen=True)
class Pagina:
    """A cleaned, printable PDF page plus its original text for legacy chunking."""

    pagina: int
    texto: str
    texto_original: str
    tabelas: tuple[TabelaExtraida, ...] = ()


@dataclass(frozen=True)
class Chunk:
    """A passage and its optional source metadata."""

    id: str
    pagina: int | None
    pagina_fim: int | None
    secao: str | None
    secao_titulo: str | None
    texto: str


@dataclass(frozen=True)
class TermosEstado:
    """Query terms and target section names for one sensor quantity."""

    dominio_falha: str
    termos_consulta: tuple[str, ...]
    secoes_alvo: tuple[str, ...]


@dataclass(frozen=True)
class DependenciasRAG:
    """Replaceable model and vector-store adapters for offline testing."""

    embedding: EmbeddingModel | None = None
    reranker: Reranker | None = None
    cliente_vetorial: Any | None = None
    termos_estado: Mapping[str, TermosEstado] | None = None


@dataclass(frozen=True)
class ComponentesRetriever:
    """Resolved adapters shared by one retriever instance."""

    colecao: VectorCollection
    embedding: EmbeddingModel
    reranker: Reranker


@dataclass(frozen=True)
class ConfiguracaoRetriever:
    """Preset and terms needed by one retrieval run."""

    preset: PresetRAG
    termos_estado: Mapping[str, TermosEstado]



@dataclass
class ContextoChunking:
    """Mutable page and section state shared while building chunks."""

    titulos_toc: Mapping[str, str]
    secoes: dict[tuple[str, str], list[tuple[int, str]]]
    ordem_secoes: list[tuple[str, str]]
    titulos_pagina: list[tuple[str, str]] = field(default_factory=list)
    secao_inicio: tuple[str, str] | None = None
    secao_fim: tuple[str, str] | None = None


@dataclass(frozen=True)
class ContextoPontuacao:
    """Ranking inputs for one retrieved candidate set."""

    pergunta: str
    reranker: Reranker
    secoes_alvo: Sequence[str]
    configuracao: ConfiguracaoRetriever

def extrair_paginas(
    arquivo_pdf: Path = PDF_CATALOGO_FILE,
    abridor_pdf: Callable[[Path], Any] | None = None,
) -> list[Pagina]:
    """Extract printed page numbers, body text, and structured table rows."""
    if not arquivo_pdf.is_file():
        raise FileNotFoundError(f"PDF do catálogo não encontrado: {arquivo_pdf}.")
    documento = (abridor_pdf or _abrir_pdf)(arquivo_pdf)
    try:
        total_paginas = len(documento)
        paginas = [
            _extrair_pagina(pagina, pagina_fisica=indice, total_paginas=total_paginas)
            for indice, pagina in enumerate(documento, start=1)
        ]
    finally:
        documento.close()
    if not paginas:
        raise ValueError("O PDF do catálogo não contém páginas.")
    return paginas


def chunk_legado(texto: str, preset: PresetRAG = LEGADO) -> list[Chunk]:
    """Reproduce the previous paragraph grouping and its 1000-character limit."""
    paragrafos = [item.strip() for item in re.split(r"\n\s*\n", texto) if item.strip()]
    grupos: list[str] = []
    atual = ""
    for paragrafo in paragrafos:
        if atual and len(atual) + len(paragrafo) > preset.chunk_max:
            grupos.append(atual.strip())
            atual = ""
        atual += f"{paragrafo}\n\n"
    if atual:
        grupos.append(atual.strip())
    return [Chunk(f"legado-{indice:05d}", None, None, None, None, grupo) for indice, grupo in enumerate(grupos, 1)]


def chunk_novo(paginas: Sequence[Pagina], preset: PresetRAG = NOVO) -> list[Chunk]:
    """Chunk one section at a time, retaining printed page and section metadata."""
    if not paginas:
        raise ValueError("É necessário fornecer páginas extraídas para gerar chunks.")
    titulos_toc = _ler_titulos_sumario(paginas)
    secoes: dict[tuple[str, str], list[tuple[int, str]]] = {}
    ordem_secoes: list[tuple[str, str]] = []
    contexto = ContextoChunking(titulos_toc, secoes, ordem_secoes)
    secao_atual = ("0", "Conte\u00fado sem se\u00e7\u00e3o numerada")
    for pagina in paginas:
        contexto.secao_inicio = secao_atual
        contexto.titulos_pagina.clear()
        secao_atual = _adicionar_texto_da_pagina(pagina, secao_atual, contexto)
        contexto.secao_fim = secao_atual
        _adicionar_tabelas_da_pagina(pagina, contexto)
    partes = [
        chunk
        for chave_secao in ordem_secoes
        for chunk in _chunkar_secao(chave_secao, secoes[chave_secao], preset)
    ]
    return _identificar_chunks(partes, "novo")


def carregar_termos_estado(arquivo: Path = TERMOS_ESTADO_FILE) -> dict[str, TermosEstado]:
    """Load the checked sensor-to-query-term catalog from JSON."""
    try:
        with arquivo.open(encoding="utf-8") as fonte:
            documento = json.load(fonte)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Não foi possível carregar os termos de estado: {arquivo.name}.") from error
    grandezas = documento.get("grandezas") if isinstance(documento, dict) else None
    if not isinstance(grandezas, dict) or not grandezas:
        raise ValueError("O catálogo de termos precisa conter grandezas.")
    return {chave: _validar_termos(item, chave) for chave, item in grandezas.items()}


def criar_retriever(
    chunks: Sequence[Chunk],
    preset: PresetRAG = NOVO,
    dependencias: DependenciasRAG | None = None,
) -> "Retriever":
    """Create an ephemeral cosine index and a retriever from injected adapters."""
    if not chunks:
        raise ValueError("Não é possível indexar uma coleção vazia de chunks.")
    dependencias_resolvidas = dependencias or DependenciasRAG()
    embedding = dependencias_resolvidas.embedding or _carregar_embedding(preset)
    reranker = dependencias_resolvidas.reranker or _carregar_reranker(preset)
    cliente = dependencias_resolvidas.cliente_vetorial or _criar_cliente_chroma()
    colecao = _criar_colecao(cliente, preset)
    _indexar_chunks(colecao, chunks, embedding, preset)
    termos = dependencias_resolvidas.termos_estado
    if termos is None:
        termos = carregar_termos_estado() if preset.usa_estado else {}
    componentes = ComponentesRetriever(colecao, embedding, reranker)
    configuracao = ConfiguracaoRetriever(preset, termos)
    return Retriever(componentes, configuracao)


class Retriever:
    """Retrieve and rerank catalog chunks, optionally using operational state."""

    def __init__(self, componentes: ComponentesRetriever, configuracao: ConfiguracaoRetriever) -> None:
        self.componentes = componentes
        self.configuracao = configuracao

    def buscar(
        self,
        pergunta: str,
        estado: EstadoOperacional | None = None,
        k_busca: int | None = None,
        k_final: int | None = None,
    ) -> list[dict[str, Any]]:
        """Expand, retrieve, rerank, and boost matching section titles."""
        if not pergunta.strip():
            raise ValueError("A pergunta não pode estar vazia.")
        k_busca = self.configuracao.preset.k_busca if k_busca is None else k_busca
        k_final = self.configuracao.preset.k_final if k_final is None else k_final
        if k_busca < 1 or k_final < 1:
            raise ValueError("k_busca e k_final precisam ser positivos.")
        estado_ativo = estado if self.configuracao.preset.usa_estado else None
        termos, secoes_alvo = _termos_da_consulta(estado_ativo, self.configuracao.termos_estado)
        consulta = _expandir_consulta(pergunta, termos)
        texto_query = self.configuracao.preset.prefixo_query + consulta
        vetor_query = _codificar(self.componentes.embedding, [texto_query])[0]
        resultados = self.componentes.colecao.query([vetor_query], n_results=k_busca)
        candidatos = _candidatos(resultados, k_busca)
        if not candidatos:
            return []
        contexto_pontuacao = ContextoPontuacao(
            pergunta, self.componentes.reranker, secoes_alvo, self.configuracao
        )
        _pontuar_candidatos(candidatos, contexto_pontuacao)
        return sorted(candidatos, key=_ordem_resultado, reverse=True)[:k_final]


def _abrir_pdf(arquivo_pdf: Path) -> Any:
    try:
        import pymupdf
    except ImportError as error:
        raise RuntimeError("Instale pymupdf conforme requirements.txt para ler o catálogo.") from error
    return pymupdf.open(arquivo_pdf)


def _extrair_pagina(
    pagina_pdf: Any,
    pagina_fisica: int | None = None,
    total_paginas: int | None = None,
) -> Pagina:
    tabelas_encontradas = pagina_pdf.find_tables(use_layout=False).tables
    blocos = pagina_pdf.get_text("blocks", sort=True)
    texto_original = pagina_pdf.get_text()
    texto_blocos = _textos_fora_das_tabelas(blocos, tabelas_encontradas)
    palavras = _palavras_ordenadas(pagina_pdf.get_text("words", sort=True))
    texto_limpo, pagina_impressa = _remover_cabecalho_e_rodape(
        texto_blocos, pagina_fisica, total_paginas
    )
    tabelas = tuple(
        tabela_extraida
        for tabela in tabelas_encontradas
        if (tabela_extraida := _extrair_tabela(tabela, blocos, tabelas_encontradas, palavras)).linhas
    )
    return Pagina(pagina_impressa, texto_limpo, texto_original, tabelas)


def _textos_fora_das_tabelas(blocos: Sequence[Sequence[Any]], tabelas: Sequence[Any]) -> str:
    textos: list[str] = []
    for bloco in blocos:
        if len(bloco) < 5:
            raise ValueError("O PyMuPDF retornou um bloco de texto incompleto.")
        if not _bloco_e_tabela(bloco, tabelas):
            textos.append(str(bloco[4]))
    return "\n\n".join(textos)


def _bloco_e_tabela(bloco: Sequence[Any], tabelas: Sequence[Any]) -> bool:
    for tabela in tabelas:
        if _proporcao_sobreposta(bloco, tabela.bbox) >= 0.5:
            return True
    return False


def _proporcao_sobreposta(bloco: Sequence[Any], caixa_tabela: Sequence[float]) -> float:
    esquerda = max(float(bloco[0]), float(caixa_tabela[0]))
    topo = max(float(bloco[1]), float(caixa_tabela[1]))
    direita = min(float(bloco[2]), float(caixa_tabela[2]))
    base = min(float(bloco[3]), float(caixa_tabela[3]))
    area_bloco = max(0.0, float(bloco[2]) - float(bloco[0])) * max(0.0, float(bloco[3]) - float(bloco[1]))
    if area_bloco == 0.0 or direita <= esquerda or base <= topo:
        return 0.0
    return ((direita - esquerda) * (base - topo)) / area_bloco


def _extrair_tabela(
    tabela: Any,
    blocos: Sequence[Sequence[Any]],
    tabelas: Sequence[Any],
    palavras: Sequence[Sequence[Any]],
) -> TabelaExtraida:
    linhas = _serializar_linhas_tabela(tabela, palavras)
    legenda = _legenda_da_tabela(tabela.bbox, blocos, tabelas)
    return TabelaExtraida(tuple(linhas), legenda, float(tabela.bbox[1]))


def _serializar_linhas_tabela(tabela: Any, palavras: Sequence[Sequence[Any]]) -> list[str]:
    linhas = _matriz_da_tabela(tabela, palavras)
    if not linhas:
        return []
    nomes_colunas, indices_cabecalho = _nomes_colunas(tabela, linhas)
    return _serializar_linhas_de_dados(linhas, nomes_colunas, indices_cabecalho)


def _matriz_da_tabela(tabela: Any, palavras: Sequence[Sequence[Any]]) -> list[list[str]]:
    linhas_pdf = getattr(tabela, "rows", None)
    if not linhas_pdf or not palavras or not isinstance(palavras[0], (list, tuple)):
        return [[_limpar_celula(valor) for valor in linha] for linha in tabela.extract()]
    return [
        [_texto_da_celula(celula, palavras) for celula in linha.cells]
        for linha in linhas_pdf
    ]


def _texto_da_celula(celula: Any, palavras: Sequence[Sequence[Any]]) -> str:
    if not celula or len(celula) != 4:
        return ""
    esquerda, topo, direita, base = map(float, celula)
    palavras_ordenadas = []
    indice_inicio = bisect_left(palavras, topo, key=_centro_vertical)
    indice_fim = bisect_right(palavras, base, key=_centro_vertical)
    for palavra in palavras[indice_inicio:indice_fim]:
        if len(palavra) < 5:
            continue
        x0, y0, x1, y1, texto = palavra[:5]
        centro_x = (float(x0) + float(x1)) / 2
        centro_y = (float(y0) + float(y1)) / 2
        if esquerda <= centro_x <= direita and topo <= centro_y <= base:
            palavras_ordenadas.append((float(y0), float(x0), str(texto)))
    return _limpar_celula(" ".join(texto for _, _, texto in sorted(palavras_ordenadas)))


def _palavras_ordenadas(palavras: Sequence[Sequence[Any]]) -> list[Sequence[Any]]:
    if not palavras or not isinstance(palavras[0], (list, tuple)):
        return []
    return sorted(palavras, key=_centro_vertical)


def _centro_vertical(palavra: Sequence[Any]) -> float:
    return (float(palavra[1]) + float(palavra[3])) / 2


def _nomes_colunas(tabela: Any, linhas: Sequence[Sequence[str]]) -> tuple[list[str], set[int]]:
    indices_cabecalho = _indices_linhas_cabecalho(tabela, linhas)
    if not indices_cabecalho:
        return [], set()
    linhas_pdf = getattr(tabela, "rows", None) or ()
    if not linhas_pdf:
        nomes = _nomes_colunas_sem_geometria(tabela, linhas[0])
        return nomes, indices_cabecalho if nomes else set()
    celulas_referencia = _celulas_referencia(linhas_pdf)
    nomes_por_coluna: list[list[str]] = [[] for _ in range(max(map(len, linhas)))]
    for indice_linha in sorted(indices_cabecalho):
        celulas = linhas_pdf[indice_linha].cells
        valores_linha = _valores_linha_cabecalho(tabela, indice_linha, linhas[indice_linha])
        _registrar_nomes_colunas(nomes_por_coluna, valores_linha, celulas, celulas_referencia)
    nomes = [" ".join(dict.fromkeys(valores)) for valores in nomes_por_coluna]
    if not any(re.search(r"[A-Za-zÀ-ÿ]", nome) for nome in nomes):
        return [], set()
    if nomes and _normalizar_texto(nomes[0]) == "carcaca":
        nomes = _nomes_colunas_carcaca(nomes)
    return nomes, indices_cabecalho


def _valores_linha_cabecalho(
    tabela: Any, indice: int, valores: Sequence[str]
) -> list[str]:
    if indice != 0:
        return list(valores)
    nomes_metadados = getattr(getattr(tabela, "header", None), "names", None) or ()
    if len(nomes_metadados) != len(valores):
        return list(valores)
    return [_limpar_celula(nome) or valor for nome, valor in zip(nomes_metadados, valores)]


def _registrar_nomes_colunas(
    nomes_por_coluna: list[list[str]],
    valores: Sequence[str],
    celulas: Sequence[Any],
    referencias: Sequence[Any],
) -> None:
    for indice, valor in enumerate(valores):
        if not valor:
            continue
        caixa = celulas[indice] if indice < len(celulas) else None
        for indice_alvo in _colunas_cobertas(caixa, referencias, indice):
            _registrar_nome_coluna(nomes_por_coluna, indice_alvo, valor)


def _registrar_nome_coluna(nomes_por_coluna: list[list[str]], indice: int, nome: str) -> None:
    if indice >= len(nomes_por_coluna):
        return
    nomes_por_coluna[indice].append(nome)


def _nomes_colunas_sem_geometria(tabela: Any, primeira_linha: Sequence[str]) -> list[str]:
    nomes = getattr(getattr(tabela, "header", None), "names", None) or primeira_linha
    textos = [_limpar_celula(nome) for nome in nomes]
    return textos if any(textos) else []


def _celulas_referencia(linhas_pdf: Sequence[Any]) -> Sequence[Any]:
    return max(linhas_pdf, key=lambda linha: sum(celula is not None for celula in linha.cells)).cells


def _colunas_cobertas(
    celula: Any, referencias: Sequence[Any], indice_coluna: int
) -> list[int]:
    if not celula:
        return [indice_coluna]
    esquerda, _, direita, _ = map(float, celula)
    cobertas = []
    for indice, referencia in enumerate(referencias):
        if not referencia:
            continue
        inicio, _, fim, _ = map(float, referencia)
        centro = (inicio + fim) / 2
        if esquerda <= centro <= direita:
            cobertas.append(indice)
    return cobertas or [indice_coluna]


def _indices_linhas_cabecalho(tabela: Any, linhas: Sequence[Sequence[str]]) -> set[int]:
    if not linhas:
        return set()
    indices = {0}
    caixa_cabecalho = getattr(getattr(tabela, "header", None), "bbox", None)
    linhas_pdf = getattr(tabela, "rows", None) or ()
    if caixa_cabecalho:
        limite_inferior = float(caixa_cabecalho[3])
        for indice, linha_pdf in enumerate(linhas_pdf):
            caixas = [celula for celula in linha_pdf.cells if celula]
            if caixas and max(float(caixa[3]) for caixa in caixas) <= limite_inferior + 0.1:
                indices.add(indice)
    if len(linhas) > 1 and _linha_eh_subcabecalho(linhas[1]):
        indices.add(1)
    return indices


def _linha_eh_subcabecalho(linha: Sequence[str]) -> bool:
    texto = _normalizar_texto(" ".join(valor for valor in linha if valor))
    unidades = ("cv", "hp", "kw", "rpm", "polos", "%", "kg")
    return sum(bool(valor) for valor in linha) >= 2 and any(unidade in texto for unidade in unidades)


def _nomes_colunas_carcaca(nomes: Sequence[str]) -> list[str]:
    return ["Atributo", "", "", *(f"Carcaça {nome}" for nome in nomes[3:])]


def _serializar_linhas_de_dados(
    linhas: Sequence[Sequence[str]], nomes_colunas: Sequence[str], indices_cabecalho: set[int]
) -> list[str]:
    linhas_serializadas = []
    grupo = ""
    for indice, linha in enumerate(linhas):
        valores = [_limpar_celula(valor) for valor in linha]
        presentes = [valor for valor in valores if valor]
        if indice in indices_cabecalho or not presentes:
            continue
        if len(presentes) == 1:
            grupo = presentes[0]
            continue
        texto = _serializar_linha(valores, nomes_colunas)
        if texto:
            linhas_serializadas.append(f"Grupo: {grupo}; {texto}" if grupo else texto)
    return linhas_serializadas


def _serializar_linha(linha: Sequence[Any], nomes_colunas: Sequence[str]) -> str:
    pares = []
    for indice, valor in enumerate(linha):
        conteudo = _limpar_celula(valor)
        if not conteudo or indice >= len(nomes_colunas) or not nomes_colunas[indice]:
            continue
        pares.append(f"{nomes_colunas[indice]}: {conteudo}")
    return "; ".join(pares)


def _legenda_da_tabela(
    caixa_tabela: Sequence[float], blocos: Sequence[Sequence[Any]], tabelas: Sequence[Any]
) -> str:
    candidatos: list[tuple[float, str]] = []
    for bloco in blocos:
        if len(bloco) < 5 or _bloco_e_tabela(bloco, tabelas):
            continue
        distancia = float(bloco[1]) - float(caixa_tabela[3])
        if 0.0 <= distancia <= TABLE_CAPTION_MAX_GAP and _sobreposicao_horizontal(bloco, caixa_tabela):
            texto = _limpar_celula(bloco[4])
            candidatos.append((distancia, texto))
    return min(candidatos, default=(0.0, ""), key=lambda candidato: candidato[0])[1]


def _sobreposicao_horizontal(bloco: Sequence[Any], caixa_tabela: Sequence[float]) -> bool:
    return min(float(bloco[2]), float(caixa_tabela[2])) > max(float(bloco[0]), float(caixa_tabela[0]))


def _remover_cabecalho_e_rodape(
    texto: str,
    pagina_fisica: int | None = None,
    total_paginas: int | None = None,
) -> tuple[str, int]:
    linhas = _limpar_controles(texto).splitlines()
    removidas: set[int] = set()
    pagina_impressa: int | None = None
    for indice, linha in enumerate(linhas):
        normalizada = _normalizar_texto(linha)
        if "www.weg.net" in normalizada:
            removidas.add(indice)
        if "motor eletrico trifasico w22" not in normalizada:
            continue
        pagina_impressa = _numero_pagina_no_rodape(normalizada, linhas, indice)
        removidas.add(indice)
        proxima_linha = _proxima_linha_com_texto(linhas, indice)
        if proxima_linha is not None and re.fullmatch(r"\d{1,3}", linhas[proxima_linha].strip()):
            removidas.add(proxima_linha)
    if pagina_impressa is None:
        paginas_sem_rodape = {1, total_paginas} if total_paginas is not None else {1}
        if pagina_fisica not in paginas_sem_rodape:
            raise ValueError("Não foi possível capturar o número impresso da página do catálogo.")
        pagina_impressa = pagina_fisica
    texto_limpo = "\n".join(linha for indice, linha in enumerate(linhas) if indice not in removidas)
    return _normalizar_espacos(texto_limpo), pagina_impressa


def _numero_pagina_no_rodape(normalizada: str, linhas: Sequence[str], indice: int) -> int:
    correspondencia = re.search(r"motor eletrico trifasico w22\s*\|?\s*(\d{1,3})\b", normalizada)
    if correspondencia:
        return int(correspondencia.group(1))
    proxima_linha = _proxima_linha_com_texto(linhas, indice)
    if proxima_linha is None or not re.fullmatch(r"\d{1,3}", linhas[proxima_linha].strip()):
        raise ValueError("O rodapé do catálogo não contém número de página legível.")
    return int(linhas[proxima_linha].strip())


def _proxima_linha_com_texto(linhas: Sequence[str], indice: int) -> int | None:
    return next((posicao for posicao in range(indice + 1, len(linhas)) if linhas[posicao].strip()), None)


def _ler_titulos_sumario(paginas: Sequence[Pagina]) -> dict[str, str]:
    titulos_candidatos: dict[str, str] = {}
    for pagina in paginas:
        titulos_pagina = _titulos_sumario_da_pagina(pagina.texto)
        if len(titulos_pagina) >= 2:
            titulos_candidatos.update(titulos_pagina)
    return _filtrar_hierarquia_toc(titulos_candidatos)


def _titulos_sumario_da_pagina(texto_pagina: str) -> dict[str, str]:
    titulos: dict[str, str] = {}
    for linha in texto_pagina.splitlines():
        correspondencia = TOC_PATTERN.match(_limpar_controles(linha).strip())
        if correspondencia is None:
            continue
        numero = correspondencia.group("numero")
        titulo = correspondencia.group("titulo").strip()
        if _titulo_comeca_com_maiuscula(titulo):
            titulos[numero] = titulo
    return titulos


def _filtrar_hierarquia_toc(titulos: Mapping[str, str]) -> dict[str, str]:
    principais = [int(numero) for numero in titulos if "." not in numero]
    maior_principal = max(principais, default=0)
    validos = {
        numero: titulo
        for numero, titulo in titulos.items()
        if "." not in numero and int(numero) <= maior_principal
    }
    for numero, titulo in titulos.items():
        partes = numero.split(".")
        if len(partes) > 1 and all(
            ".".join(partes[:indice]) in validos for indice in range(1, len(partes))
        ):
            validos[numero] = titulo
    return validos


def _adicionar_texto_da_pagina(
    pagina: Pagina, secao_atual: tuple[str, str], contexto: ContextoChunking
) -> tuple[str, str]:
    linhas = pagina.texto.splitlines()
    indice = 0
    while indice < len(linhas):
        texto = _limpar_celula(_limpar_controles(linhas[indice]))
        if not texto or TOC_PATTERN.match(texto) or DOTTED_LEADER_PATTERN.search(texto):
            indice += 1
            continue
        correspondencia = SECTION_PATTERN.match(texto)
        linhas_consumidas = 0
        if correspondencia:
            correspondencia, linhas_consumidas = _complementar_titulo(
                linhas, indice, correspondencia, contexto.titulos_toc
            )
        if correspondencia and _titulo_reconhecido(correspondencia, contexto.titulos_toc):
            numero = correspondencia.group("numero")
            secao_atual = (numero, contexto.titulos_toc[numero])
            contexto.titulos_pagina.append(secao_atual)
            _garantir_secao(secao_atual, contexto.secoes, contexto.ordem_secoes)
            indice += linhas_consumidas + 1
            continue
        _adicionar_trecho(secao_atual, pagina.pagina, texto, contexto)
        indice += 1
    return secao_atual


def _complementar_titulo(
    linhas: Sequence[str],
    indice: int,
    correspondencia: re.Match[str],
    titulos_toc: Mapping[str, str],
) -> tuple[re.Match[str], int]:
    if _titulo_reconhecido(correspondencia, titulos_toc):
        return correspondencia, 0
    numero = correspondencia.group("numero")
    titulo = correspondencia.group("titulo").strip()
    if numero not in titulos_toc or not _titulo_comeca_com_maiuscula(titulo):
        return correspondencia, 0
    for deslocamento, linha in enumerate(linhas[indice + 1 : indice + 4], start=1):
        continuacao = _limpar_celula(_limpar_controles(linha))
        if not continuacao or DOTTED_LEADER_PATTERN.search(continuacao):
            break
        if SECTION_PATTERN.match(continuacao) or len(continuacao.split()) > 4:
            break
        titulo += f" {continuacao}"
        candidato = SECTION_PATTERN.match(f"{numero} {titulo}")
        if candidato and _titulo_reconhecido(candidato, titulos_toc):
            return candidato, deslocamento
    return correspondencia, 0

def _titulo_reconhecido(correspondencia: re.Match[str], titulos_toc: Mapping[str, str]) -> bool:
    numero = correspondencia.group("numero")
    titulo_corpo = correspondencia.group("titulo").strip()
    if numero not in titulos_toc or NOTE_ITEM_PATTERN.match(correspondencia.group(0)):
        return False
    if DOTTED_LEADER_PATTERN.search(titulo_corpo) or not _titulo_comeca_com_maiuscula(titulo_corpo):
        return False
    tokens_sumario = _tokens(titulos_toc[numero])
    tokens_corpo = _tokens(titulo_corpo)
    extras = tokens_corpo - tokens_sumario
    return bool(tokens_sumario) and tokens_sumario <= tokens_corpo and len(extras) <= 4


def _titulo_comeca_com_maiuscula(titulo: str) -> bool:
    primeira_letra = next((caractere for caractere in titulo if caractere.isalpha()), "")
    return bool(primeira_letra) and primeira_letra.isupper()


def _adicionar_tabelas_da_pagina(pagina: Pagina, contexto: ContextoChunking) -> None:
    if contexto.secao_inicio is None or contexto.secao_fim is None:
        raise RuntimeError("Page section boundaries are not initialized.")
    for tabela in pagina.tabelas:
        secao = _secao_da_tabela(
            tabela.legenda,
            contexto.titulos_pagina,
            contexto.secao_inicio,
            contexto.secao_fim,
        )
        for linha in tabela.linhas:
            _adicionar_trecho(secao, pagina.pagina, linha, contexto)

def _secao_da_tabela(
    legenda: str,
    titulos_pagina: Sequence[tuple[str, str]],
    secao_inicio: tuple[str, str],
    secao_fim: tuple[str, str],
) -> tuple[str, str]:
    if not legenda or not titulos_pagina:
        return secao_inicio if secao_inicio != ("0", "Conteúdo sem seção numerada") else secao_fim
    tokens_legenda = _tokens(legenda)
    pontuacoes = [
        (
            len(tokens_legenda.intersection(_tokens(secao[1]))) / max(1, len(_tokens(secao[1]))),
            -len(_tokens(secao[1])),
            indice,
            secao,
        )
        for indice, secao in enumerate(titulos_pagina)
    ]
    melhor = max(pontuacoes, default=(0.0, 0, 0, secao_fim))
    return melhor[3] if melhor[0] > 0 else secao_inicio


def _garantir_secao(
    secao: tuple[str, str],
    secoes: dict[tuple[str, str], list[tuple[int, str]]],
    ordem_secoes: list[tuple[str, str]],
) -> None:
    if secao not in secoes:
        secoes[secao] = []
        ordem_secoes.append(secao)


def _adicionar_trecho(
    secao: tuple[str, str], pagina: int, texto: str, contexto: ContextoChunking
) -> None:
    _garantir_secao(secao, contexto.secoes, contexto.ordem_secoes)
    contexto.secoes[secao].append((pagina, texto))

def _chunkar_secao(
    secao: tuple[str, str], trechos: Sequence[tuple[int, str]], preset: PresetRAG
) -> list[Chunk]:
    limite_texto = _limite_texto(secao, preset)
    chunks: list[Chunk] = []
    atual: list[tuple[int, str]] = []
    for pagina, trecho in trechos:
        for parte in _dividir_trecho(trecho, limite_texto):
            candidato = [*atual, (pagina, parte)]
            if atual and len(_texto_dos_trechos(candidato)) > limite_texto:
                _guardar_chunk(chunks, secao, atual, preset)
                sobreposicao = _trecho_sobreposto(atual, preset.chunk_overlap, limite_texto - len(parte) - 2)
                atual = ([sobreposicao] if sobreposicao else []) + [(pagina, parte)]
            else:
                atual = candidato
    if atual:
        _guardar_chunk(chunks, secao, atual, preset)
    return chunks


def _limite_texto(secao: tuple[str, str], preset: PresetRAG) -> int:
    maior_prefixo = f"[Seção {secao[0]} — {secao[1]} | p. 999-999] "
    limite = preset.chunk_max - len(maior_prefixo)
    if limite < CHUNK_MIN:
        raise ValueError(f"O título da seção {secao[0]} é longo demais para o limite de chunk.")
    return limite


def _dividir_trecho(texto: str, limite: int) -> list[str]:
    partes: list[str] = []
    atual = ""
    for frase in SENTENCE_PATTERN.split(texto.strip()):
        if len(frase) > limite:
            if atual:
                partes.append(atual)
                atual = ""
            partes.extend(textwrap.wrap(frase, width=limite, break_long_words=True, break_on_hyphens=False))
            continue
        candidato = f"{atual} {frase}".strip()
        if atual and len(candidato) > limite:
            partes.append(atual)
            atual = frase
        else:
            atual = candidato
    if atual:
        partes.append(atual)
    return partes


def _guardar_chunk(
    chunks: list[Chunk], secao: tuple[str, str], trechos: Sequence[tuple[int, str]], preset: PresetRAG
) -> None:
    conteudo = _texto_dos_trechos(trechos).strip()
    if len(conteudo) < CHUNK_MIN:
        return
    pagina_inicio, pagina_fim = trechos[0][0], trechos[-1][0]
    referencia = f"p. {pagina_inicio}" if pagina_inicio == pagina_fim else f"p. {pagina_inicio}-{pagina_fim}"
    texto = f"[Seção {secao[0]} — {secao[1]} | {referencia}] {conteudo}"
    if len(texto) > preset.chunk_max:
        raise ValueError("O chunk excedeu CHUNK_MAX após a inclusão dos metadados.")
    chunks.append(Chunk("", pagina_inicio, pagina_fim, secao[0], secao[1], texto))


def _texto_dos_trechos(trechos: Sequence[tuple[int, str]]) -> str:
    return "\n\n".join(texto for _, texto in trechos)


def _trecho_sobreposto(
    trechos: Sequence[tuple[int, str]], sobreposicao: int, limite: int
) -> tuple[int, str] | None:
    quantidade = min(sobreposicao, max(0, limite))
    if quantidade == 0 or not trechos:
        return None
    conteudo = _texto_dos_trechos(trechos)
    final = conteudo[-quantidade:].lstrip()
    inicio_palavra = final.find(" ")
    if inicio_palavra > 0:
        final = final[inicio_palavra + 1 :]
    return (trechos[-1][0], final) if final else None


def _identificar_chunks(chunks: Sequence[Chunk], prefixo: str) -> list[Chunk]:
    return [
        Chunk(f"{prefixo}-{indice:05d}", chunk.pagina, chunk.pagina_fim, chunk.secao, chunk.secao_titulo, chunk.texto)
        for indice, chunk in enumerate(chunks, start=1)
    ]


def _validar_termos(item: Any, chave: str) -> TermosEstado:
    if not isinstance(item, dict):
        raise ValueError(f"A configuração de termos para {chave} precisa ser um objeto.")
    termos = item.get("termos_consulta")
    secoes = item.get("secoes_alvo")
    dominio = item.get("dominio_falha")
    if not isinstance(dominio, str) or not dominio.strip():
        raise ValueError(f"A configuração de termos para {chave} não declara domínio.")
    if not _validar_lista_texto(termos) or not _validar_lista_texto(secoes):
        raise ValueError(f"A configuração de termos para {chave} contém listas vazias ou inválidas.")
    return TermosEstado(dominio, tuple(termos), tuple(secoes))


def _validar_lista_texto(valores: Any) -> bool:
    return isinstance(valores, list) and bool(valores) and all(isinstance(item, str) and item.strip() for item in valores)


def _termos_da_consulta(
    estado: EstadoOperacional | None, termos_catalogo: Mapping[str, TermosEstado]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if estado is None or estado.operacao_normal:
        return (), ()
    termos: list[str] = []
    secoes: list[str] = []
    for alerta in estado.alertas_ativos:
        chave = _chave_da_grandeza(alerta.grandeza)
        configuracao = termos_catalogo.get(chave)
        if configuracao is None or configuracao.dominio_falha != alerta.dominio_falha:
            raise ValueError(f"Não há termos válidos para o alerta {alerta.id}.")
        termos.extend(termo for termo in configuracao.termos_consulta if termo not in termos)
        secoes.extend(secao for secao in configuracao.secoes_alvo if secao not in secoes)
    return tuple(termos), tuple(secoes)


def _chave_da_grandeza(grandeza: str) -> str:
    texto = _normalizar_texto(grandeza)
    if "temperatura" in texto:
        return "temperatura"
    if "corrente" in texto:
        return "corrente"
    if "vibra" in texto:
        return "vibração"
    if "velocidade" in texto:
        return "velocidade"
    raise ValueError(f"Não há termos de busca para a grandeza {grandeza}.")


def _expandir_consulta(pergunta: str, termos: Sequence[str]) -> str:
    return " ".join((pergunta, *termos)) if termos else pergunta


def _candidatos(resultados: Mapping[str, Any], limite: int) -> list[dict[str, Any]]:
    documentos = _primeiro_resultado(resultados, "documents")
    if not documentos:
        return []
    metadados = _primeiro_resultado(resultados, "metadatas") or []
    ids = _primeiro_resultado(resultados, "ids") or []
    distancias = _primeiro_resultado(resultados, "distances")
    if distancias is None or len(distancias) < min(limite, len(documentos)):
        raise ValueError("A busca vetorial não retornou distâncias para todos os candidatos.")
    candidatos = []
    for indice, documento in enumerate(documentos[:limite]):
        meta = metadados[indice] if indice < len(metadados) and metadados[indice] else {}
        candidatos.append(
            {
                "id": ids[indice] if indice < len(ids) else str(indice),
                "texto": str(documento),
                "pagina": _int_opcional(meta.get("pagina")),
                "pagina_fim": _int_opcional(meta.get("pagina_fim")),
                "secao": meta.get("secao"),
                "secao_titulo": meta.get("secao_titulo"),
                "distancia": float(distancias[indice]),
            }
        )
    escores_denso = _normalizar_escores([item["distancia"] for item in candidatos], inverter=True)
    for candidato, score in zip(candidatos, escores_denso, strict=True):
        candidato["score_denso"] = score
    return candidatos


def _primeiro_resultado(resultados: Mapping[str, Any], campo: str) -> Any:
    valores = resultados.get(campo)
    if not valores:
        return []
    return valores[0] if isinstance(valores[0], (list, tuple)) else valores


def _int_opcional(valor: Any) -> int | None:
    return int(valor) if valor is not None else None


def _pontuar_candidatos(
    candidatos: list[dict[str, Any]], contexto: ContextoPontuacao
) -> None:
    pares = [(contexto.pergunta, candidato["texto"]) for candidato in candidatos]
    resultado = contexto.reranker.predict(pares)
    try:
        valores_brutos = list(resultado)
    except TypeError:
        valores_brutos = [resultado]
    try:
        valores = [float(valor) for valor in valores_brutos]
    except (TypeError, ValueError) as error:
        raise ValueError("O reranker retornou escores inv\u00e1lidos para os candidatos.") from error
    if len(valores) != len(candidatos) or not all(math.isfinite(valor) for valor in valores):
        raise ValueError("O reranker retornou escores inv\u00e1lidos para os candidatos.")
    escores = _normalizar_escores(valores)
    for candidato, score in zip(candidatos, escores, strict=True):
        candidato["score_rerank"] = score
        candidato["score_final"] = score + _boost_secao(
            candidato, contexto.secoes_alvo, contexto.configuracao.preset
        )

def _normalizar_escores(valores: Sequence[float], inverter: bool = False) -> list[float]:
    if not valores:
        return []
    minimo, maximo = min(valores), max(valores)
    if minimo == maximo:
        return [1.0] * len(valores)
    normalizados = [(valor - minimo) / (maximo - minimo) for valor in valores]
    return [1.0 - valor for valor in normalizados] if inverter else normalizados


def _boost_secao(
    candidato: Mapping[str, Any], secoes_alvo: Sequence[str], preset: PresetRAG
) -> float:
    titulo = _normalizar_texto(str(candidato.get("secao_titulo") or ""))
    if not preset.usa_estado or not titulo:
        return 0.0
    return preset.peso_estado if any(_normalizar_texto(secao) in titulo for secao in secoes_alvo) else 0.0


def _ordem_resultado(candidato: Mapping[str, Any]) -> tuple[float, float, float, str]:
    return (
        float(candidato["score_final"]),
        float(candidato["score_rerank"]),
        float(candidato["score_denso"]),
        str(candidato["id"]),
    )


def _codificar(modelo: EmbeddingModel, textos: Sequence[str]) -> list[list[float]]:
    return [[float(valor) for valor in vetor] for vetor in modelo.encode(textos)]


def _criar_cliente_chroma() -> Any:
    try:
        import chromadb
    except ImportError as error:
        raise RuntimeError("Instale chromadb conforme requirements.txt para criar o índice.") from error
    return chromadb.EphemeralClient()


def _criar_colecao(cliente: Any, preset: PresetRAG) -> VectorCollection:
    return cliente.create_collection(
        name=preset.colecao,
        metadata={CHROMA_DISTANCE_KEY: CHROMA_DISTANCE_COSINE},
    )


def _indexar_chunks(
    colecao: VectorCollection, chunks: Sequence[Chunk], embedding: EmbeddingModel, preset: PresetRAG
) -> None:
    textos = [preset.prefixo_passage + chunk.texto for chunk in chunks]
    vetores = _codificar(embedding, textos)
    metadados = [_metadata_chunk(chunk) for chunk in chunks]
    if all(not item for item in metadados):
        colecao.add(
            ids=[item.id for item in chunks],
            documents=[item.texto for item in chunks],
            embeddings=vetores,
        )
        return
    colecao.add(
        ids=[item.id for item in chunks],
        documents=[item.texto for item in chunks],
        embeddings=vetores,
        metadatas=metadados,
    )


def _metadata_chunk(chunk: Chunk) -> dict[str, Any]:
    valores = (chunk.pagina, chunk.pagina_fim, chunk.secao, chunk.secao_titulo)
    if all(valor is None for valor in valores):
        return {}
    if any(valor is None for valor in valores):
        raise ValueError(f"O chunk {chunk.id} possui metadados incompletos.")
    return {
        "pagina": chunk.pagina,
        "pagina_fim": chunk.pagina_fim,
        "secao": chunk.secao,
        "secao_titulo": chunk.secao_titulo,
    }


def _carregar_embedding(preset: PresetRAG) -> EmbeddingModel:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as error:
        raise RuntimeError("Instale sentence-transformers conforme requirements.txt.") from error
    return SentenceTransformer(preset.modelo_embedding)


def _carregar_reranker(preset: PresetRAG) -> Reranker:
    try:
        from sentence_transformers import CrossEncoder
    except ImportError as error:
        raise RuntimeError("Instale sentence-transformers conforme requirements.txt.") from error
    return CrossEncoder(preset.modelo_reranker)


def _tokens(texto: str) -> set[str]:
    palavras = re.findall(r"\w+", _normalizar_texto(texto), flags=re.UNICODE)
    return {_singularizar(palavra) for palavra in palavras if not palavra.isdigit()}


def _singularizar(palavra: str) -> str:
    if palavra.endswith("is") and len(palavra) > 4:
        return f"{palavra[:-2]}l"
    return palavra[:-1] if palavra.endswith("s") and len(palavra) > 3 else palavra


def _normalizar_texto(texto: str) -> str:
    decomposed = unicodedata.normalize("NFKD", texto.casefold())
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", without_marks).strip()


def _normalizar_espacos(texto: str) -> str:
    linhas = [re.sub(r"[ \t]+", " ", linha).strip() for linha in texto.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(linhas)).strip()


def _limpar_controles(texto: str) -> str:
    return "".join(
        caractere if caractere in "\r\n\t" or unicodedata.category(caractere) != "Cc" else " "
        for caractere in texto
    )


def _limpar_celula(valor: Any) -> str:
    if valor is None:
        return ""
    texto_sem_hifen_discricionario = re.sub(r"\u00ad\s*", "", str(valor))
    texto_normalizado = re.sub(r"\s+", " ", _limpar_controles(texto_sem_hifen_discricionario)).strip()
    return re.sub(r"(?<=[A-Za-zÀ-ÿ])-\s+(?=[a-zà-ÿ])", "", texto_normalizado)
