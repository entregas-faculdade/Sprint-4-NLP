from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import pytest

from src.pln.alertas import Alerta
from src.pln.assistente import Resposta
from src.pln.avaliacao import (
    CasoCalibracao,
    ContextoRespostas,
    Juiz,
    PerguntaAvaliacao,
    aplicar_guardas,
    ancora_presente,
    anotar_paginas_legado,
    avaliar_resposta,
    calibrar_juiz,
    carregar_casos_calibracao,
    carregar_gabarito,
    chunk_relevante_estrito,
    chunk_relevante_pagina,
    construir_estados,
    dividir_afirmacoes,
    escolher_parametros,
    executar_respostas,
    faithfulness,
    marcador_externo,
    metricas_posicao,
    metricas_rotulos,
    numeros_ausentes,
    resumir_respostas,
    retriever_com_peso,
    rotular_afirmacao,
    similaridade_cosseno,
    termo_ausente_no_pdf,
    textos_por_pagina,
    varrer_parametros,
    verificar_modelo_unico,
)
from src.pln.config import (
    CATEGORIAS_AVALIACAO,
    ESTADOS_AVALIACAO,
    FRASE_ABSTENCAO,
    GRADE_LIMIAR_ABSTENCAO,
    GRADE_PESO_ESTADO,
    GUARDA_JUIZ_INVALIDO,
    GUARDA_MARCADOR,
    GUARDA_NUMERO,
    MODELO_GERADOR,
    MODELO_JUIZ,
    NOVO,
)
from src.pln.llm import OpenRouterRequestError
from src.pln.rag import ComponentesRetriever, ConfiguracaoRetriever, Pagina, Retriever, extrair_paginas


class ClienteFalso:
    """Chat client that answers from a function of (model, last user message)."""

    def __init__(self, responder: Callable[[str, str], str]) -> None:
        self._responder = responder
        self.chamadas: list[tuple[str, str]] = []

    def complete(self, model_id: str, messages: list[dict[str, str]]) -> str:
        conteudo = messages[-1]["content"]
        self.chamadas.append((model_id, conteudo))
        return self._responder(model_id, conteudo)


class EmbeddingFalso:
    def encode(self, sentences: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] if "motor" in frase else [0.0, 1.0] for frase in sentences]


class AssistenteFalso:
    def __init__(self, respostas: dict[str, Resposta | Exception]) -> None:
        self._respostas = respostas
        self.reinicios = 0

    def reiniciar(self) -> None:
        self.reinicios += 1

    def responder(self, pergunta: str, estado: Any = None) -> Resposta:
        resultado = self._respostas[pergunta]
        if isinstance(resultado, Exception):
            raise resultado
        return resultado


def _chunk(texto: str = "A carcaça é de ferro fundido FC-200.", pagina: int = 9, **extra: Any) -> dict[str, Any]:
    return {"id": f"c-{pagina}", "pagina": pagina, "pagina_fim": pagina, "secao": "3.1",
            "secao_titulo": "Carcaça", "texto": texto, "score_rerank_bruto": 5.0, **extra}


def _resposta(texto: str, abstencao: bool = False, modelo: str = MODELO_GERADOR) -> Resposta:
    return Resposta(texto, [], "Média", abstencao, False, True, modelo, "consulta", [_chunk()], "estado")


def _pergunta(escopo: str = "dentro", **extra: Any) -> PerguntaAvaliacao:
    base: dict[str, Any] = {
        "id": "q1", "escopo": escopo, "pergunta": "De que material é a carcaça?", "split": "teste", "estado": None,
        "resposta_referencia": "Ferro fundido FC-200.", "paginas_gabarito": (9,), "categoria": "mecânica",
        "trecho_ancora": "ferro fundido FC-200",
    }
    return PerguntaAvaliacao(**{**base, **extra})


def _juiz(rotulo: str = "SUSTENTADA", cobertura: str = "COBRE") -> tuple[Juiz, ClienteFalso]:
    def responder(_modelo: str, conteudo: str) -> str:
        return cobertura if conteudo.startswith("PERGUNTA") else rotulo

    cliente = ClienteFalso(responder)
    return Juiz(cliente), cliente


def _contexto(juiz: Juiz, assistente: AssistenteFalso) -> ContextoRespostas:
    return ContextoRespostas(assistente, juiz, EmbeddingFalso(), {})  # type: ignore[arg-type]


# ------------------------------------------------------------ afirmações


def test_divide_em_frases_ignorando_confianca_citacao_e_abstencao() -> None:
    texto = (
        "A carcaça é de ferro fundido FC-200 [p. 9, seç. 3.1]. Os pés são maciços [p. 9, seç. 3.1].\n"
        f"- Há quatro olhais.\n{FRASE_ABSTENCAO}\nConfiança: Alta"
    )

    assert dividir_afirmacoes(texto) == [
        "A carcaça é de ferro fundido FC-200.",
        "Os pés são maciços.",
        "Há quatro olhais.",
    ]


def test_divisao_nao_quebra_numero_decimal_nem_milhar() -> None:
    assert dividir_afirmacoes("A vida útil é de 25.000 horas e o fator é 1,25 [p. 14, seç. 5.2].") == [
        "A vida útil é de 25.000 horas e o fator é 1,25."
    ]


def test_resposta_so_de_abstencao_nao_tem_afirmacao() -> None:
    assert dividir_afirmacoes(f"{FRASE_ABSTENCAO}\nConfiança: Baixa") == []


# --------------------------------------------------------------- guardas


def test_guarda_numerica_reprova_numero_ausente_do_contexto() -> None:
    contexto = "[p. 14, seç. 5.2] Os rolamentos têm vida útil L10h de 25.000 horas."

    assert numeros_ausentes("A vida útil chega a 40.000 horas.", contexto) == ["40000"]
    assert numeros_ausentes("A vida útil é de 25000 horas.", contexto) == []
    assert numeros_ausentes("Os motores W22 têm rolamentos L10h.", contexto) == []


def test_guarda_numerica_ignora_cabecalho_com_numero_de_pagina() -> None:
    assert numeros_ausentes("Veja a página 14.", "[Seção 5.2 — Rolamentos | p. 14] Texto sem números.") == ["14"]


def test_guarda_de_marcador_externo_e_ignorada_quando_o_contexto_usa_a_palavra() -> None:
    assert marcador_externo("Em geral, o motor dura mais.", "Contexto sobre carcaça.") == "em geral"
    assert marcador_externo("Pelo conhecimento geral, é bom.", "x") == "conhecimento geral"
    assert marcador_externo("Contatos normalmente fechados.", "tipo NF (normalmente fechados)") is None


def test_guardas_prevalecem_sobre_o_juiz() -> None:
    contexto = "A carcaça é de ferro fundido."

    assert aplicar_guardas("A carcaça pesa 80 kg.", contexto, "SUSTENTADA") == ("EXTERNA", GUARDA_NUMERO)
    assert aplicar_guardas("Normalmente é de ferro.", contexto, "SUSTENTADA") == ("EXTERNA", GUARDA_MARCADOR)
    assert aplicar_guardas("É de ferro fundido.", contexto, "SUSTENTADA") == ("SUSTENTADA", None)
    assert aplicar_guardas("É de ferro fundido.", contexto, None) == ("EXTERNA", GUARDA_JUIZ_INVALIDO)


def test_juiz_extrai_rotulo_do_texto_e_externa_nunca_vira_sustentada() -> None:
    juiz, _ = _juiz(rotulo="Rótulo: externa")

    resultado = rotular_afirmacao(juiz, "A graxa é de lítio.", "A carcaça é de ferro.")

    assert resultado.rotulo_juiz == "EXTERNA"
    assert resultado.rotulo == "EXTERNA"


def test_juiz_sem_rotulo_valido_conta_como_externa() -> None:
    juiz, _ = _juiz(rotulo="não sei")

    resultado = rotular_afirmacao(juiz, "A carcaça é de ferro.", "A carcaça é de ferro.")

    assert (resultado.rotulo_juiz, resultado.rotulo, resultado.guarda) == (None, "EXTERNA", GUARDA_JUIZ_INVALIDO)


def test_faithfulness_e_sustentadas_sobre_factuais_e_ignora_meta() -> None:
    assert faithfulness(["SUSTENTADA", "SUSTENTADA", "EXTERNA", "CONTRADIZ", "META"]) == pytest.approx(0.5)
    assert faithfulness(["EXTERNA", "EXTERNA"]) == 0.0
    assert faithfulness(["META"]) is None
    assert faithfulness([]) is None


def test_juiz_e_gerador_sao_modelos_de_familias_diferentes() -> None:
    familia = lambda modelo: modelo.split("/")[-1].split("-")[0]  # noqa: E731

    assert MODELO_JUIZ != MODELO_GERADOR
    assert familia(MODELO_JUIZ) != familia(MODELO_GERADOR)
    with pytest.raises(ValueError):
        Juiz(ClienteFalso(lambda *_: ""), modelo=MODELO_GERADOR)


# ------------------------------------------------------------ recuperação


def test_metricas_de_recuperacao_com_listas_conhecidas() -> None:
    metricas = metricas_posicao([False, True, False, True], 4)

    assert metricas["hit"] == 1.0
    assert metricas["precision"] == 0.5
    assert metricas["mrr"] == 0.5
    assert metricas["context_precision"] == pytest.approx((1 / 2 + 2 / 4) / 2)
    assert metricas_posicao([False, True, False, True], 1) == {
        "hit": 0.0, "precision": 0.0, "mrr": 0.0, "context_precision": 0.0,
    }
    assert metricas_posicao([True, True, True, True], 4)["context_precision"] == 1.0


def test_metricas_sem_chunk_relevante_sao_zero() -> None:
    assert metricas_posicao([False, False], 4) == {
        "hit": 0.0, "precision": 0.0, "mrr": 0.0, "context_precision": 0.0,
    }
    with pytest.raises(ValueError):
        metricas_posicao([True], 0)


def test_relevancia_por_pagina_e_estrita() -> None:
    chunk = _chunk("A carcaça é produzida em ferro\nfundido FC-200 e otimiza a troca.", pagina=9)
    entre_paginas = {**chunk, "pagina": 8, "pagina_fim": 9}

    assert chunk_relevante_pagina(chunk, (9,)) and not chunk_relevante_pagina(chunk, (10,))
    assert chunk_relevante_pagina(entre_paginas, (9,))
    assert not chunk_relevante_pagina({**chunk, "pagina": None}, (9,))
    assert chunk_relevante_estrito(chunk, "é produzida em ferro fundido FC-200")
    assert not chunk_relevante_estrito(chunk, "é produzida em alumínio")


def test_chunk_legado_recebe_as_paginas_em_que_o_texto_aparece() -> None:
    paginas = [
        Pagina(1, "x", "Um parágrafo da página um.\n\nOutro da um."),
        Pagina(2, "y", "Texto da página dois."),
    ]
    resultados = [{"id": "l1", "texto": "Um parágrafo da página um.\n\nTexto da página dois."}]

    anotado = anotar_paginas_legado(resultados, paginas)

    assert (anotado[0]["pagina"], anotado[0]["pagina_fim"]) == (1, 2)
    assert "pagina" not in resultados[0]


# --------------------------------------------------------------- respostas


def test_abstencao_em_pergunta_dentro_do_escopo_vale_zero_sem_chamar_o_juiz() -> None:
    juiz, cliente = _juiz()
    resposta = _resposta(f"{FRASE_ABSTENCAO}\nConfiança: Baixa", abstencao=True)

    registro = avaliar_resposta(_pergunta(), resposta, _contexto(juiz, AssistenteFalso({})))

    assert (registro["cobertura"], registro["pontos"], registro["abstencao_indevida"]) == ("NAO_COBRE", 0.0, True)
    assert registro["faithfulness"] == 1.0
    assert cliente.chamadas == []


def test_resposta_factual_a_pergunta_fora_do_escopo_e_alucinacao() -> None:
    juiz, _ = _juiz()
    resposta = _resposta("O preço é alto [p. 9, seç. 3.1].\nConfiança: Média")
    pergunta = _pergunta("fora", esperado="abstencao")

    registro = avaliar_resposta(pergunta, resposta, _contexto(juiz, AssistenteFalso({})))

    assert registro["alucinacao_fora_escopo"] is True
    assert registro["abstencao_correta"] is False


def test_abstencao_em_pergunta_fora_do_escopo_e_correta() -> None:
    juiz, _ = _juiz()
    resposta = _resposta(f"{FRASE_ABSTENCAO}\nConfiança: Baixa", abstencao=True)

    registro = avaliar_resposta(_pergunta("fora"), resposta, _contexto(juiz, AssistenteFalso({})))

    assert registro["abstencao_correta"] is True and registro["alucinacao_fora_escopo"] is False
    assert registro["faithfulness"] == 1.0


def test_resposta_com_frase_de_abstencao_do_proprio_gerador_conta_como_abstencao() -> None:
    juiz, cliente = _juiz()
    resposta = _resposta(f"{FRASE_ABSTENCAO}\nConfiança: Média", abstencao=False)

    registro = avaliar_resposta(_pergunta("fora"), resposta, _contexto(juiz, AssistenteFalso({})))

    assert registro["abstencao"] is True and cliente.chamadas == []


def test_resposta_dentro_do_escopo_registra_fidelidade_por_afirmacao_e_relevancia() -> None:
    juiz, _ = _juiz(rotulo="SUSTENTADA", cobertura="PARCIAL")
    resposta = _resposta("A carcaça é de ferro fundido FC-200 [p. 9, seç. 3.1]. Pesa 80 kg.\nConfiança: Média")

    registro = avaliar_resposta(_pergunta(), resposta, _contexto(juiz, AssistenteFalso({})))

    assert registro["faithfulness"] == 0.5
    assert registro["contagem"]["EXTERNA"] == 1
    assert registro["afirmacoes"][1]["guarda"] == GUARDA_NUMERO
    assert (registro["cobertura"], registro["pontos"]) == ("PARCIAL", 0.5)
    assert registro["modelo"] == MODELO_GERADOR and registro["modelo_juiz"] == MODELO_JUIZ
    assert registro["cosseno"] == pytest.approx(1.0)


def test_juiz_roda_so_no_modelo_juiz() -> None:
    juiz, cliente = _juiz()
    resposta = _resposta("A carcaça é de ferro fundido FC-200.\nConfiança: Média")

    avaliar_resposta(_pergunta(), resposta, _contexto(juiz, AssistenteFalso({})))

    assert {modelo for modelo, _ in cliente.chamadas} == {MODELO_JUIZ}


def test_erro_de_api_marca_a_pergunta_sem_trocar_de_modelo() -> None:
    juiz, _ = _juiz()
    boa = _resposta("A carcaça é de ferro fundido FC-200.\nConfiança: Média")
    assistente = AssistenteFalso({"p-ok": boa, "p-erro": OpenRouterRequestError("falhou")})
    perguntas = [_pergunta(id="a", pergunta="p-ok"), _pergunta(id="b", pergunta="p-erro")]

    registros = executar_respostas(_contexto(juiz, assistente), perguntas)

    assert assistente.reinicios == 2
    assert [registro.get("erro") for registro in registros] == [None, True]
    assert {registro["modelo"] for registro in registros} == {MODELO_GERADOR}
    assert resumir_respostas(registros)["geral"]["erros"] == 1


def test_modelos_misturados_sao_rejeitados() -> None:
    with pytest.raises(RuntimeError):
        verificar_modelo_unico([{"modelo": MODELO_GERADOR}, {"modelo": "outro/modelo"}])


def test_resumo_de_respostas_conta_alucinacao_e_abstencoes() -> None:
    registros = [
        {"escopo": "dentro", "split": "teste", "categoria": "mecânica", "faithfulness": 1.0, "pontos": 1.0,
         "cosseno": 0.8, "abstencao_indevida": False},
        {"escopo": "dentro", "split": "teste", "categoria": "mecânica", "faithfulness": 1.0, "pontos": 0.0,
         "cosseno": None, "abstencao_indevida": True},
        {"escopo": "fora", "split": "dev", "categoria": "", "faithfulness": 0.0,
         "abstencao_correta": False, "alucinacao_fora_escopo": True},
        {"escopo": "fora", "split": "dev", "categoria": "", "faithfulness": 1.0,
         "abstencao_correta": True, "alucinacao_fora_escopo": False},
    ]

    geral = resumir_respostas(registros)["geral"]

    assert geral["faithfulness_media"] == pytest.approx(0.75)
    assert geral["relevancy_media"] == pytest.approx(0.5)
    assert (geral["abstencoes_indevidas"], geral["abstencoes_corretas"], geral["alucinacoes_fora_escopo"]) == (1, 1, 1)


def test_similaridade_cosseno() -> None:
    assert similaridade_cosseno([1, 0], [1, 0]) == pytest.approx(1.0)
    assert similaridade_cosseno([1, 0], [0, 1]) == 0.0
    assert similaridade_cosseno([0, 0], [1, 1]) == 0.0


# ------------------------------------------------------------- calibração


def test_calibracao_calcula_acuracia_revocacao_e_matriz() -> None:
    casos = [
        CasoCalibracao("1", "dev", "A carcaça é de ferro.", "A carcaça é de ferro.", "SUSTENTADA"),
        CasoCalibracao("2", "dev", "A carcaça é de ferro.", "O anel V-ring veda o eixo.", "EXTERNA"),
        CasoCalibracao("3", "teste", "A carcaça é de ferro.", "A carcaça é de alumínio.", "CONTRADIZ"),
        CasoCalibracao("4", "teste", "A carcaça é de ferro.", "A tampa é de ferro.", "EXTERNA"),
    ]
    respostas = {"A carcaça é de ferro.": "SUSTENTADA", "O anel V-ring veda o eixo.": "EXTERNA",
                 "A carcaça é de alumínio.": "CONTRADIZ", "A tampa é de ferro.": "SUSTENTADA"}
    juiz = Juiz(ClienteFalso(lambda _m, c: respostas[c.split("AFIRMAÇÃO\n")[-1]]))

    resultado = calibrar_juiz(juiz, casos)

    todos = resultado["metricas"]["todos"]["juiz_isolado"]
    assert todos["acuracia"] == 0.75
    assert todos["revocacao_externa"] == 0.5
    assert todos["precisao_externa"] == 1.0
    assert todos["matriz_confusao"]["EXTERNA"]["SUSTENTADA"] == 1
    assert resultado["metricas"]["dev"]["juiz_isolado"]["acuracia"] == 1.0
    assert resultado["modelo_juiz"] == MODELO_JUIZ


def test_metricas_de_rotulos_com_rotulo_invalido() -> None:
    metricas = metricas_rotulos(["EXTERNA", "SUSTENTADA"], [None, "SUSTENTADA"])

    assert metricas["acuracia"] == 0.5
    assert metricas["matriz_confusao"]["EXTERNA"]["INVALIDO"] == 1


def test_arquivo_de_calibracao_tem_casos_rotulados_a_mao_e_cobre_os_rotulos() -> None:
    casos = carregar_casos_calibracao()
    rotulos = Counter(caso.rotulo_esperado for caso in casos)
    divisao = Counter(caso.split for caso in casos)

    assert len(casos) >= 12
    assert rotulos["EXTERNA"] >= 4 and rotulos["CONTRADIZ"] >= 3 and rotulos["SUSTENTADA"] >= 3
    assert divisao["dev"] == 6 and divisao["teste"] == len(casos) - 6
    assert any("V-ring" in caso.afirmacao for caso in casos)
    assert any("classe F" in caso.afirmacao and "classe de isolamento" not in caso.contexto for caso in casos)
    assert len({caso.id for caso in casos}) == len(casos)


# ------------------------------------------------------- estados e limiar


def _alerta(grandeza: str, inicio: datetime, ident: str, severidade: str = "critico") -> Alerta:
    return Alerta(
        id=ident, ativo="WEG W22", sensor_id="s", grandeza=grandeza, unidade="u", severidade=severidade,
        inicio=inicio, fim=inicio + timedelta(minutes=5), duracao_min=5.0, n_leituras=3, valor_max=1.0,
        valor_medio=1.0, limiar_nominal=1.0, limiar_alerta=1.0, limiar_critico=1.0, desvio_abs=1.0,
        desvio_pct=1.0, ids_leitura=("a",),
    )


def test_estado_do_cenario_so_tem_a_grandeza_pedida() -> None:
    t0 = datetime(2026, 8, 1, 10, tzinfo=timezone.utc)
    alertas = [
        _alerta("Temperatura do enrolamento (estator)", t0, "A-1"),
        _alerta("Corrente elétrica por fase", t0, "A-2"),
        _alerta("Corrente elétrica por fase", t0 + timedelta(hours=2), "A-3"),
        _alerta("Vibração no mancal lado acoplado", t0 + timedelta(hours=4), "A-4"),
        _alerta("Temperatura do enrolamento (estator)", t0 + timedelta(hours=6), "A-5"),
    ]

    estados = construir_estados(alertas)

    assert set(estados) == set(ESTADOS_AVALIACAO)
    assert [a.id for a in estados["corrente_critico"].alertas_ativos] == ["A-3"]
    assert [a.id for a in estados["vibracao_critico"].alertas_ativos] == ["A-4"]
    assert [a.id for a in estados["temperatura_critico"].alertas_ativos] == ["A-5"]


def test_cenario_sem_alerta_correspondente_falha() -> None:
    alertas = [_alerta("Corrente elétrica por fase", datetime(2026, 8, 1, tzinfo=timezone.utc), "A-1")]

    with pytest.raises(ValueError):
        construir_estados(alertas)


def _buscar_falso(
    self: Retriever, pergunta: str, estado: Any = None, k_busca: Any = None, k_final: Any = None
) -> list[dict[str, Any]]:
    """Scores depend only on the section-boost weight, to exercise the grid."""
    peso = self.configuracao.preset.peso_estado
    dentro = "externa" not in pergunta
    pagina = 9 if dentro and peso >= 0.15 else 99
    melhor = -2.0 if dentro else -4.0
    return [_chunk(pagina=pagina, score_rerank_bruto=melhor)]


@pytest.fixture
def retriever_falso(monkeypatch: pytest.MonkeyPatch) -> Retriever:
    monkeypatch.setattr(Retriever, "buscar", _buscar_falso)
    return Retriever(ComponentesRetriever(None, None, None), ConfiguracaoRetriever(NOVO, {}))  # type: ignore[arg-type]


def test_retriever_com_peso_nao_altera_o_original(retriever_falso: Retriever) -> None:
    original = retriever_falso

    novo = retriever_com_peso(original, 0.3)

    assert novo.configuracao.preset.peso_estado == 0.3
    assert original.configuracao.preset.peso_estado == NOVO.peso_estado
    assert novo.componentes is original.componentes


def test_varredura_escolhe_par_que_acerta_mais_e_abstem_nas_perguntas_fora(retriever_falso: Retriever) -> None:
    perguntas = [
        _pergunta(id="d1", split="dev"),
        _pergunta("fora", id="f1", split="dev", pergunta="pergunta externa", esperado="abstencao"),
        _pergunta(id="t1", split="teste"),
    ]

    grade = varrer_parametros(retriever_falso, perguntas, {})

    assert len(grade) == len(GRADE_PESO_ESTADO) * len(GRADE_LIMIAR_ABSTENCAO)
    assert {(linha["n_dentro"], linha["n_fora"]) for linha in grade} == {(1, 1)}
    escolhido = escolher_parametros(grade)
    assert escolhido["hit4_dentro"] == 1
    assert escolhido["abstencao_fora_correta"] == 1
    assert escolhido["abstencao_dentro_indevida"] == 0
    assert escolhido["peso_estado"] >= 0.15
    assert escolhido["limiar_abstencao"] == -3.0


def test_empate_escolhe_o_limiar_mediano_da_faixa_viavel() -> None:
    def linha(limiar: float, fora: int) -> dict[str, Any]:
        return {"peso_estado": 0.15, "limiar_abstencao": limiar, "hit4_dentro": 5, "n_dentro": 5,
                "abstencao_fora_correta": fora, "n_fora": 2, "abstencao_dentro_indevida": 0}

    grade = [linha(0.0, 1), linha(0.5, 2), linha(1.0, 2), linha(2.0, 2), linha(3.0, 2), linha(4.0, 2)]

    assert escolher_parametros(grade)["limiar_abstencao"] == 2.0


def test_escolha_sem_par_viavel_maximiza_abstencao_correta() -> None:
    grade = [
        {"peso_estado": 0.0, "limiar_abstencao": -3.0, "hit4_dentro": 3, "n_dentro": 3,
         "abstencao_fora_correta": 1, "n_fora": 2, "abstencao_dentro_indevida": 0},
        {"peso_estado": 0.0, "limiar_abstencao": -2.0, "hit4_dentro": 1, "n_dentro": 3,
         "abstencao_fora_correta": 2, "n_fora": 2, "abstencao_dentro_indevida": 2},
    ]

    assert escolher_parametros(grade)["limiar_abstencao"] == -2.0
    with pytest.raises(ValueError):
        escolher_parametros([])


# ---------------------------------------------------------------- gabarito


@pytest.fixture(scope="module")
def textos_do_pdf() -> dict[int, str]:
    return textos_por_pagina(extrair_paginas())


def test_gabarito_tem_20_dentro_5_fora_split_5_15_e_categorias_cobertas() -> None:
    perguntas = carregar_gabarito()
    dentro = [p for p in perguntas if p.escopo == "dentro"]
    fora = [p for p in perguntas if p.escopo == "fora"]

    assert (len(dentro), len(fora)) == (20, 5)
    assert Counter(p.split for p in dentro) == {"dev": 5, "teste": 15}
    categorias = Counter(p.categoria for p in dentro)
    assert set(categorias) == set(CATEGORIAS_AVALIACAO)
    assert all(categorias[categoria] >= 4 for categoria in ("elétrica", "mecânica", "preventiva"))
    assert len({p.id for p in perguntas}) == 25
    assert all(p.esperado == "abstencao" for p in fora)


def test_gabarito_usa_estados_conhecidos_em_pelo_menos_oito_perguntas() -> None:
    perguntas = carregar_gabarito()
    com_estado = [p for p in perguntas if p.estado]

    assert sum(1 for p in com_estado if p.escopo == "dentro") >= 8
    assert {p.estado for p in com_estado} <= set(ESTADOS_AVALIACAO)


def test_gabarito_nao_cita_outros_fabricantes() -> None:
    texto = " ".join(p.pergunta + p.resposta_referencia for p in carregar_gabarito()).casefold()

    assert "siemens" not in texto and "abb" not in texto.split()


def test_toda_ancora_ocorre_numa_pagina_do_gabarito_no_pdf_real(textos_do_pdf: dict[int, str]) -> None:
    dentro = [p for p in carregar_gabarito() if p.escopo == "dentro"]
    ausentes = [p.id for p in dentro if not ancora_presente(p, textos_do_pdf)]

    assert ausentes == []
    assert all(pagina in textos_do_pdf for p in dentro for pagina in p.paginas_gabarito)


def test_termo_de_cada_pergunta_fora_do_escopo_nao_ocorre_no_pdf(textos_do_pdf: dict[int, str]) -> None:
    fora = [p for p in carregar_gabarito() if p.escopo == "fora"]

    assert all(termo_ausente_no_pdf(p, textos_do_pdf) for p in fora)


def test_ancora_inventada_e_detectada(textos_do_pdf: dict[int, str]) -> None:
    inventada = _pergunta(trecho_ancora="o motor W22 pesa exatamente 80 kg", paginas_gabarito=(9,))

    assert not ancora_presente(inventada, textos_do_pdf)
