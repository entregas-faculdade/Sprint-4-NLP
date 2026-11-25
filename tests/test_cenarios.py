from __future__ import annotations

import copy
import json
import re
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import pytest

from src.pln.alertas import Alerta, carregar_leituras, detectar_episodios
from src.pln.assistente import Assistente
from src.pln.avaliacao import Juiz, normalizar_trecho, textos_por_pagina
from src.pln.cenarios import (
    AmbienteCenarios,
    Cenario,
    ConjuntoCenarios,
    ExecucaoLimites,
    carregar_cenarios,
    coletar_fatos_dados,
    consolidar_cenarios,
    descrever_episodio,
    escolher_episodio,
    executar_cenario,
    executar_cenarios,
    formatar_cenario,
    linhas_turnos,
    montar_limites,
    validar_limites,
)
from src.pln.config import CATEGORIAS_LIMITE, FRASE_ABSTENCAO, MODELO_GERADOR
from src.pln.estado import EstadoOperacional, construir_estado_operacional
from src.pln.llm import OpenRouterRequestError
from src.pln.rag import extrair_paginas

INICIO = datetime(2026, 8, 1, tzinfo=timezone.utc)
VALOR_PADRAO = 100.0
PAGINA_FORA = 32
SCORE_DENTRO = 9.0
SCORE_FORA = -3.0
ROTULO_CHUNK = re.compile(r"\[p\. \d+, seç\. [^\]]+\]")


# ---------------------------------------------------------------- fixtures


@pytest.fixture(scope="module")
def leituras() -> list[dict[str, Any]]:
    return carregar_leituras()


@pytest.fixture(scope="module")
def alertas(leituras: list[dict[str, Any]]) -> list[Alerta]:
    return detectar_episodios(leituras)


@pytest.fixture(scope="module")
def conjunto() -> ConjuntoCenarios:
    return carregar_cenarios()


@pytest.fixture(scope="module")
def textos_do_pdf() -> dict[int, str]:
    return textos_por_pagina(extrair_paginas())


def _alerta(id_: str, grandeza: str, severidade: str, inicio: datetime) -> Alerta:
    return Alerta(
        id=id_, ativo="W22", sensor_id="s1", grandeza=grandeza, unidade="u", severidade=severidade,
        inicio=inicio, fim=inicio + timedelta(minutes=30), duracao_min=30.0, n_leituras=3, valor_max=VALOR_PADRAO,
        valor_medio=VALOR_PADRAO, limiar_nominal=1.0, limiar_alerta=2.0, limiar_critico=3.0, desvio_abs=1.0,
        desvio_pct=1.0, ids_leitura=(f"L-{id_}-1", f"L-{id_}-2"),
    )


def _horas(quantidade: int) -> datetime:
    return INICIO + timedelta(hours=quantidade)


def _leituras_horarias(total: int) -> list[dict[str, Any]]:
    return [{"id": f"R-{hora}", "asset_id": "a1", "timestamp": _horas(hora)} for hora in range(total)]


REGRA_CORRENTE = {"tipo": "maior_severidade", "grandezas": ["corrente"], "severidade": "critico"}
REGRA_MECANICA = {"tipo": "maior_severidade", "grandezas": ["vibra", "velocidade"], "severidade": "critico"}
REGRA_CALMA = {"tipo": "janela_calma", "horas": 24, "severidades_bloqueadas": ["moderado", "critico"]}
REGRA_MENOR = {"tipo": "menor_valor", "grandezas": ["velocidade"], "severidade": "critico"}


# --------------------------------------------------- regras de escolha (sintético)


def test_maior_severidade_escolhe_o_alerta_critico_mais_recente_da_grandeza() -> None:
    alertas = [
        _alerta("A-1", "Corrente elétrica por fase", "critico", _horas(1)),
        _alerta("A-2", "Corrente elétrica por fase", "critico", _horas(5)),
        _alerta("A-3", "Corrente elétrica por fase", "moderado", _horas(9)),
        _alerta("A-4", "Vibração no mancal", "critico", _horas(10)),
    ]

    episodio = escolher_episodio(REGRA_CORRENTE, alertas, [])

    assert (episodio.alerta_id, episodio.candidatos) == ("A-2", 2)
    assert episodio.leitura_id == "L-A-2-1"
    assert episodio.instante == _horas(5)


def test_mecanica_cai_para_velocidade_quando_vibracao_nao_tem_critico() -> None:
    alertas = [
        _alerta("A-1", "Vibração no mancal lado acoplado", "moderado", _horas(1)),
        _alerta("A-2", "Velocidade do eixo", "critico", _horas(2)),
    ]

    assert escolher_episodio(REGRA_MECANICA, alertas, []).alerta_id == "A-2"

    alertas.append(_alerta("A-3", "Vibração no mancal lado acoplado", "critico", _horas(1)))

    assert escolher_episodio(REGRA_MECANICA, alertas, []).alerta_id == "A-3"


def test_regra_sem_candidato_e_regra_desconhecida_falham() -> None:
    with pytest.raises(ValueError, match="Nenhum alerta"):
        escolher_episodio(REGRA_CORRENTE, [_alerta("A-1", "Temperatura", "critico", _horas(1))], [])
    with pytest.raises(ValueError, match="desconhecida"):
        escolher_episodio({"tipo": "aleatoria"}, [], [])


def test_janela_calma_pula_instantes_a_menos_de_24h_de_alerta_moderado_ou_critico() -> None:
    leituras = _leituras_horarias(72)
    alertas = [
        _alerta("A-1", "Corrente elétrica por fase", "moderado", _horas(10)),
        _alerta("A-2", "Corrente elétrica por fase", "critico", _horas(60)),
        _alerta("A-3", "Corrente elétrica por fase", "leve", _horas(57)),
    ]

    episodio = escolher_episodio(REGRA_CALMA, alertas, leituras)

    assert episodio.alerta_id is None
    assert episodio.leitura_id == "R-59"
    assert episodio.instante == _horas(59)


def test_janela_calma_aceita_a_leitura_mais_recente_quando_nada_a_bloqueia() -> None:
    leituras = _leituras_horarias(72)
    alertas = [_alerta("A-1", "Corrente elétrica por fase", "moderado", _horas(10))]

    episodio = escolher_episodio(REGRA_CALMA, alertas, leituras)

    # Horas 0-9 vêm antes do alerta; 35-71 já estão a mais de 24 h do fim dele (10h30).
    assert (episodio.leitura_id, episodio.candidatos) == ("R-71", 10 + 37)


def test_janela_calma_sem_instante_calmo_falha() -> None:
    alertas = [_alerta("A-1", "Corrente elétrica por fase", "critico", _horas(0))]

    with pytest.raises(ValueError, match="Nenhum instante"):
        escolher_episodio(REGRA_CALMA, alertas, _leituras_horarias(10))


def test_menor_valor_desempata_pelo_mais_recente() -> None:
    alertas = [
        replace(_alerta("A-1", "Velocidade do eixo", "critico", _horas(1)), valor_max=1851.0),
        replace(_alerta("A-2", "Velocidade do eixo", "critico", _horas(2)), valor_max=1850.4),
        replace(_alerta("A-3", "Velocidade do eixo", "critico", _horas(3)), valor_max=1850.4),
    ]

    episodio = escolher_episodio(REGRA_MENOR, alertas, [])

    assert (episodio.alerta_id, episodio.valor_max) == ("A-3", 1850.4)


def test_menor_valor_isolado_ignora_alerta_com_outro_alerta_ativo() -> None:
    alertas = [
        replace(_alerta("A-1", "Velocidade do eixo", "critico", _horas(1)), valor_max=1850.1),
        _alerta("A-2", "Temperatura do enrolamento", "critico", _horas(1)),
        replace(_alerta("A-3", "Velocidade do eixo", "critico", _horas(9)), valor_max=1851.0),
    ]

    sem_isolamento = escolher_episodio(REGRA_MENOR, alertas, [])
    isolado = escolher_episodio({**REGRA_MENOR, "isolado": True}, alertas, [])

    assert (sem_isolamento.alerta_id, isolado.alerta_id, isolado.candidatos) == ("A-1", "A-3", 1)


# ------------------------------------------------- escolha nos dados reais


ExecucaoFalsa = tuple["Montagem", list[dict[str, Any]], dict[str, Any]]


def _todos(conjunto: ConjuntoCenarios) -> list[Cenario]:
    return [*conjunto.cenarios, conjunto.adversarial]


def test_episodio_registrado_e_o_que_a_regra_devolve_nos_dados_reais(conjunto: ConjuntoCenarios, alertas: list[Alerta], leituras: list[dict[str, Any]]) -> None:
    for cenario in _todos(conjunto):
        episodio = escolher_episodio(cenario.regra, alertas, leituras)

        assert descrever_episodio(episodio) == dict(cenario.episodio), cenario.id


def test_ids_de_alerta_e_de_leitura_registrados_existem_nos_dados(conjunto: ConjuntoCenarios, alertas: list[Alerta], leituras: list[dict[str, Any]]) -> None:
    por_id = {alerta.id: alerta for alerta in alertas}
    ids_leitura = {str(leitura["id"]) for leitura in leituras}

    for cenario in _todos(conjunto):
        registrado = cenario.episodio
        assert registrado["leitura_id"] in ids_leitura, cenario.id
        if registrado["alerta_id"]:
            assert registrado["leitura_id"] in por_id[registrado["alerta_id"]].ids_leitura


def _estado_do_cenario(cenario: Cenario, alertas: list[Alerta]) -> EstadoOperacional:
    return construir_estado_operacional(alertas, datetime.fromisoformat(cenario.episodio["instante"]))


def test_os_tres_estados_tem_dominios_distintos(conjunto: ConjuntoCenarios, alertas: list[Alerta]) -> None:
    eletrica, mecanica, preventiva = (_estado_do_cenario(c, alertas) for c in conjunto.cenarios)

    assert [a.dominio_falha for a in eletrica.alertas_ativos] == ["elétrica"]
    assert [a.dominio_falha for a in mecanica.alertas_ativos] == ["mecânica"]
    assert conjunto.cenarios[0].episodio["alerta_id"] in {a.id for a in eletrica.alertas_ativos}
    assert conjunto.cenarios[1].episodio["alerta_id"] in {a.id for a in mecanica.alertas_ativos}
    assert preventiva.operacao_normal or preventiva.severidade_geral == "leve"


def test_cenario_preventivo_nao_tem_alerta_moderado_ou_critico_nas_24h(conjunto: ConjuntoCenarios, alertas: list[Alerta]) -> None:
    instante = datetime.fromisoformat(conjunto.cenarios[2].episodio["instante"])

    bloqueantes = [
        alerta.id for alerta in alertas
        if alerta.severidade in ("moderado", "critico") and alerta.inicio <= instante and alerta.fim >= instante - timedelta(hours=24)
    ]

    assert bloqueantes == []
    assert conjunto.cenarios[2].episodio["alerta_id"] is None


def test_estado_adversarial_e_so_o_critico_de_velocidade_com_o_menor_valor(conjunto: ConjuntoCenarios, alertas: list[Alerta]) -> None:
    estado = _estado_do_cenario(conjunto.adversarial, alertas)
    isolados = [
        a.valor_max for a in alertas
        if a.severidade == "critico" and "Velocidade" in a.grandeza
        and len(construir_estado_operacional(alertas, a.inicio).alertas_ativos) == 1
    ]

    assert [a.id for a in estado.alertas_ativos] == [conjunto.adversarial.episodio["alerta_id"]]
    assert estado.severidade_geral == "critico"
    assert conjunto.adversarial.episodio["valor_max"] == min(isolados)


# ----------------------------------------------------------------- carga


def test_cenarios_reais_tem_tres_turnos_na_ordem_e_fonte_esperada(conjunto: ConjuntoCenarios) -> None:
    assert [c.id for c in conjunto.cenarios] == ["eletrica", "mecanica", "preventiva"]
    for cenario in conjunto.cenarios:
        assert [t.tipo for t in cenario.turnos] == ["natural", "seguimento", "fora_escopo"]
        assert cenario.turnos[0].fonte_esperada and cenario.turnos[1].fonte_esperada
        assert cenario.turnos[2].termo_ausente
    assert [t.tipo for t in conjunto.adversarial.turnos] == ["contradicao_estado", "conhecimento_externo"]


def _documento_com(alteracao: Callable[[dict[str, Any]], Any]) -> dict[str, Any]:
    arquivo = Path(__file__).resolve().parents[1] / "data" / "cenarios.json"
    documento = json.loads(arquivo.read_text(encoding="utf-8"))
    alteracao(documento)
    return documento


def _gravar(tmp_path: Path, documento: dict[str, Any]) -> Path:
    arquivo = tmp_path / "cenarios.json"
    arquivo.write_text(json.dumps(documento, ensure_ascii=False), encoding="utf-8")
    return arquivo


def test_carga_recusa_turnos_fora_de_ordem(tmp_path: Path) -> None:
    documento = _documento_com(lambda d: d["cenarios"][0]["turnos"].reverse())

    with pytest.raises(ValueError, match="precisa ter os turnos"):
        carregar_cenarios(_gravar(tmp_path, documento))


def test_carga_recusa_turno_dentro_do_escopo_sem_fonte_esperada(tmp_path: Path) -> None:
    documento = _documento_com(lambda d: d["cenarios"][1]["turnos"][0].pop("fonte_esperada"))

    with pytest.raises(ValueError, match="fonte_esperada"):
        carregar_cenarios(_gravar(tmp_path, documento))


def test_carga_recusa_categoria_de_limite_desconhecida(tmp_path: Path) -> None:
    documento = _documento_com(lambda d: d["limites"][0].update(categoria="outra"))

    with pytest.raises(ValueError, match="Categoria de limite"):
        carregar_cenarios(_gravar(tmp_path, documento))


def test_carga_recusa_arquivo_inexistente(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="Não foi possível carregar"):
        carregar_cenarios(tmp_path / "nao-existe.json")


# ------------------------------------------------------------ PDF real


def test_fonte_esperada_ocorre_na_pagina_indicada_do_pdf_real(conjunto: ConjuntoCenarios, textos_do_pdf: dict[int, str]) -> None:
    for cenario in conjunto.cenarios:
        for turno in cenario.turnos[:2]:
            fonte = turno.fonte_esperada
            ancora = normalizar_trecho(fonte["trecho_ancora"])

            assert ancora in textos_do_pdf[int(fonte["pagina"])], turno.id


def test_termo_ausente_dos_turnos_sem_resposta_nao_ocorre_em_nenhuma_pagina(conjunto: ConjuntoCenarios, textos_do_pdf: dict[int, str]) -> None:
    turnos = [t for c in _todos(conjunto) for t in c.turnos if t.termo_ausente]

    assert len(turnos) == 5
    for turno in turnos:
        termo = normalizar_trecho(turno.termo_ausente)
        assert not any(termo in texto for texto in textos_do_pdf.values()), turno.id


# -------------------------------------------------------- execução (falsa)


class RetrieverFalso:
    """Returns one chunk per question: on the expected page when answerable, a weak one otherwise."""

    def __init__(self, conjunto: ConjuntoCenarios) -> None:
        self.consultas: list[str] = []
        self._respostas: dict[str, tuple[int, str, float]] = {}
        for cenario in _todos(conjunto):
            for turno in cenario.turnos:
                fonte = turno.fonte_esperada
                self._respostas[turno.pergunta] = (
                    (int(fonte["pagina"]), str(fonte["secao"]), SCORE_DENTRO) if fonte else (PAGINA_FORA, "15", SCORE_FORA)
                )

    def buscar(self, pergunta: str, estado: Any = None) -> list[dict[str, Any]]:
        self.consultas.append(pergunta)
        original = next(p for p in self._respostas if pergunta.endswith(p))
        pagina, secao, score = self._respostas[original]
        return [{
            "id": f"c-{pagina}-{secao}", "pagina": pagina, "pagina_fim": pagina, "secao": secao,
            "secao_titulo": "Título", "texto": f"Trecho da página {pagina}.", "score_rerank_bruto": score,
        }]


class GeradorFalso:
    """Cites the first context label, like a faithful model would."""

    def __init__(self, falhar_em: int | None = None) -> None:
        self.chamadas = 0
        self._falhar_em = falhar_em

    def complete(self, model_id: str, messages: list[dict[str, str]]) -> str:
        self.chamadas += 1
        if self.chamadas == self._falhar_em:
            raise OpenRouterRequestError("sem resposta")
        rotulo = ROTULO_CHUNK.search(messages[-1]["content"]).group(0)
        return f"O catálogo trata disso {rotulo}.\nConfiança: Alta"


class JuizFalso:
    def complete(self, model_id: str, messages: list[dict[str, str]]) -> str:
        return "COBRE" if messages[-1]["content"].startswith("PERGUNTA") else "SUSTENTADA"


class EmbeddingFalso:
    def encode(self, sentences: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in sentences]


class Montagem:
    """Wires the fake retriever and generator into a scenario environment."""

    def __init__(self, conjunto: ConjuntoCenarios, alertas: list[Alerta], gerador: GeradorFalso | None = None) -> None:
        self.retriever = RetrieverFalso(conjunto)
        self.gerador = gerador or GeradorFalso()
        self.assistentes: list[Assistente] = []
        self.ambiente = AmbienteCenarios(alertas, self._fabrica, Juiz(JuizFalso()), EmbeddingFalso())

    def _fabrica(self) -> Assistente:
        assistente = Assistente(self.retriever, self.gerador)
        self.assistentes.append(assistente)
        return assistente


@pytest.fixture(scope="module")
def execucao_falsa(conjunto: ConjuntoCenarios, alertas: list[Alerta]) -> ExecucaoFalsa:
    montagem = Montagem(conjunto, alertas)
    resultados = executar_cenarios(conjunto.cenarios, montagem.ambiente)
    adversarial = executar_cenario(conjunto.adversarial, montagem.ambiente)
    return montagem, resultados, adversarial


def test_segundo_turno_usa_a_memoria_e_primeiro_e_terceiro_nao(conjunto: ConjuntoCenarios, execucao_falsa: ExecucaoFalsa) -> None:
    _, resultados, _ = execucao_falsa

    for cenario, resultado in zip(conjunto.cenarios, resultados, strict=True):
        perguntas = [turno.pergunta for turno in cenario.turnos]
        consultas = [turno["consulta"] for turno in resultado["turnos"]]
        assert consultas == [perguntas[0], f"{perguntas[0]} {perguntas[1]}", perguntas[2]], cenario.id


def test_cada_cenario_ganha_um_assistente_novo_sem_memoria(conjunto: ConjuntoCenarios, execucao_falsa: ExecucaoFalsa) -> None:
    montagem, resultados, _ = execucao_falsa

    assert len(montagem.assistentes) == len(conjunto.cenarios) + 1
    primeiros = [resultado["turnos"][0] for resultado in resultados]
    for cenario, turno in zip(conjunto.cenarios, primeiros, strict=True):
        assert turno["consulta"] == cenario.turnos[0].pergunta


def test_registro_do_turno_traz_fonte_confianca_modelo_e_hit(execucao_falsa: ExecucaoFalsa, conjunto: ConjuntoCenarios) -> None:
    _, resultados, _ = execucao_falsa
    turno = resultados[0]["turnos"][0]
    fonte = conjunto.cenarios[0].turnos[0].fonte_esperada

    assert turno["modelo"] == MODELO_GERADOR
    assert turno["confianca"] == "Média"
    assert turno["fontes"][0]["pagina"] == fonte["pagina"]
    assert turno["fonte"]["hit_pagina"] is True and turno["fonte"]["hit_secao"] is True
    assert turno["fonte"]["citada"] is True
    assert turno["faithfulness"] == 1.0 and turno["cobertura"] == "COBRE"
    assert turno["id"] == "eletrica-t1" and turno["cenario"] == "eletrica" and turno["turno"] == 1


def test_terceiro_turno_abstem_sem_chamar_o_gerador(conjunto: ConjuntoCenarios, alertas: list[Alerta]) -> None:
    montagem = Montagem(conjunto, alertas)

    resultado = executar_cenario(conjunto.cenarios[0], montagem.ambiente)
    terceiro = resultado["turnos"][2]

    assert montagem.gerador.chamadas == 2
    assert terceiro["abstencao"] is True and terceiro["abstencao_correta"] is True
    assert terceiro["resposta"].startswith(FRASE_ABSTENCAO)
    assert terceiro["fontes"] == [] and terceiro["confianca"] == "Baixa"


def test_estado_do_cenario_vem_do_alerta_real(execucao_falsa: ExecucaoFalsa, conjunto: ConjuntoCenarios) -> None:
    _, resultados, _ = execucao_falsa

    assert conjunto.cenarios[0].episodio["alerta_id"] in resultados[0]["estado"]["texto"]
    assert resultados[0]["estado"]["dominios"] == ["elétrica"]
    assert resultados[1]["estado"]["dominios"] == ["mecânica"]
    assert resultados[2]["estado"]["operacao_normal"] is True


def test_resumo_do_cenario_conta_fontes_e_abstencoes(execucao_falsa: ExecucaoFalsa) -> None:
    _, resultados, _ = execucao_falsa

    resumo = resultados[0]["resumo"]
    assert resumo["fontes_esperadas"] == 2 and resumo["fontes_esperadas_recuperadas"] == 2
    assert resumo["abstencoes_corretas"] == 1 and resumo["respostas_sem_abster_fora_escopo"] == 0
    assert resumo["abstencoes_indevidas"] == 0 and resumo["erros"] == 0
    assert resumo["confiancas"] == ["Média", "Média", "Baixa"]


def test_falha_de_api_vira_erro_do_turno_sem_trocar_de_modelo(conjunto: ConjuntoCenarios, alertas: list[Alerta]) -> None:
    montagem = Montagem(conjunto, alertas, GeradorFalso(falhar_em=1))

    resultado = executar_cenario(conjunto.cenarios[0], montagem.ambiente)

    primeiro, segundo = resultado["turnos"][:2]
    assert primeiro["erro"] is True and primeiro["modelo"] == MODELO_GERADOR
    assert "erro" not in segundo
    assert resultado["resumo"]["erros"] == 1


def test_modelos_misturados_reprovam_a_consolidacao(execucao_falsa: ExecucaoFalsa) -> None:
    _, resultados, adversarial = execucao_falsa
    adulterado = copy.deepcopy(adversarial)
    adulterado["turnos"][0]["modelo"] = "outro/modelo"

    with pytest.raises(RuntimeError, match="Modelos misturados"):
        consolidar_cenarios(resultados, adulterado)


def test_consolidacao_resume_cada_cenario_e_registra_os_dois_modelos(execucao_falsa: ExecucaoFalsa) -> None:
    _, resultados, adversarial = execucao_falsa

    documento = consolidar_cenarios(resultados, adversarial)

    assert set(documento["resumo"]) == {"eletrica", "mecanica", "preventiva", "adversarial"}
    assert documento["modelo_gerador"] == MODELO_GERADOR and documento["modelo_juiz"]
    json.dumps(documento, ensure_ascii=False)


def test_exibicao_mostra_estado_fontes_confianca_e_modelo(execucao_falsa: ExecucaoFalsa) -> None:
    _, resultados, _ = execucao_falsa

    texto = formatar_cenario(resultados[0])

    assert "Cenário 1 — anomalia elétrica" in texto
    assert resultados[0]["episodio"]["alerta_id"] in texto
    assert "consulta usada:" in texto and "[p. 19, seç. 9]" in texto
    assert "confiança: Média" in texto and f"modelo: {MODELO_GERADOR}" in texto
    assert "fonte esperada:" in texto


def test_linhas_da_tabela_mostram_consulta_fonte_esperada_e_abstencao(execucao_falsa: ExecucaoFalsa) -> None:
    _, resultados, _ = execucao_falsa

    linhas = linhas_turnos(resultados[0])

    assert [linha["turno"] for linha in linhas] == [1, 2, 3]
    assert linhas[1]["consulta usada"].startswith(linhas[0]["consulta usada"])
    assert linhas[0]["fontes"] == "p. 19, seç. 9" and linhas[0]["fonte esperada recuperada"] is True
    assert linhas[2]["abstenção"] is True and linhas[2]["fonte esperada recuperada"] is None


def test_linha_de_turno_com_erro_traz_a_mensagem(conjunto: ConjuntoCenarios, alertas: list[Alerta]) -> None:
    montagem = Montagem(conjunto, alertas, GeradorFalso(falhar_em=1))

    linhas = linhas_turnos(executar_cenario(conjunto.cenarios[0], montagem.ambiente))

    assert linhas[0]["erro"] == "sem resposta" and "confiança" not in linhas[0]


# ------------------------------------------------------------------ limites


def _registro_resposta(id_: str, escopo: str, abstencao: bool, **extra: Any) -> dict[str, Any]:
    base = {
        "id": id_, "escopo": escopo, "split": "teste", "abstencao": abstencao, "confianca": "Baixa" if abstencao else "Média",
        "chunks": [{"pagina": 8, "secao": "1", "score_rerank_bruto": 0.41}], "afirmacoes": [], "faithfulness": 1.0,
    }
    return {**base, **extra}


FRASE_EXTERNA = "O fator de serviço do W22 Super Premium é 1,15."


def _respostas_de_avaliacao() -> list[dict[str, Any]]:
    externa = {"afirmacao": FRASE_EXTERNA, "rotulo_juiz": "SUSTENTADA", "rotulo": "EXTERNA", "guarda": "guarda_numero"}
    sustentada = {"afirmacao": "A carcaça é de ferro fundido.", "rotulo_juiz": "SUSTENTADA", "rotulo": "SUSTENTADA", "guarda": None}
    return [
        _registro_resposta("s02", "dentro", False, afirmacoes=[sustentada, externa], faithfulness=0.5),
        _registro_resposta("p01", "dentro", True, abstencao_indevida=True, chunks=[{"pagina": 16, "secao": "5.2.1", "score_rerank_bruto": -3.91}]),
        _registro_resposta("f01", "fora", True, split="dev"),
        _registro_resposta("f02", "fora", False, split="dev"),
    ]


CALIBRACAO = {
    "metricas": {"todos": {"juiz_com_guardas": {"n": 16, "acuracia": 0.9375, "revocacao_externa": 1.0, "precisao_externa": 0.8333}}},
    "casos": [
        {"id": "c03", "afirmacao": "O Pt-100 é um termistor.", "esperado": "CONTRADIZ", "juiz": "EXTERNA", "final": "EXTERNA"},
        {"id": "c04", "afirmacao": "A carcaça é de ferro.", "esperado": "SUSTENTADA", "juiz": "SUSTENTADA", "final": "SUSTENTADA"},
    ],
}


@pytest.fixture(scope="module")
def execucao_limites(conjunto: ConjuntoCenarios, execucao_falsa: ExecucaoFalsa, leituras: list[dict[str, Any]]) -> ExecucaoLimites:
    _, resultados, adversarial = execucao_falsa
    return ExecucaoLimites(_respostas_de_avaliacao(), resultados, adversarial, CALIBRACAO, coletar_fatos_dados(leituras))


def test_limites_cobrem_as_cinco_categorias_com_mitigacao_e_risco(conjunto: ConjuntoCenarios, execucao_limites: ExecucaoLimites) -> None:
    limites = montar_limites(conjunto.modelos_limite, execucao_limites)

    assert {linha["categoria"] for linha in limites["linhas"]} == set(CATEGORIAS_LIMITE)
    for linha in limites["linhas"]:
        assert linha["evidencias"], linha["id"]
        assert linha["mitigacao"] and linha["risco_residual"]
        for campo in ("limite", "mitigacao", "risco_residual"):
            assert "{" not in linha[campo], (linha["id"], campo)


def test_limite_de_alucinacao_cita_a_frase_externa_da_execucao(conjunto: ConjuntoCenarios, execucao_limites: ExecucaoLimites) -> None:
    limites = montar_limites(conjunto.modelos_limite, execucao_limites)
    linha = next(item for item in limites["linhas"] if item["id"] == "alucinacao_afirmacoes")

    assert re.search(r"1 de \d+ afirmações rotuladas EXTERNA ou CONTRADIZ \(1 EXTERNA, 0 CONTRADIZ; ids: s02\)", linha["limite"])
    assert any(e["afirmacao"] == FRASE_EXTERNA and e["id"] == "s02" for e in linha["evidencias"])


def test_limite_de_fora_do_escopo_separa_quem_abstem_de_quem_responde(conjunto: ConjuntoCenarios, execucao_limites: ExecucaoLimites) -> None:
    linha = next(i for i in montar_limites(conjunto.modelos_limite, execucao_limites)["linhas"] if i["id"] == "fora_escopo_abstencao")

    assert "f02" in linha["limite"]
    ids = {e["id"]: e["detalhe"] for e in linha["evidencias"]}
    assert ids["f02"].startswith("respondeu sem abster") and ids["f01"].startswith("abstenção")
    assert "eletrica-t3" in ids


def test_limite_do_limiar_cita_a_abstencao_indevida_com_o_escore(conjunto: ConjuntoCenarios, execucao_limites: ExecucaoLimites) -> None:
    linha = next(i for i in montar_limites(conjunto.modelos_limite, execucao_limites)["linhas"] if i["id"] == "metodo_limiar_abstencao")

    assert any(e["id"] == "p01" and "-3,91" in e["detalhe"] for e in linha["evidencias"])


def test_limites_de_dados_usam_numeros_reais_do_csv_e_dos_sensores(conjunto: ConjuntoCenarios, execucao_limites: ExecucaoLimites, leituras: list[dict[str, Any]]) -> None:
    linhas = {i["id"]: i for i in montar_limites(conjunto.modelos_limite, execucao_limites)["linhas"]}

    assert "Só 4 das 6 variáveis" in linhas["dados_limiares"]["limite"]
    assert f"{len(leituras)} leituras" in linhas["dados_baseline"]["limite"]
    assert "1 ativo" in linhas["dados_baseline"]["limite"]
    assert "34 leituras" in linhas["dados_baseline"]["limite"]
    assert "6 de 6 variáveis" in linhas["dados_nomes"]["limite"]


def test_limite_sem_ocorrencia_cita_a_contagem_zero_em_vez_de_ficar_generico(conjunto: ConjuntoCenarios, execucao_limites: ExecucaoLimites) -> None:
    limpas = [r for r in _respostas_de_avaliacao() if r["id"] != "s02"]
    execucao = ExecucaoLimites(limpas, execucao_limites.cenarios, execucao_limites.adversarial, CALIBRACAO, execucao_limites.fatos)

    linha = next(i for i in montar_limites(conjunto.modelos_limite, execucao)["linhas"] if i["id"] == "alucinacao_afirmacoes")

    assert linha["evidencias"][0]["id"] is None and "0 de" in linha["evidencias"][0]["detalhe"]
    assert re.search(r"0 de \d+ afirmações rotuladas EXTERNA ou CONTRADIZ", linha["limite"])


def _linha_com(evidencia: dict[str, Any]) -> dict[str, Any]:
    return {"id": "teste", "evidencias": [evidencia]}


def _ev(origem: str = "avaliacao_respostas", id_: str | None = "s02", afirmacao: str | None = FRASE_EXTERNA) -> dict[str, Any]:
    return {"origem": origem, "id": id_, "detalhe": "x", "afirmacao": afirmacao}


def test_validacao_aceita_id_e_afirmacao_que_existem_na_execucao(execucao_limites: ExecucaoLimites) -> None:
    validar_limites([_linha_com(_ev())], execucao_limites)
    validar_limites([_linha_com(_ev("juiz_calibracao", "c03", "O Pt-100 é um termistor."))], execucao_limites)
    validar_limites([_linha_com(_ev("cenarios", "mecanica-t2", None))], execucao_limites)


@pytest.mark.parametrize(
    "evidencia, trecho",
    [
        (_ev(id_="s99"), "não existe na execução"),
        (_ev(afirmacao="Frase que o assistente nunca escreveu."), "afirmação citada"),
        (_ev(origem="manual"), "origem de evidência"),
        (_ev(id_=None), "sem id de origem"),
        (_ev("cenarios", "eletrica-t9", None), "não existe na execução"),
    ],
)
def test_validacao_recusa_citacao_que_a_execucao_nao_produziu(execucao_limites: ExecucaoLimites, evidencia: dict[str, Any], trecho: str) -> None:
    with pytest.raises(ValueError, match=trecho):
        validar_limites([_linha_com(evidencia)], execucao_limites)


def test_validacao_recusa_linha_generica_sem_evidencia(execucao_limites: ExecucaoLimites) -> None:
    with pytest.raises(ValueError, match="não cita caso nem número"):
        validar_limites([{"id": "vaga", "evidencias": []}], execucao_limites)


def test_montagem_recusa_modelo_de_limite_sem_construtor_e_categoria_faltante(conjunto: ConjuntoCenarios, execucao_limites: ExecucaoLimites) -> None:
    com_extra = [*conjunto.modelos_limite, {**conjunto.modelos_limite[0], "id": "inventado"}]
    sem_dados = [{**m, "categoria": "metodo"} if m["categoria"] == "dados" else m for m in conjunto.modelos_limite]

    with pytest.raises(ValueError, match="divergem dos construtores"):
        montar_limites(com_extra, execucao_limites)
    with pytest.raises(ValueError, match="Categorias de limite sem linha"):
        montar_limites(sem_dados, execucao_limites)


def test_fatos_dos_dados_batem_com_o_csv_e_os_sensores(leituras: list[dict[str, Any]]) -> None:
    fatos = coletar_fatos_dados(leituras)

    assert (fatos["n_sensores"], fatos["n_com_limiar"]) == (6, 4)
    assert fatos["n_leituras"] == len(leituras) and fatos["n_ativos"] == 1
    assert fatos["n_unidade_divergente"] >= 1 and fatos["exemplo_nome"] and fatos["exemplo_canonico"]
