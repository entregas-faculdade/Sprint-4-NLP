"""Evaluate RAG retrieval against a page-level gold set and judge answers claim by claim."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Protocol

from src.pln.alertas import Alerta
from src.pln.assistente import Assistente, Resposta
from src.pln.config import (
    AVALIACAO_RAG_FILE,
    CATEGORIAS_AVALIACAO,
    COBERTURA_NAO_COBRE,
    CRITERIO_ESTRITO,
    CRITERIO_PAGINA,
    ESCOPO_DENTRO,
    ESCOPO_FORA,
    ESPERADO_ABSTENCAO,
    ESTADOS_AVALIACAO,
    FRASE_ABSTENCAO,
    GRADE_LIMIAR_ABSTENCAO,
    GRADE_PESO_ESTADO,
    GUARDA_JUIZ_INVALIDO,
    GUARDA_MARCADOR,
    GUARDA_NUMERO,
    JUIZ_CALIBRACAO_FILE,
    K_FINAL,
    KS_AVALIACAO,
    MARCADORES_CONHECIMENTO_EXTERNO,
    MODELO_GERADOR,
    MODELO_JUIZ,
    PADRAO_CITACAO_ASSISTENTE,
    PADRAO_COLCHETES,
    PADRAO_DIVISAO_FRASES,
    PADRAO_LINHA_CONFIANCA,
    PADRAO_MARCADOR_LISTA,
    PADRAO_MILHAR,
    PADRAO_NUMERO_AFIRMACAO,
    PADRAO_ROTULO_AFIRMACAO,
    PADRAO_ROTULO_COBERTURA,
    PESO_ESTADO,
    PONTOS_COBERTURA,
    PREFIXO_QUERY_NOVO,
    PROMPT_JUIZ_AFIRMACAO,
    PROMPT_JUIZ_COBERTURA,
    ROTULO_CONTRADIZ,
    ROTULO_EXTERNA,
    ROTULO_META,
    ROTULO_SUSTENTADA,
    ROTULOS_AFIRMACAO,
    SPLIT_DEV,
    SPLIT_TESTE,
)
from src.pln.estado import EstadoOperacional, construir_estado_operacional
from src.pln.llm import OpenRouterRequestError
from src.pln.rag import ConfiguracaoRetriever, EmbeddingModel, Pagina, Retriever


class CompletionClient(Protocol):
    """Chat completion boundary shared by the generator and the judge."""

    def complete(self, model_id: str, messages: list[dict[str, str]]) -> str:
        """Return a completion for the requested model and messages."""


@dataclass(frozen=True)
class PerguntaAvaliacao:
    """One gold-set question, inside or outside the catalog scope."""

    id: str
    escopo: str
    pergunta: str
    split: str
    estado: str | None
    resposta_referencia: str = ""
    paginas_gabarito: tuple[int, ...] = ()
    secoes_gabarito: tuple[str, ...] = ()
    trecho_ancora: str = ""
    categoria: str = ""
    esperado: str = ""
    termo_ausente: str = ""


@dataclass(frozen=True)
class CasoCalibracao:
    """One hand-labelled (context, claim, label) triple used to validate the judge."""

    id: str
    split: str
    contexto: str
    afirmacao: str
    rotulo_esperado: str


@dataclass(frozen=True)
class RotuloAfirmacao:
    """Judge label, final label after deterministic guards, and the guard that fired."""

    afirmacao: str
    rotulo_juiz: str | None
    rotulo: str
    guarda: str | None


@dataclass(frozen=True)
class ConfiguracaoRecuperacao:
    """A retriever plus how it receives operational state and page metadata."""

    nome: str
    retriever: Retriever
    estados: Mapping[str, EstadoOperacional] | None = None
    paginas_legado: Sequence[Pagina] | None = None


@dataclass(frozen=True)
class ContextoRespostas:
    """Everything needed to generate and judge the answer to one question."""

    assistente: Assistente
    juiz: "Juiz"
    embedding: EmbeddingModel
    estados: Mapping[str, EstadoOperacional]


# ---------------------------------------------------------------- gabarito


def carregar_gabarito(arquivo: Path = AVALIACAO_RAG_FILE) -> list[PerguntaAvaliacao]:
    """Load and validate the gold set from JSON."""
    itens = _ler_json(arquivo).get("perguntas")
    if not isinstance(itens, list) or not itens:
        raise ValueError("O gabarito precisa conter a lista 'perguntas'.")
    return [_pergunta_do_item(item) for item in itens]


def carregar_casos_calibracao(arquivo: Path = JUIZ_CALIBRACAO_FILE) -> list[CasoCalibracao]:
    """Load the hand-labelled judge calibration cases."""
    itens = _ler_json(arquivo).get("casos")
    if not isinstance(itens, list) or not itens:
        raise ValueError("O arquivo de calibração precisa conter a lista 'casos'.")
    casos = [CasoCalibracao(**item) for item in itens]
    for caso in casos:
        if caso.rotulo_esperado not in ROTULOS_AFIRMACAO:
            raise ValueError(f"Rótulo desconhecido no caso {caso.id}.")
    return casos


def normalizar_trecho(texto: str) -> str:
    """Collapse spaces, join hyphenated line breaks and fold case for substring checks."""
    sem_hifen = re.sub(r"­\s*|(?<=[A-Za-zÀ-ÿ])-\s+(?=[a-zà-ÿ])", "", texto)
    return re.sub(r"\s+", " ", sem_hifen.replace("’", "'")).strip().casefold()


def textos_por_pagina(paginas: Sequence[Pagina]) -> dict[int, str]:
    """Normalized body and table text of each printed page."""
    textos = {}
    for pagina in paginas:
        linhas_tabela = (linha for tabela in pagina.tabelas for linha in tabela.linhas)
        textos[pagina.pagina] = normalizar_trecho("\n".join((pagina.texto, *linhas_tabela)))
    return textos


def ancora_presente(pergunta: PerguntaAvaliacao, textos: Mapping[int, str]) -> bool:
    """Whether the literal anchor occurs in one of the gold pages."""
    ancora = normalizar_trecho(pergunta.trecho_ancora)
    return any(ancora in textos.get(pagina, "") for pagina in pergunta.paginas_gabarito)


def termo_ausente_no_pdf(pergunta: PerguntaAvaliacao, textos: Mapping[int, str]) -> bool:
    """Whether the out-of-scope question's key term is absent from the whole catalog."""
    termo = normalizar_trecho(pergunta.termo_ausente)
    return bool(termo) and not any(termo in texto for texto in textos.values())


def _ler_json(arquivo: Path) -> dict[str, Any]:
    try:
        with arquivo.open(encoding="utf-8") as fonte:
            documento = json.load(fonte)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Não foi possível carregar {arquivo.name}.") from error
    if not isinstance(documento, dict):
        raise ValueError(f"{arquivo.name} precisa ser um objeto JSON.")
    return documento


def _pergunta_do_item(item: Mapping[str, Any]) -> PerguntaAvaliacao:
    escopo = item.get("escopo")
    if escopo == ESCOPO_DENTRO:
        _exigir_campos(item, ("resposta_referencia", "paginas_gabarito", "trecho_ancora", "categoria"))
    elif escopo == ESCOPO_FORA:
        _exigir_campos(item, ("esperado", "termo_ausente"))
        if item["esperado"] != ESPERADO_ABSTENCAO:
            raise ValueError(f"A pergunta {item['id']} fora do escopo deve esperar abstenção.")
    else:
        raise ValueError(f"Escopo inválido na pergunta {item.get('id')}.")
    return PerguntaAvaliacao(
        id=str(item["id"]),
        escopo=escopo,
        pergunta=str(item["pergunta"]),
        split=str(item["split"]),
        estado=item.get("estado"),
        resposta_referencia=str(item.get("resposta_referencia", "")),
        paginas_gabarito=tuple(int(pagina) for pagina in item.get("paginas_gabarito", ())),
        secoes_gabarito=tuple(str(secao) for secao in item.get("secoes_gabarito", ())),
        trecho_ancora=str(item.get("trecho_ancora", "")),
        categoria=str(item.get("categoria", "")),
        esperado=str(item.get("esperado", "")),
        termo_ausente=str(item.get("termo_ausente", "")),
    )


def _exigir_campos(item: Mapping[str, Any], campos: Sequence[str]) -> None:
    faltantes = [campo for campo in ("id", "pergunta", "split", *campos) if not item.get(campo)]
    if faltantes:
        raise ValueError(f"A pergunta {item.get('id')} não tem os campos {faltantes}.")


# ------------------------------------------------------------- recuperação


def chunk_relevante_pagina(chunk: Mapping[str, Any], paginas_gabarito: Sequence[int]) -> bool:
    """A chunk is relevant by page when its page span touches a gold page."""
    inicio = chunk.get("pagina")
    if inicio is None:
        return False
    fim = chunk.get("pagina_fim") or inicio
    return any(inicio <= pagina <= fim for pagina in paginas_gabarito)


def chunk_relevante_estrito(chunk: Mapping[str, Any], trecho_ancora: str) -> bool:
    """A chunk is strictly relevant when it contains the literal anchor sentence."""
    return normalizar_trecho(trecho_ancora) in normalizar_trecho(str(chunk["texto"]))


def metricas_posicao(relevantes: Sequence[bool], k: int) -> dict[str, float]:
    """hit@k, precision@k, MRR@k and position-weighted context precision@k."""
    if k < 1:
        raise ValueError("k precisa ser positivo.")
    topo = list(relevantes[:k])
    acertos = sum(topo)
    primeiro = next((posicao for posicao, relevante in enumerate(topo, 1) if relevante), None)
    return {
        "hit": float(acertos > 0),
        "precision": acertos / k,
        "mrr": 1.0 / primeiro if primeiro else 0.0,
        "context_precision": _context_precision(topo),
    }


def anotar_paginas_legado(
    resultados: Sequence[Mapping[str, Any]], paginas: Sequence[Pagina]
) -> list[dict[str, Any]]:
    """Give legacy chunks (which carry no metadata) the pages whose text contains them."""
    anotados = []
    for resultado in resultados:
        copia = dict(resultado)
        encontradas = _paginas_dos_paragrafos(str(copia["texto"]), paginas)
        if encontradas:
            copia["pagina"], copia["pagina_fim"] = min(encontradas), max(encontradas)
        anotados.append(copia)
    return anotados


def avaliar_recuperacao_pergunta(
    pergunta: PerguntaAvaliacao, resultados: Sequence[Mapping[str, Any]], ks: Sequence[int]
) -> dict[str, Any]:
    """Per-question relevance flags and metrics for both relevance criteria."""
    por_criterio = {
        CRITERIO_PAGINA: [chunk_relevante_pagina(c, pergunta.paginas_gabarito) for c in resultados],
        CRITERIO_ESTRITO: [chunk_relevante_estrito(c, pergunta.trecho_ancora) for c in resultados],
    }
    return {
        "id": pergunta.id,
        "split": pergunta.split,
        "categoria": pergunta.categoria,
        "tem_estado": pergunta.estado is not None,
        "chunks": [_resumo_chunk(chunk) for chunk in resultados],
        "relevantes": por_criterio,
        "metricas": {
            criterio: {str(k): metricas_posicao(relevantes, k) for k in ks}
            for criterio, relevantes in por_criterio.items()
        },
    }


def executar_recuperacao(
    configuracao: ConfiguracaoRecuperacao, perguntas: Sequence[PerguntaAvaliacao], ks: Sequence[int] = KS_AVALIACAO
) -> list[dict[str, Any]]:
    """Retrieve the top max(ks) chunks of every in-scope question and score them."""
    registros = []
    for pergunta in perguntas:
        if pergunta.escopo != ESCOPO_DENTRO:
            continue
        estado = _estado_da_pergunta(configuracao.estados, pergunta)
        resultados = configuracao.retriever.buscar(pergunta.pergunta, estado=estado, k_final=max(ks))
        if configuracao.paginas_legado is not None:
            resultados = anotar_paginas_legado(resultados, configuracao.paginas_legado)
        registro = avaliar_recuperacao_pergunta(pergunta, resultados, ks)
        registros.append({**registro, "configuracao": configuracao.nome, "consulta": pergunta.pergunta})
    return registros


def resumir_recuperacao(
    registros: Sequence[Mapping[str, Any]], ks: Sequence[int] = KS_AVALIACAO
) -> list[dict[str, Any]]:
    """Mean metrics per group (split, split/category, with-state subset), criterion and k."""
    linhas = []
    for grupo, membros in _grupos_de_recuperacao(registros).items():
        for criterio in (CRITERIO_PAGINA, CRITERIO_ESTRITO):
            for k in ks:
                linhas.append(_linha_resumo(grupo, criterio, k, membros))
    return linhas


def retriever_com_peso(retriever: Retriever, peso_estado: float) -> Retriever:
    """Share models and index with `retriever` but change the section-boost weight."""
    preset = replace(retriever.configuracao.preset, peso_estado=peso_estado)
    configuracao = ConfiguracaoRetriever(preset, retriever.configuracao.termos_estado)
    return Retriever(retriever.componentes, configuracao)


def varrer_parametros(
    retriever: Retriever,
    perguntas: Sequence[PerguntaAvaliacao],
    estados: Mapping[str, EstadoOperacional],
) -> list[dict[str, Any]]:
    """Grid over PESO_ESTADO x LIMIAR_ABSTENCAO on the dev questions (in and out of scope)."""
    dev = [pergunta for pergunta in perguntas if pergunta.split == SPLIT_DEV]
    linhas = []
    for peso in GRADE_PESO_ESTADO:
        medidas = _medir_dev(retriever_com_peso(retriever, peso), dev, estados)
        linhas.extend(_linha_grade(peso, limiar, medidas) for limiar in GRADE_LIMIAR_ABSTENCAO)
    return linhas


def escolher_parametros(grade: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Max hit@4 among pairs that abstain on every out-of-scope dev question.

    Ties on hit@4, undue abstentions and distance to the current weight are broken by the median
    threshold, the one farthest from both edges of the feasible range.
    """
    if not grade:
        raise ValueError("A grade de calibração está vazia.")
    maximo_fora = max(linha["abstencao_fora_correta"] for linha in grade)
    viaveis = [linha for linha in grade if linha["abstencao_fora_correta"] == maximo_fora]
    melhor = _chave_de_escolha(min(viaveis, key=_chave_de_escolha))
    empatadas = sorted(
        (linha for linha in viaveis if _chave_de_escolha(linha) == melhor),
        key=lambda linha: linha["limiar_abstencao"],
    )
    return dict(empatadas[(len(empatadas) - 1) // 2])


def _context_precision(topo: Sequence[bool]) -> float:
    acumulado, soma = 0, 0.0
    for posicao, relevante in enumerate(topo, 1):
        if relevante:
            acumulado += 1
            soma += acumulado / posicao
    return soma / acumulado if acumulado else 0.0


def _paginas_dos_paragrafos(texto: str, paginas: Sequence[Pagina]) -> set[int]:
    encontradas: set[int] = set()
    for paragrafo in (item.strip() for item in re.split(r"\n\s*\n", texto)):
        if paragrafo:
            encontradas.update(p.pagina for p in paginas if paragrafo in p.texto_original)
    return encontradas


def _resumo_chunk(chunk: Mapping[str, Any]) -> dict[str, Any]:
    campos = ("id", "pagina", "pagina_fim", "secao", "secao_titulo")
    escores = ("score_denso", "score_rerank", "score_rerank_bruto", "score_final")
    resumo = {campo: chunk.get(campo) for campo in campos}
    resumo.update({campo: chunk[campo] for campo in escores if campo in chunk})
    return resumo


def _estado_da_pergunta(
    estados: Mapping[str, EstadoOperacional] | None, pergunta: PerguntaAvaliacao
) -> EstadoOperacional | None:
    if not estados or pergunta.estado is None:
        return None
    return estados[pergunta.estado]


def _grupos_de_recuperacao(registros: Sequence[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    grupos: dict[str, list[Mapping[str, Any]]] = {}
    for registro in registros:
        chaves = [registro["split"], f"{registro['split']}/{registro['categoria']}"]
        if registro["tem_estado"]:
            chaves.append("com_estado")
        for chave in chaves:
            grupos.setdefault(chave, []).append(registro)
    return dict(sorted(grupos.items()))


def _linha_resumo(
    grupo: str, criterio: str, k: int, membros: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    linha: dict[str, Any] = {"grupo": grupo, "criterio": criterio, "k": k, "n": len(membros)}
    for metrica in ("hit", "precision", "mrr", "context_precision"):
        valores = [membro["metricas"][criterio][str(k)][metrica] for membro in membros]
        linha[metrica] = sum(valores) / len(valores)
    return linha


def _medir_dev(
    retriever: Retriever,
    dev: Sequence[PerguntaAvaliacao],
    estados: Mapping[str, EstadoOperacional],
) -> list[dict[str, Any]]:
    medidas = []
    for pergunta in dev:
        estado = _estado_da_pergunta(estados, pergunta)
        resultados = retriever.buscar(pergunta.pergunta, estado=estado, k_final=K_FINAL)
        melhor = float(resultados[0]["score_rerank_bruto"]) if resultados else -math.inf
        acerto = any(chunk_relevante_pagina(c, pergunta.paginas_gabarito) for c in resultados)
        medidas.append({"escopo": pergunta.escopo, "melhor": melhor, "hit4": acerto})
    return medidas


def _linha_grade(peso: float, limiar: float, medidas: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    dentro = [medida for medida in medidas if medida["escopo"] == ESCOPO_DENTRO]
    fora = [medida for medida in medidas if medida["escopo"] == ESCOPO_FORA]
    return {
        "peso_estado": peso,
        "limiar_abstencao": limiar,
        "hit4_dentro": sum(medida["hit4"] for medida in dentro),
        "n_dentro": len(dentro),
        "abstencao_fora_correta": sum(medida["melhor"] < limiar for medida in fora),
        "n_fora": len(fora),
        "abstencao_dentro_indevida": sum(medida["melhor"] < limiar for medida in dentro),
    }


def _chave_de_escolha(linha: Mapping[str, Any]) -> tuple[float, ...]:
    return (
        -linha["hit4_dentro"],
        linha["abstencao_dentro_indevida"],
        abs(linha["peso_estado"] - PESO_ESTADO),
        linha["peso_estado"],
    )


# -------------------------------------------------------------------- juiz


class Juiz:
    """Claim-level and coverage judge, always run on MODELO_JUIZ through the injected client."""

    def __init__(self, cliente: CompletionClient, modelo: str = MODELO_JUIZ) -> None:
        if modelo == MODELO_GERADOR:
            raise ValueError("O juiz não pode usar o modelo do gerador.")
        self._cliente = cliente
        self.modelo = modelo

    def rotular(self, afirmacao: str, contexto: str) -> str | None:
        """Raw judge label for one claim, or None when the reply carries no valid label."""
        conteudo = f"CONTEXTO\n{contexto}\n\nAFIRMAÇÃO\n{afirmacao}"
        resposta = self._completar(PROMPT_JUIZ_AFIRMACAO, conteudo)
        achado = re.search(PADRAO_ROTULO_AFIRMACAO, _sem_acentos(resposta).upper())
        return achado.group(1) if achado else None

    def classificar_cobertura(self, pergunta: str, resposta: str, referencia: str) -> str | None:
        """COBRE / PARCIAL / NAO_COBRE for an answer against the reference, or None."""
        conteudo = f"PERGUNTA\n{pergunta}\n\nREFERÊNCIA\n{referencia}\n\nRESPOSTA\n{resposta}"
        retorno = self._completar(PROMPT_JUIZ_COBERTURA, conteudo)
        achado = re.search(PADRAO_ROTULO_COBERTURA, _sem_acentos(retorno).upper())
        return achado.group(1).replace(" ", "_") if achado else None

    def _completar(self, prompt_sistema: str, conteudo: str) -> str:
        mensagens = [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": conteudo},
        ]
        return self._cliente.complete(self.modelo, mensagens)


def limpar_resposta(texto: str) -> str:
    """Answer text without the confidence line and the [p., seç.] citations."""
    sem_confianca = re.sub(PADRAO_LINHA_CONFIANCA, "", texto)
    return re.sub(PADRAO_CITACAO_ASSISTENTE, "", sem_confianca).strip()


def dividir_afirmacoes(texto: str) -> list[str]:
    """Sentence-level claims (no LLM), ignoring confidence line, citations and abstention."""
    limpo = limpar_resposta(texto)
    afirmacoes = []
    for bloco in re.split(r"\n+", limpo):
        sem_lista = re.sub(PADRAO_MARCADOR_LISTA, "", bloco)
        for frase in re.split(PADRAO_DIVISAO_FRASES, sem_lista):
            afirmacao = _limpar_afirmacao(frase)
            if _e_afirmacao(afirmacao):
                afirmacoes.append(afirmacao)
    return afirmacoes


def numeros_ausentes(afirmacao: str, contexto: str) -> list[str]:
    """Numbers written in the claim that do not occur anywhere in the context."""
    presentes = _numeros_do_texto(contexto)
    return [numero for numero in _numeros_do_texto(afirmacao) if numero not in presentes]


def marcador_externo(afirmacao: str, contexto: str) -> str | None:
    """First external-knowledge marker in the claim that the context itself does not use."""
    afirmacao_comparavel = _comparavel(afirmacao)
    contexto_comparavel = _comparavel(contexto)
    for marcador in MARCADORES_CONHECIMENTO_EXTERNO:
        if marcador in afirmacao_comparavel and marcador not in contexto_comparavel:
            return marcador
    return None


def aplicar_guardas(afirmacao: str, contexto: str, rotulo_juiz: str | None) -> tuple[str, str | None]:
    """Deterministic guards override the judge: absent numbers and external markers are EXTERNA."""
    if numeros_ausentes(afirmacao, contexto):
        return ROTULO_EXTERNA, GUARDA_NUMERO
    if marcador_externo(afirmacao, contexto):
        return ROTULO_EXTERNA, GUARDA_MARCADOR
    if rotulo_juiz is None:
        return ROTULO_EXTERNA, GUARDA_JUIZ_INVALIDO
    return rotulo_juiz, None


def rotular_afirmacao(juiz: Juiz, afirmacao: str, contexto: str) -> RotuloAfirmacao:
    """Ask the judge, then apply the deterministic guards."""
    rotulo_juiz = juiz.rotular(afirmacao, contexto)
    rotulo, guarda = aplicar_guardas(afirmacao, contexto, rotulo_juiz)
    return RotuloAfirmacao(afirmacao, rotulo_juiz, rotulo, guarda)


def faithfulness(rotulos: Sequence[str]) -> float | None:
    """SUSTENTADA / (SUSTENTADA + EXTERNA + CONTRADIZ); META is ignored; None without claims."""
    sustentadas = sum(rotulo == ROTULO_SUSTENTADA for rotulo in rotulos)
    factuais = sustentadas + sum(rotulo in (ROTULO_EXTERNA, ROTULO_CONTRADIZ) for rotulo in rotulos)
    return sustentadas / factuais if factuais else None


def contexto_dos_chunks(chunks: Sequence[Mapping[str, Any]]) -> str:
    """The context block the generator saw, with the same [p., seç.] labels."""
    return "\n\n".join(f"[p. {c['pagina']}, seç. {c['secao']}] {c['texto']}" for c in chunks)


def avaliar_fidelidade(texto: str, chunks: Sequence[Mapping[str, Any]], juiz: Juiz) -> dict[str, Any]:
    """Label every claim of an answer against its chunks and compute faithfulness."""
    contexto = contexto_dos_chunks(chunks)
    rotuladas = [rotular_afirmacao(juiz, a, contexto) for a in dividir_afirmacoes(texto)]
    rotulos = [item.rotulo for item in rotuladas]
    return {
        "faithfulness": faithfulness(rotulos),
        "contagem": {rotulo: rotulos.count(rotulo) for rotulo in ROTULOS_AFIRMACAO},
        "afirmacoes": [_dict_rotulo(item) for item in rotuladas],
    }


def similaridade_cosseno(vetor_a: Sequence[float], vetor_b: Sequence[float]) -> float:
    """Cosine similarity of two vectors; 0.0 when either has no magnitude."""
    a = [float(valor) for valor in vetor_a]
    b = [float(valor) for valor in vetor_b]
    norma = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return sum(x * y for x, y in zip(a, b, strict=True)) / norma if norma else 0.0


def avaliar_relevancia(pergunta: PerguntaAvaliacao, texto: str, contexto: ContextoRespostas) -> dict[str, Any]:
    """Coverage label and points from the judge plus embedding cosine against the reference."""
    resposta = limpar_resposta(texto)
    rotulo = contexto.juiz.classificar_cobertura(pergunta.pergunta, resposta, pergunta.resposta_referencia)
    prefixo = PREFIXO_QUERY_NOVO
    vetores = contexto.embedding.encode([prefixo + resposta, prefixo + pergunta.resposta_referencia])
    final = rotulo or COBERTURA_NAO_COBRE
    return {
        "cobertura": final,
        "pontos": PONTOS_COBERTURA[final],
        "juiz_invalido": rotulo is None,
        "cosseno": similaridade_cosseno(vetores[0], vetores[1]),
    }


# --------------------------------------------------------------- calibração


def calibrar_juiz(juiz: Juiz, casos: Sequence[CasoCalibracao]) -> dict[str, Any]:
    """Run the judge on every case; report raw-judge and judge+guards metrics per split."""
    registros = []
    for caso in casos:
        resultado = rotular_afirmacao(juiz, caso.afirmacao, caso.contexto)
        registros.append(_registro_calibracao(caso, resultado))
    return {
        "modelo_juiz": juiz.modelo,
        "casos": registros,
        "metricas": {split: _metricas_calibracao(registros, split) for split in (SPLIT_DEV, SPLIT_TESTE, "todos")},
    }


def matriz_confusao(esperados: Sequence[str], previstos: Sequence[str | None]) -> dict[str, dict[str, int]]:
    """Counts of predicted label (columns) for each expected label (rows)."""
    colunas = (*ROTULOS_AFIRMACAO, "INVALIDO")
    matriz = {esperado: {coluna: 0 for coluna in colunas} for esperado in ROTULOS_AFIRMACAO}
    for esperado, previsto in zip(esperados, previstos, strict=True):
        matriz[esperado][previsto if previsto in ROTULOS_AFIRMACAO else "INVALIDO"] += 1
    return matriz


def metricas_rotulos(esperados: Sequence[str], previstos: Sequence[str | None]) -> dict[str, Any]:
    """Accuracy, EXTERNA recall and precision, and the confusion matrix."""
    total = len(esperados)
    acertos = sum(e == p for e, p in zip(esperados, previstos, strict=True))
    externas = sum(e == ROTULO_EXTERNA for e in esperados)
    externas_certas = sum(e == p == ROTULO_EXTERNA for e, p in zip(esperados, previstos, strict=True))
    previstas_externas = sum(p == ROTULO_EXTERNA for p in previstos)
    return {
        "n": total,
        "acuracia": acertos / total if total else None,
        "revocacao_externa": externas_certas / externas if externas else None,
        "precisao_externa": externas_certas / previstas_externas if previstas_externas else None,
        "matriz_confusao": matriz_confusao(esperados, previstos),
    }


def _registro_calibracao(caso: CasoCalibracao, resultado: RotuloAfirmacao) -> dict[str, Any]:
    return {
        "id": caso.id,
        "split": caso.split,
        "afirmacao": caso.afirmacao,
        "esperado": caso.rotulo_esperado,
        "juiz": resultado.rotulo_juiz,
        "final": resultado.rotulo,
        "guarda": resultado.guarda,
    }


def _metricas_calibracao(registros: Sequence[Mapping[str, Any]], split: str) -> dict[str, Any]:
    selecionados = [r for r in registros if split == "todos" or r["split"] == split]
    esperados = [r["esperado"] for r in selecionados]
    return {
        "juiz_isolado": metricas_rotulos(esperados, [r["juiz"] for r in selecionados]),
        "juiz_com_guardas": metricas_rotulos(esperados, [r["final"] for r in selecionados]),
    }


# --------------------------------------------------------------- respostas


def construir_estados(alertas: Sequence[Alerta]) -> dict[str, EstadoOperacional]:
    """Synthetic operational states: the state at the start of the first matching alert."""
    return {chave: _estado_do_cenario(alertas, *regra) for chave, regra in ESTADOS_AVALIACAO.items()}


def abstencao_efetiva(resposta: Resposta) -> bool:
    """True when the assistant abstained, or the generator answered with the fixed phrase."""
    return resposta.abstencao or _comparavel(limpar_resposta(resposta.texto)) == _comparavel(FRASE_ABSTENCAO)


def avaliar_resposta(
    pergunta: PerguntaAvaliacao, resposta: Resposta, contexto: ContextoRespostas
) -> dict[str, Any]:
    """Faithfulness, relevancy and abstention outcome of one answer."""
    abstencao = abstencao_efetiva(resposta)
    registro = _registro_base(pergunta, resposta, abstencao)
    registro["modelo_juiz"] = contexto.juiz.modelo
    if abstencao:
        registro["faithfulness"] = 1.0
    else:
        fidelidade = avaliar_fidelidade(resposta.texto, resposta.chunks, contexto.juiz)
        registro.update(fidelidade)
    if pergunta.escopo == ESCOPO_FORA:
        registro.update(_desfecho_fora(abstencao))
    else:
        registro.update(_desfecho_dentro(pergunta, resposta, abstencao, contexto))
    return registro


def executar_respostas(
    contexto: ContextoRespostas, perguntas: Sequence[PerguntaAvaliacao]
) -> list[dict[str, Any]]:
    """Answer and judge every question; an API failure marks the question as `erro`, never swaps model."""
    registros = []
    for pergunta in perguntas:
        contexto.assistente.reiniciar()
        estado = _estado_da_pergunta(contexto.estados, pergunta)
        try:
            resposta = contexto.assistente.responder(pergunta.pergunta, estado=estado)
            registros.append(avaliar_resposta(pergunta, resposta, contexto))
        except OpenRouterRequestError as erro:
            registros.append(_registro_erro(pergunta, erro))
    verificar_modelo_unico(registros)
    return registros


def verificar_modelo_unico(registros: Sequence[Mapping[str, Any]]) -> None:
    """Fail when any answer was produced by a model other than MODELO_GERADOR."""
    modelos = {registro["modelo"] for registro in registros}
    if modelos - {MODELO_GERADOR}:
        raise RuntimeError(f"Modelos misturados na avaliação: {sorted(modelos)}.")


def resumir_respostas(registros: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Means, abstention outcomes and error counts, overall and per split and category."""
    validos = [registro for registro in registros if not registro.get("erro")]
    return {
        "geral": _resumo_respostas(registros, validos),
        **{split: _resumo_grupo(registros, split) for split in (SPLIT_DEV, SPLIT_TESTE)},
        "por_categoria": {
            categoria: _resumo_respostas(
                [r for r in registros if r.get("categoria") == categoria],
                [r for r in validos if r.get("categoria") == categoria],
            )
            for categoria in CATEGORIAS_AVALIACAO
        },
    }


def gravar_json(arquivo: Path, dados: Any) -> None:
    """Write evaluation results as UTF-8 JSON."""
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    with arquivo.open("w", encoding="utf-8") as destino:
        json.dump(dados, destino, ensure_ascii=False, indent=2)
        destino.write("\n")


def _resumo_grupo(registros: Sequence[Mapping[str, Any]], split: str) -> dict[str, Any]:
    do_split = [r for r in registros if r.get("split") == split]
    return _resumo_respostas(do_split, [r for r in do_split if not r.get("erro")])


def _resumo_respostas(
    todos: Sequence[Mapping[str, Any]], validos: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    dentro = [r for r in validos if r["escopo"] == ESCOPO_DENTRO]
    fora = [r for r in validos if r["escopo"] == ESCOPO_FORA]
    return {
        "n": len(todos),
        "erros": len(todos) - len(validos),
        "faithfulness_media": _media(r.get("faithfulness") for r in validos),
        "relevancy_media": _media(r.get("pontos") for r in dentro),
        "cosseno_medio": _media(r.get("cosseno") for r in dentro),
        "abstencoes_indevidas": sum(bool(r.get("abstencao_indevida")) for r in dentro),
        "abstencoes_corretas": sum(bool(r.get("abstencao_correta")) for r in fora),
        "alucinacoes_fora_escopo": sum(bool(r.get("alucinacao_fora_escopo")) for r in fora),
    }


def _media(valores: Any) -> float | None:
    validos = [float(valor) for valor in valores if valor is not None]
    return sum(validos) / len(validos) if validos else None


def _registro_base(pergunta: PerguntaAvaliacao, resposta: Resposta, abstencao: bool) -> dict[str, Any]:
    return {
        "id": pergunta.id,
        "escopo": pergunta.escopo,
        "split": pergunta.split,
        "categoria": pergunta.categoria,
        "pergunta": pergunta.pergunta,
        "estado": pergunta.estado,
        "modelo": resposta.modelo,
        "consulta": resposta.consulta_usada,
        "chunks": [{**_resumo_chunk(chunk), "texto": chunk["texto"]} for chunk in resposta.chunks],
        "resposta": resposta.texto,
        "confianca": resposta.confianca,
        "abstencao": abstencao,
        "fontes": resposta.fontes,
        "citacao_invalida": resposta.citacao_invalida,
    }


def _desfecho_fora(abstencao: bool) -> dict[str, Any]:
    return {"abstencao_correta": abstencao, "alucinacao_fora_escopo": not abstencao}


def _desfecho_dentro(
    pergunta: PerguntaAvaliacao, resposta: Resposta, abstencao: bool, contexto: ContextoRespostas
) -> dict[str, Any]:
    if abstencao:
        return {"abstencao_indevida": True, "cobertura": COBERTURA_NAO_COBRE, "pontos": 0.0, "cosseno": None}
    return {"abstencao_indevida": False, **avaliar_relevancia(pergunta, resposta.texto, contexto)}


def _registro_erro(pergunta: PerguntaAvaliacao, erro: Exception) -> dict[str, Any]:
    return {
        "id": pergunta.id,
        "escopo": pergunta.escopo,
        "split": pergunta.split,
        "categoria": pergunta.categoria,
        "pergunta": pergunta.pergunta,
        "modelo": MODELO_GERADOR,
        "erro": True,
        "mensagem_erro": str(erro),
    }


def _estado_do_cenario(alertas: Sequence[Alerta], prefixo: str, severidade: str) -> EstadoOperacional:
    for alerta in alertas:
        if alerta.severidade != severidade or not _grandeza_casa(alerta.grandeza, prefixo):
            continue
        estado = construir_estado_operacional(alertas, alerta.inicio)
        if all(_grandeza_casa(ativo.grandeza, prefixo) for ativo in estado.alertas_ativos):
            return estado
    raise ValueError(f"Nenhum estado {severidade} só de '{prefixo}' nos alertas fornecidos.")


def _grandeza_casa(grandeza: str, prefixo: str) -> bool:
    return prefixo in _sem_acentos(grandeza).casefold()


def _dict_rotulo(item: RotuloAfirmacao) -> dict[str, Any]:
    return {
        "afirmacao": item.afirmacao,
        "rotulo_juiz": item.rotulo_juiz,
        "rotulo": item.rotulo,
        "guarda": item.guarda,
    }


def _limpar_afirmacao(frase: str) -> str:
    colapsada = re.sub(r"\s+", " ", frase).strip()
    return re.sub(r"\s+([.,;:!?])", r"\1", colapsada)


def _e_afirmacao(frase: str) -> bool:
    if not re.search(r"[A-Za-zÀ-ÿ]", frase):
        return False
    return _comparavel(frase).rstrip(".") != _comparavel(FRASE_ABSTENCAO).rstrip(".")


def _numeros_do_texto(texto: str) -> set[str]:
    sem_colchetes = re.sub(PADRAO_COLCHETES, " ", texto)
    return {_normalizar_numero(item) for item in re.findall(PADRAO_NUMERO_AFIRMACAO, sem_colchetes)}


def _normalizar_numero(numero: str) -> str:
    if re.fullmatch(PADRAO_MILHAR, numero):
        return numero.replace(".", "")
    return numero.replace(",", ".")


def _sem_acentos(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(caractere for caractere in decomposto if not unicodedata.combining(caractere))


def _comparavel(texto: str) -> str:
    return re.sub(r"\s+", " ", _sem_acentos(texto).casefold()).strip()

