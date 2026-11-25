"""Pick real alert episodes for the demo scenarios, run the dialogue and document the observed limits."""

from __future__ import annotations

import json
import unicodedata
from bisect import bisect_right
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import accumulate
from pathlib import Path
from typing import Any

from src.pln.alertas import Alerta
from src.pln.assistente import Assistente, Resposta
from src.pln.avaliacao import (
    ContextoRespostas,
    Juiz,
    PerguntaAvaliacao,
    avaliar_resposta,
    chunk_relevante_estrito,
    chunk_relevante_pagina,
    verificar_modelo_unico,
)
from src.pln.config import (
    CATEGORIAS_LIMITE,
    CENARIOS_FILE,
    DATA_VARIABLES_FILE,
    ESCOPO_DENTRO,
    ESCOPO_FORA,
    ESPERADO_ABSTENCAO,
    IDS_CENARIOS,
    LIMIAR_ABSTENCAO,
    MODELO_GERADOR,
    MODELO_JUIZ,
    ORIGEM_CALIBRACAO,
    ORIGEM_CENARIOS,
    ORIGEM_DADOS,
    ORIGEM_RESPOSTAS,
    ORIGENS_EVIDENCIA,
    REGRA_JANELA_CALMA,
    REGRA_MAIOR_SEVERIDADE,
    REGRA_MENOR_VALOR,
    ROTULO_CONTRADIZ,
    ROTULO_EXTERNA,
    SPLIT_CENARIO,
    TURNO_FORA_ESCOPO,
    TURNO_NATURAL,
    TURNO_SEGUIMENTO,
    TURNOS_ADVERSARIAIS,
    TURNOS_POR_CENARIO,
)
from src.pln.estado import EstadoOperacional, construir_estado_operacional
from src.pln.llm import OpenRouterRequestError
from src.pln.rag import EmbeddingModel
from src.pln.sensores import carregar_sensores

TIPOS_DENTRO_ESCOPO = (TURNO_NATURAL, TURNO_SEGUIMENTO)
ROTULOS_ALUCINACAO = (ROTULO_EXTERNA, ROTULO_CONTRADIZ)


@dataclass(frozen=True)
class Turno:
    """One question of a scenario dialogue, with the page that must support the answer."""

    id: str
    indice: int
    tipo: str
    pergunta: str
    fonte_esperada: Mapping[str, Any] | None
    resposta_referencia: str
    termo_ausente: str

    @property
    def escopo(self) -> str:
        return ESCOPO_DENTRO if self.tipo in TIPOS_DENTRO_ESCOPO else ESCOPO_FORA


@dataclass(frozen=True)
class Cenario:
    """A scenario: the rule that picks its episode, the recorded pick, and the dialogue."""

    id: str
    titulo: str
    dominio: str
    regra: Mapping[str, Any]
    episodio: Mapping[str, Any]
    turnos: tuple[Turno, ...]


@dataclass(frozen=True)
class ConjuntoCenarios:
    """The three demo scenarios, the adversarial one and the limit templates."""

    cenarios: tuple[Cenario, ...]
    adversarial: Cenario
    modelos_limite: tuple[Mapping[str, str], ...]


@dataclass(frozen=True)
class Episodio:
    """The real alert (or calm instant) that a scenario rule selected."""

    alerta_id: str | None
    leitura_id: str
    instante: datetime
    grandeza: str | None
    severidade: str | None
    valor_max: float | None
    candidatos: int
    motivo: str


@dataclass(frozen=True)
class AmbienteCenarios:
    """Everything a scenario run needs; the assistant factory gives each scenario its own memory."""

    alertas: Sequence[Alerta]
    fabrica_assistente: Callable[[], Assistente]
    juiz: Juiz
    embedding: EmbeddingModel


@dataclass(frozen=True)
class ExecucaoLimites:
    """The observed run that every row of the limits table must cite."""

    respostas: Sequence[Mapping[str, Any]]
    cenarios: Sequence[Mapping[str, Any]]
    adversarial: Mapping[str, Any]
    calibracao: Mapping[str, Any]
    fatos: Mapping[str, Any]


# ------------------------------------------------------------------ carga


def carregar_cenarios(arquivo: Path = CENARIOS_FILE) -> ConjuntoCenarios:
    """Load and validate data/cenarios.json."""
    try:
        with arquivo.open(encoding="utf-8") as fonte:
            documento = json.load(fonte)
    except (OSError, json.JSONDecodeError) as erro:
        raise RuntimeError(f"Não foi possível carregar {arquivo.name}.") from erro
    _exigir_campos(documento, ("cenarios", "adversarial", "limites"), arquivo.name)
    cenarios = tuple(_cenario_do_item(item, TURNOS_POR_CENARIO) for item in documento["cenarios"])
    if tuple(cenario.id for cenario in cenarios) != IDS_CENARIOS:
        raise ValueError(f"{arquivo.name} precisa trazer os cenários {list(IDS_CENARIOS)} nessa ordem.")
    adversarial = _cenario_do_item(documento["adversarial"], TURNOS_ADVERSARIAIS)
    modelos = tuple(documento["limites"])
    for modelo in modelos:
        _exigir_campos(modelo, ("id", "categoria", "limite", "mitigacao", "risco_residual"), "limites")
        if modelo["categoria"] not in CATEGORIAS_LIMITE:
            raise ValueError(f"Categoria de limite desconhecida: {modelo['categoria']}.")
    return ConjuntoCenarios(cenarios, adversarial, modelos)


def _exigir_campos(item: Mapping[str, Any], campos: Sequence[str], origem: str) -> None:
    ausentes = [campo for campo in campos if campo not in item]
    if ausentes:
        raise ValueError(f"{origem}: faltam os campos {ausentes}.")


def _cenario_do_item(item: Mapping[str, Any], tipos: Sequence[str]) -> Cenario:
    _exigir_campos(item, ("id", "titulo", "dominio", "regra", "episodio", "turnos"), "cenário")
    turnos = tuple(_turno_do_item(turno, item["id"], indice) for indice, turno in enumerate(item["turnos"], 1))
    if tuple(turno.tipo for turno in turnos) != tuple(tipos):
        raise ValueError(f"O cenário {item['id']} precisa ter os turnos {list(tipos)}.")
    return Cenario(item["id"], item["titulo"], item["dominio"], item["regra"], item["episodio"], turnos)


def _turno_do_item(item: Mapping[str, Any], cenario_id: str, indice: int) -> Turno:
    _exigir_campos(item, ("tipo", "pergunta"), f"turno {indice} de {cenario_id}")
    fonte = item.get("fonte_esperada")
    if item["tipo"] in TIPOS_DENTRO_ESCOPO:
        _exigir_campos(fonte or {}, ("pagina", "secao", "trecho_ancora"), f"fonte_esperada de {cenario_id}-t{indice}")
        _exigir_campos(item, ("resposta_referencia",), f"turno {indice} de {cenario_id}")
    else:
        _exigir_campos(item, ("termo_ausente",), f"turno {indice} de {cenario_id}")
    return Turno(
        f"{cenario_id}-t{indice}", indice, item["tipo"], item["pergunta"], fonte,
        item.get("resposta_referencia", ""), item.get("termo_ausente", ""),
    )


# ---------------------------------------------------------------- episódio


def escolher_episodio(regra: Mapping[str, Any], alertas: Sequence[Alerta], leituras: Sequence[Mapping[str, Any]]) -> Episodio:
    """Apply a scenario rule to the real alerts and readings; ties go to the most recent."""
    escolhedor = _ESCOLHEDORES.get(regra.get("tipo"))
    if escolhedor is None:
        raise ValueError(f"Regra de cenário desconhecida: {regra.get('tipo')}.")
    return escolhedor(regra, alertas, leituras)


def descrever_episodio(episodio: Episodio) -> dict[str, Any]:
    """JSON form of the pick, as recorded in data/cenarios.json."""
    return {
        "alerta_id": episodio.alerta_id,
        "leitura_id": episodio.leitura_id,
        "instante": episodio.instante.isoformat(),
        "grandeza": episodio.grandeza,
        "severidade": episodio.severidade,
        "valor_max": episodio.valor_max,
        "candidatos": episodio.candidatos,
        "motivo": episodio.motivo,
    }


def _escolher_maior_severidade(regra: Mapping[str, Any], alertas: Sequence[Alerta], _leituras: Any) -> Episodio:
    for prefixo in regra["grandezas"]:
        candidatos = _alertas_da_grandeza(alertas, prefixo, regra["severidade"])
        if candidatos:
            alerta = max(candidatos, key=lambda item: item.inicio)
            motivo = (
                f"{len(candidatos)} alertas {regra['severidade']} de '{prefixo}'; "
                f"o mais recente é {alerta.id}."
            )
            return _episodio_do_alerta(alerta, len(candidatos), motivo)
    raise ValueError(f"Nenhum alerta {regra['severidade']} para {regra['grandezas']}.")


def _escolher_menor_valor(regra: Mapping[str, Any], alertas: Sequence[Alerta], _leituras: Any) -> Episodio:
    prefixo = regra["grandezas"][0]
    candidatos = _alertas_da_grandeza(alertas, prefixo, regra["severidade"])
    if regra.get("isolado"):
        candidatos = [alerta for alerta in candidatos if _e_o_unico_ativo(alerta, alertas)]
    if not candidatos:
        raise ValueError(f"Nenhum alerta {regra['severidade']} para '{prefixo}'.")
    alerta = min(candidatos, key=lambda item: (item.valor_max, -item.inicio.timestamp()))
    isolamento = ", sozinhos no estado do instante," if regra.get("isolado") else ""
    motivo = (
        f"{len(candidatos)} alertas {regra['severidade']} de '{prefixo}'{isolamento} "
        f"{alerta.id} tem o menor valor máximo ({alerta.valor_max:g} {alerta.unidade})."
    )
    return _episodio_do_alerta(alerta, len(candidatos), motivo)


def _e_o_unico_ativo(alerta: Alerta, alertas: Sequence[Alerta]) -> bool:
    return len(construir_estado_operacional(alertas, alerta.inicio).alertas_ativos) == 1


def _escolher_janela_calma(regra: Mapping[str, Any], alertas: Sequence[Alerta], leituras: Sequence[Mapping[str, Any]]) -> Episodio:
    janela = timedelta(hours=regra["horas"])
    bloqueados = sorted(
        (alerta for alerta in alertas if alerta.severidade in regra["severidades_bloqueadas"]),
        key=lambda alerta: alerta.inicio,
    )
    inicios = [alerta.inicio for alerta in bloqueados]
    maior_fim = list(accumulate((alerta.fim for alerta in bloqueados), max))
    calmas = [leitura for leitura in leituras if _instante_calmo(leitura["timestamp"], inicios, maior_fim, janela)]
    if not calmas:
        raise ValueError(f"Nenhum instante sem {regra['severidades_bloqueadas']} nas {regra['horas']} h anteriores.")
    leitura = max(calmas, key=lambda item: item["timestamp"])
    motivo = (
        f"{len(calmas)} leituras sem alerta {'/'.join(regra['severidades_bloqueadas'])} nas "
        f"{regra['horas']} h anteriores; a mais recente é a leitura {leitura['id']}."
    )
    return Episodio(None, str(leitura["id"]), leitura["timestamp"], None, None, None, len(calmas), motivo)


def _instante_calmo(instante: datetime, inicios: list[datetime], maior_fim: list[datetime], janela: timedelta) -> bool:
    iniciados = bisect_right(inicios, instante)
    return iniciados == 0 or maior_fim[iniciados - 1] < instante - janela


def _alertas_da_grandeza(alertas: Sequence[Alerta], prefixo: str, severidade: str) -> list[Alerta]:
    return [a for a in alertas if a.severidade == severidade and prefixo in _sem_acento(a.grandeza)]


def _episodio_do_alerta(alerta: Alerta, candidatos: int, motivo: str) -> Episodio:
    return Episodio(
        alerta.id, alerta.ids_leitura[0], alerta.inicio, alerta.grandeza, alerta.severidade,
        alerta.valor_max, candidatos, motivo,
    )


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto.casefold())
    return "".join(caractere for caractere in decomposto if not unicodedata.combining(caractere))


_ESCOLHEDORES: dict[str, Callable[[Mapping[str, Any], Sequence[Alerta], Sequence[Mapping[str, Any]]], Episodio]] = {
    REGRA_MAIOR_SEVERIDADE: _escolher_maior_severidade,
    REGRA_MENOR_VALOR: _escolher_menor_valor,
    REGRA_JANELA_CALMA: _escolher_janela_calma,
}


# ---------------------------------------------------------------- execução


def executar_cenario(cenario: Cenario, ambiente: AmbienteCenarios) -> dict[str, Any]:
    """Build the state of the recorded episode, run the dialogue and evaluate each answer."""
    estado = construir_estado_operacional(ambiente.alertas, datetime.fromisoformat(cenario.episodio["instante"]))
    assistente = ambiente.fabrica_assistente()
    contexto = ContextoRespostas(assistente, ambiente.juiz, ambiente.embedding, {})
    turnos = [_executar_turno(turno, cenario, estado, contexto) for turno in cenario.turnos]
    return {
        "id": cenario.id,
        "titulo": cenario.titulo,
        "dominio": cenario.dominio,
        "regra": dict(cenario.regra),
        "episodio": dict(cenario.episodio),
        "estado": _estado_para_json(estado),
        "turnos": turnos,
        "resumo": _resumir_cenario(turnos),
    }


def executar_cenarios(cenarios: Sequence[Cenario], ambiente: AmbienteCenarios) -> list[dict[str, Any]]:
    """Run every scenario with a fresh assistant, so memory never leaks between them."""
    resultados = [executar_cenario(cenario, ambiente) for cenario in cenarios]
    verificar_modelo_unico([turno for resultado in resultados for turno in resultado["turnos"]])
    return resultados


def _executar_turno(turno: Turno, cenario: Cenario, estado: EstadoOperacional, contexto: ContextoRespostas) -> dict[str, Any]:
    pergunta = _pergunta_avaliacao(turno, cenario)
    try:
        resposta = contexto.assistente.responder(turno.pergunta, estado=estado)
        registro = avaliar_resposta(pergunta, resposta, contexto)
    except OpenRouterRequestError as erro:
        return _registro_erro_turno(turno, cenario, erro)
    return {
        **registro,
        "cenario": cenario.id,
        "turno": turno.indice,
        "tipo": turno.tipo,
        "citou": resposta.citou,
        "fonte_esperada": dict(turno.fonte_esperada) if turno.fonte_esperada else None,
        "fonte": _conferir_fonte(turno, resposta),
    }


def _pergunta_avaliacao(turno: Turno, cenario: Cenario) -> PerguntaAvaliacao:
    fonte = turno.fonte_esperada
    return PerguntaAvaliacao(
        id=turno.id,
        escopo=turno.escopo,
        pergunta=turno.pergunta,
        split=SPLIT_CENARIO,
        estado=None,
        resposta_referencia=turno.resposta_referencia,
        paginas_gabarito=(int(fonte["pagina"]),) if fonte else (),
        secoes_gabarito=(str(fonte["secao"]),) if fonte else (),
        trecho_ancora=str(fonte["trecho_ancora"]) if fonte else "",
        categoria=cenario.dominio,
        esperado=ESPERADO_ABSTENCAO if turno.escopo == ESCOPO_FORA else "",
        termo_ausente=turno.termo_ausente,
    )


def _conferir_fonte(turno: Turno, resposta: Resposta) -> dict[str, Any] | None:
    fonte = turno.fonte_esperada
    if not fonte:
        return None
    pagina, secao = int(fonte["pagina"]), str(fonte["secao"])
    return {
        "hit_pagina": any(chunk_relevante_pagina(chunk, (pagina,)) for chunk in resposta.chunks),
        "hit_secao": any(str(chunk["secao"]) == secao for chunk in resposta.chunks),
        "hit_ancora": any(chunk_relevante_estrito(chunk, str(fonte["trecho_ancora"])) for chunk in resposta.chunks),
        "citada": any(item["pagina"] == pagina for item in resposta.fontes),
        "paginas_recuperadas": [chunk["pagina"] for chunk in resposta.chunks],
    }


def _registro_erro_turno(turno: Turno, cenario: Cenario, erro: Exception) -> dict[str, Any]:
    return {
        "id": turno.id,
        "cenario": cenario.id,
        "turno": turno.indice,
        "tipo": turno.tipo,
        "escopo": turno.escopo,
        "pergunta": turno.pergunta,
        "modelo": MODELO_GERADOR,
        "erro": True,
        "mensagem_erro": str(erro),
    }


def _estado_para_json(estado: EstadoOperacional) -> dict[str, Any]:
    return {
        "texto": estado.texto(),
        "severidade_geral": estado.severidade_geral,
        "operacao_normal": estado.operacao_normal,
        "dominios": sorted({alerta.dominio_falha for alerta in estado.alertas_ativos}),
        "alertas_ativos": [
            {
                "id": alerta.id,
                "grandeza": alerta.grandeza,
                "severidade": alerta.severidade,
                "valor_max": alerta.valor_max,
                "unidade": alerta.unidade,
                "inicio": alerta.inicio.isoformat(),
                "dominio_falha": alerta.dominio_falha,
            }
            for alerta in estado.alertas_ativos
        ],
    }


def _resumir_cenario(turnos: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    validos = [turno for turno in turnos if not turno.get("erro")]
    dentro = [turno for turno in validos if turno["escopo"] == ESCOPO_DENTRO]
    fora = [turno for turno in validos if turno["escopo"] == ESCOPO_FORA]
    com_fonte = [turno for turno in dentro if turno.get("fonte")]
    return {
        "n_turnos": len(turnos),
        "erros": len(turnos) - len(validos),
        "faithfulness_media": _media(turno.get("faithfulness") for turno in validos),
        "relevancy_media": _media(turno.get("pontos") for turno in dentro),
        "fontes_esperadas_recuperadas": sum(turno["fonte"]["hit_pagina"] for turno in com_fonte),
        "fontes_esperadas": len(com_fonte),
        "abstencoes_indevidas": sum(bool(turno.get("abstencao_indevida")) for turno in dentro),
        "abstencoes_corretas": sum(bool(turno.get("abstencao_correta")) for turno in fora),
        "respostas_sem_abster_fora_escopo": sum(bool(turno.get("alucinacao_fora_escopo")) for turno in fora),
        "confiancas": [turno["confianca"] for turno in validos],
    }


def _media(valores: Any) -> float | None:
    validos = [float(valor) for valor in valores if valor is not None]
    return sum(validos) / len(validos) if validos else None


def consolidar_cenarios(resultados: Sequence[Mapping[str, Any]], adversarial: Mapping[str, Any]) -> dict[str, Any]:
    """The document written to data/saida/cenarios.json."""
    todos = [*resultados, adversarial]
    verificar_modelo_unico([turno for item in todos for turno in item["turnos"]])
    return {
        "modelo_gerador": MODELO_GERADOR,
        "modelo_juiz": MODELO_JUIZ,
        "cenarios": list(resultados),
        "adversarial": dict(adversarial),
        "resumo": {item["id"]: item["resumo"] for item in todos},
    }


# --------------------------------------------------------------- exibição


def formatar_cenario(resultado: Mapping[str, Any]) -> str:
    """Plain-text view of one scenario: state, dialogue, sources, confidence and evaluation."""
    episodio = resultado["episodio"]
    linhas = [
        f"== {resultado['titulo']} ==",
        f"Episódio: alerta {episodio['alerta_id'] or '—'} | leitura {episodio['leitura_id']} | {episodio['instante']}",
        f"Regra: {episodio['motivo']}",
        f"Estado: {resultado['estado']['texto']}",
    ]
    for turno in resultado["turnos"]:
        linhas.extend(["", *_formatar_turno(turno)])
    linhas.extend(["", f"Resumo: {resultado['resumo']}"])
    return "\n".join(linhas)


def linhas_turnos(resultado: Mapping[str, Any]) -> list[dict[str, Any]]:
    """One table row per turn: query, sources, confidence, abstention and evaluation."""
    linhas = []
    for turno in resultado["turnos"]:
        base = {"turno": turno["turno"], "tipo": turno["tipo"]}
        if turno.get("erro"):
            linhas.append({**base, "erro": turno["mensagem_erro"]})
            continue
        fonte = turno.get("fonte")
        fontes = ", ".join(f"p. {item['pagina']}, seç. {item['secao']}" for item in turno["fontes"])
        linhas.append({
            **base,
            "consulta usada": turno["consulta"],
            "fontes": fontes or "—",
            "fonte esperada recuperada": None if fonte is None else fonte["hit_pagina"],
            "confiança": turno["confianca"],
            "abstenção": turno["abstencao"],
            "faithfulness": turno.get("faithfulness"),
            "cobertura": turno.get("cobertura"),
            "modelo": turno["modelo"],
        })
    return linhas


def _formatar_turno(turno: Mapping[str, Any]) -> list[str]:
    cabecalho = f"-- Turno {turno['turno']} ({turno['tipo']}): {turno['pergunta']}"
    if turno.get("erro"):
        return [cabecalho, f"   ERRO: {turno['mensagem_erro']}"]
    fontes = ", ".join(f"[p. {f['pagina']}, seç. {f['secao']}]" for f in turno["fontes"]) or "nenhuma"
    linhas = [
        cabecalho,
        f"   consulta usada: {turno['consulta']}",
        f"   resposta: {turno['resposta']}",
        f"   fontes: {fontes} | confiança: {turno['confianca']} | abstenção: {turno['abstencao']} | modelo: {turno['modelo']}",
        f"   avaliação: {_formatar_avaliacao(turno)}",
    ]
    if turno.get("fonte"):
        linhas.append(f"   fonte esperada: {_formatar_fonte(turno)}")
    return linhas


def _formatar_avaliacao(turno: Mapping[str, Any]) -> str:
    partes = [f"faithfulness {turno.get('faithfulness')}", f"afirmações {turno.get('contagem')}"]
    if turno["escopo"] == ESCOPO_DENTRO:
        partes.append(f"cobertura {turno.get('cobertura')} (cosseno {turno.get('cosseno')})")
    else:
        partes.append("abstenção correta" if turno.get("abstencao_correta") else "respondeu sem abster")
    return " | ".join(partes)


def _formatar_fonte(turno: Mapping[str, Any]) -> str:
    esperada, achada = turno["fonte_esperada"], turno["fonte"]
    return (
        f"[p. {esperada['pagina']}, seç. {esperada['secao']}] → página recuperada: {achada['hit_pagina']}, "
        f"seção: {achada['hit_secao']}, âncora no chunk: {achada['hit_ancora']}, citada: {achada['citada']} "
        f"(páginas recuperadas {achada['paginas_recuperadas']})"
    )


# ------------------------------------------------------------------ limites


def coletar_fatos_dados(leituras: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Facts about the data that bound what the assistant can know (sensors, names, asset count)."""
    sensores = carregar_sensores()
    with DATA_VARIABLES_FILE.open(encoding="utf-8") as fonte:
        variaveis = {item["id"]: item for item in json.load(fonte)}
    divergentes = [
        (variaveis[chave], sensor) for chave, sensor in sensores.items() if variaveis[chave]["unit"] != sensor.unidade
    ]
    instantes = [leitura["timestamp"] for leitura in leituras]
    original, canonico = divergentes[0] if divergentes else ({"name": "", "unit": ""}, None)
    return {
        "n_sensores": len(sensores),
        "n_com_limiar": sum(sensor.limiares is not None for sensor in sensores.values()),
        "n_unidade_divergente": len(divergentes),
        "exemplo_nome": f"{original['name']} [{original['unit']}]",
        "exemplo_canonico": f"{canonico.grandeza} ({canonico.unidade})" if canonico else "",
        "n_ativos": len({leitura["asset_id"] for leitura in leituras}),
        "n_leituras": len(leituras),
        "dias": (max(instantes) - min(instantes)).days,
    }


def montar_limites(modelos: Sequence[Mapping[str, str]], execucao: ExecucaoLimites) -> dict[str, Any]:
    """One row per limit template, each citing real cases or numbers from the run."""
    ids_modelos = {modelo["id"] for modelo in modelos}
    if ids_modelos != set(_CONSTRUTORES):
        raise ValueError(f"Os limites de cenarios.json divergem dos construtores: {sorted(ids_modelos ^ set(_CONSTRUTORES))}.")
    linhas = [_montar_linha(modelo, execucao) for modelo in modelos]
    faltantes = set(CATEGORIAS_LIMITE) - {linha["categoria"] for linha in linhas}
    if faltantes:
        raise ValueError(f"Categorias de limite sem linha: {sorted(faltantes)}.")
    validar_limites(linhas, execucao)
    return {"modelo_gerador": MODELO_GERADOR, "modelo_juiz": MODELO_JUIZ, "linhas": linhas}


def validar_limites(linhas: Sequence[Mapping[str, Any]], execucao: ExecucaoLimites) -> None:
    """Fail when a row is generic, or cites an id or a sentence that the run did not produce."""
    indice = _indice_evidencias(execucao)
    for linha in linhas:
        if not linha["evidencias"]:
            raise ValueError(f"A linha {linha['id']} não cita caso nem número da execução.")
        for evidencia in linha["evidencias"]:
            _validar_evidencia(evidencia, indice, linha["id"])


def _montar_linha(modelo: Mapping[str, str], execucao: ExecucaoLimites) -> dict[str, Any]:
    valores, evidencias = _CONSTRUTORES[modelo["id"]](execucao)
    return {
        "id": modelo["id"],
        "categoria": modelo["categoria"],
        "limite": modelo["limite"].format_map(valores),
        "mitigacao": modelo["mitigacao"].format_map(valores),
        "risco_residual": modelo["risco_residual"].format_map(valores),
        "evidencias": evidencias,
    }


def _indice_evidencias(execucao: ExecucaoLimites) -> dict[tuple[str, str], set[str]]:
    indice: dict[tuple[str, str], set[str]] = {}
    for origem, registro in _registros(execucao):
        frases = {item["afirmacao"] for item in registro.get("afirmacoes", [])}
        indice[(origem, registro["id"])] = frases
    for caso in execucao.calibracao.get("casos", []):
        indice[(ORIGEM_CALIBRACAO, caso["id"])] = {caso["afirmacao"]}
    return indice


def _validar_evidencia(evidencia: Mapping[str, Any], indice: Mapping[tuple[str, str], set[str]], linha_id: str) -> None:
    if evidencia["origem"] not in ORIGENS_EVIDENCIA:
        raise ValueError(f"{linha_id}: origem de evidência desconhecida: {evidencia['origem']}.")
    if evidencia["id"] is None:
        if evidencia["afirmacao"] is not None:
            raise ValueError(f"{linha_id}: afirmação citada sem id de origem.")
        return
    frases = indice.get((evidencia["origem"], evidencia["id"]))
    if frases is None:
        raise ValueError(f"{linha_id}: o id {evidencia['id']} não existe na execução ({evidencia['origem']}).")
    if evidencia["afirmacao"] is not None and evidencia["afirmacao"] not in frases:
        raise ValueError(f"{linha_id}: a afirmação citada em {evidencia['id']} não existe na execução.")


def _registros(execucao: ExecucaoLimites) -> list[tuple[str, Mapping[str, Any]]]:
    turnos = [turno for cenario in (*execucao.cenarios, execucao.adversarial) for turno in cenario["turnos"]]
    pares = [(ORIGEM_RESPOSTAS, registro) for registro in execucao.respostas]
    pares.extend((ORIGEM_CENARIOS, turno) for turno in turnos)
    return [(origem, registro) for origem, registro in pares if not registro.get("erro")]


def _evidencia(origem: str, id_: str | None, detalhe: str, afirmacao: str | None = None) -> dict[str, Any]:
    return {"origem": origem, "id": id_, "detalhe": detalhe, "afirmacao": afirmacao}


def _fmt(valor: float | None) -> str:
    return "n/d" if valor is None else f"{valor:.3f}".replace(".", ",")


def _score_do_melhor_chunk(registro: Mapping[str, Any]) -> str:
    chunks = registro.get("chunks") or []
    return f"{chunks[0]['score_rerank_bruto']:.2f}".replace(".", ",") if chunks else "n/d"


def _desfecho(registro: Mapping[str, Any]) -> str:
    return "abstenção" if registro["abstencao"] else "respondeu sem abster"


def _limite_fora_escopo(execucao: ExecucaoLimites) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    fora = [(origem, item) for origem, item in _registros(execucao) if item["escopo"] == ESCOPO_FORA]
    responderam = [item["id"] for _, item in fora if not item["abstencao"]]
    valores = {
        "n_fora": len(fora),
        "n_abstiveram": len(fora) - len(responderam),
        "n_responderam": len(responderam),
        "ids_responderam": ", ".join(responderam) or "nenhuma",
    }
    evidencias = [
        _evidencia(origem, item["id"], f"{_desfecho(item)}; escore bruto {_score_do_melhor_chunk(item)}; confiança {item['confianca']}")
        for origem, item in fora
    ]
    return valores, evidencias


def _limite_alucinacao(execucao: ExecucaoLimites) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    registros = _registros(execucao)
    achados = [
        (origem, item, afirmacao)
        for origem, item in registros
        for afirmacao in item.get("afirmacoes", [])
        if afirmacao["rotulo"] in ROTULOS_ALUCINACAO
    ]
    total = sum(len(item.get("afirmacoes", [])) for _, item in registros)
    valores = {
        "n_achados": len(achados),
        "n_rotuladas": total,
        "n_externa": sum(a["rotulo"] == ROTULO_EXTERNA for _, _, a in achados),
        "n_contradiz": sum(a["rotulo"] == ROTULO_CONTRADIZ for _, _, a in achados),
        "ids": ", ".join(sorted({item["id"] for _, item, _ in achados})) or "nenhum",
    }
    evidencias = [
        _evidencia(origem, item["id"], f"{a['rotulo']} ({a['guarda'] or 'juiz'})", a["afirmacao"])
        for origem, item, a in achados
    ] or [_evidencia(ORIGEM_RESPOSTAS, None, f"0 de {total} afirmações rotuladas EXTERNA ou CONTRADIZ")]
    return valores, evidencias


def _limite_adversarial(execucao: ExecucaoLimites) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    turnos = [turno for turno in execucao.adversarial["turnos"] if not turno.get("erro")]
    valores = {
        "n_turnos": len(turnos),
        "n_abstiveram": sum(bool(turno["abstencao"]) for turno in turnos),
        "estado": execucao.adversarial["estado"]["texto"],
    }
    evidencias = [
        _evidencia(ORIGEM_CENARIOS, turno["id"], f"{turno['tipo']}: {_desfecho(turno)}; faithfulness {_fmt(turno.get('faithfulness'))}")
        for turno in turnos
    ]
    return valores, evidencias


def _limite_corpus(execucao: ExecucaoLimites) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cenarios = [turno for _, turno in _registros(execucao) if turno.get("tipo") == TURNO_FORA_ESCOPO]
    dentro = [turno for _, turno in _registros(execucao) if turno.get("fonte")]
    recuperadas = [turno for turno in dentro if turno["fonte"]["hit_pagina"]]
    valores = {
        "n_troubleshooting": len(cenarios),
        "n_abstiveram": sum(bool(turno["abstencao"]) for turno in cenarios),
        "n_fonte_recuperada": len(recuperadas),
        "n_com_fonte": len(dentro),
    }
    evidencias = [_evidencia(ORIGEM_CENARIOS, turno["id"], f"{turno['pergunta']} → {_desfecho(turno)}") for turno in cenarios]
    evidencias += [
        _evidencia(ORIGEM_CENARIOS, turno["id"], f"fonte esperada recuperada: {turno['fonte']['hit_pagina']}")
        for turno in dentro
    ]
    return valores, evidencias


def _limite_juiz(execucao: ExecucaoLimites) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    metricas = execucao.calibracao["metricas"]["todos"]["juiz_com_guardas"]
    divergentes = [caso for caso in execucao.calibracao["casos"] if caso["final"] != caso["esperado"]]
    valores = {
        "n_casos": metricas["n"],
        "acuracia": _fmt(metricas["acuracia"]),
        "revocacao_externa": _fmt(metricas["revocacao_externa"]),
        "precisao_externa": _fmt(metricas["precisao_externa"]),
        "n_divergentes": len(divergentes),
    }
    evidencias = [_evidencia(ORIGEM_CALIBRACAO, None, f"{metricas['n']} casos; acurácia {valores['acuracia']}")]
    evidencias += [
        _evidencia(ORIGEM_CALIBRACAO, caso["id"], f"esperado {caso['esperado']}, final {caso['final']}", caso["afirmacao"])
        for caso in divergentes
    ]
    return valores, evidencias


def _limite_amostra(execucao: ExecucaoLimites) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    respostas = [item for item in execucao.respostas if not item.get("erro")]
    dentro = [item for item in respostas if item["escopo"] == ESCOPO_DENTRO]
    fora_teste = [item for item in respostas if item["escopo"] == ESCOPO_FORA and item["split"] == "teste"]
    valores = {
        "n_dentro": len(dentro),
        "n_fora": len(respostas) - len(dentro),
        "n_fora_teste": len(fora_teste),
        "n_turnos": sum(len(cenario["turnos"]) for cenario in (*execucao.cenarios, execucao.adversarial)),
        "faithfulness": _fmt(_media(item.get("faithfulness") for item in respostas)),
    }
    detalhe = f"{len(respostas)} respostas avaliadas; faithfulness média {valores['faithfulness']}"
    return valores, [_evidencia(ORIGEM_RESPOSTAS, None, detalhe)]


def _limite_limiar(execucao: ExecucaoLimites) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    indevidas = [(origem, item) for origem, item in _registros(execucao) if item.get("abstencao_indevida")]
    valores = {
        "limiar": _fmt(LIMIAR_ABSTENCAO),
        "n_indevidas": len(indevidas),
        "ids": ", ".join(item["id"] for _, item in indevidas) or "nenhuma",
    }
    evidencias = [
        _evidencia(origem, item["id"], f"abstenção indevida; escore bruto {_score_do_melhor_chunk(item)}; limiar {valores['limiar']}")
        for origem, item in indevidas
    ] or [_evidencia(ORIGEM_RESPOSTAS, None, f"0 abstenções indevidas com limiar {valores['limiar']}")]
    return valores, evidencias


def _limite_dados_limiares(execucao: ExecucaoLimites) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    fatos = execucao.fatos
    valores = {
        "n_sensores": fatos["n_sensores"],
        "n_com_limiar": fatos["n_com_limiar"],
        "n_sem_limiar": fatos["n_sensores"] - fatos["n_com_limiar"],
    }
    detalhe = f"{fatos['n_com_limiar']} de {fatos['n_sensores']} variáveis têm limiar em active_assets.json"
    return valores, [_evidencia(ORIGEM_DADOS, None, detalhe)]


def _limite_dados_nomes(execucao: ExecucaoLimites) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    fatos = execucao.fatos
    valores = {
        "n_divergentes": fatos["n_unidade_divergente"],
        "n_sensores": fatos["n_sensores"],
        "exemplo_nome": fatos["exemplo_nome"],
        "exemplo_canonico": fatos["exemplo_canonico"],
    }
    detalhe = f"{fatos['exemplo_nome']} em data_variables.json × {fatos['exemplo_canonico']} no mapeamento canônico"
    return valores, [_evidencia(ORIGEM_DADOS, None, detalhe)]


def _limite_dados_baseline(execucao: ExecucaoLimites) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    fatos = execucao.fatos
    preventiva = next((item for item in execucao.cenarios if item["id"] == "preventiva"), None)
    calmas = preventiva["episodio"]["candidatos"] if preventiva else 0
    valores = {
        "n_ativos": fatos["n_ativos"],
        "n_leituras": fatos["n_leituras"],
        "dias": fatos["dias"],
        "n_calmas": calmas,
    }
    detalhe = f"{fatos['n_ativos']} ativo, {fatos['n_leituras']} leituras em {fatos['dias']} dias; {calmas} leituras calmas nas 24 h anteriores"
    return valores, [_evidencia(ORIGEM_DADOS, None, detalhe)]


_CONSTRUTORES: dict[str, Callable[[ExecucaoLimites], tuple[dict[str, Any], list[dict[str, Any]]]]] = {
    "fora_escopo_abstencao": _limite_fora_escopo,
    "alucinacao_afirmacoes": _limite_alucinacao,
    "alucinacao_adversarial": _limite_adversarial,
    "corpus_troubleshooting": _limite_corpus,
    "metodo_juiz": _limite_juiz,
    "metodo_amostra": _limite_amostra,
    "metodo_limiar_abstencao": _limite_limiar,
    "dados_limiares": _limite_dados_limiares,
    "dados_nomes": _limite_dados_nomes,
    "dados_baseline": _limite_dados_baseline,
}
