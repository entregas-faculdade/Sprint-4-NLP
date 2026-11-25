"""Build a deterministic operational snapshot from active alert episodes."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from src.pln.alertas import Alerta
from src.pln.config import ACTIVE_ASSET_LOCATION, ACTIVE_ASSET_NAME, CLASSES_SEVERIDADE_RELATORIO

SEVERIDADE_ORDEM = {severidade: indice for indice, severidade in enumerate(CLASSES_SEVERIDADE_RELATORIO)}


@dataclass(frozen=True)
class AlertaOperacional:
    """Only alert fields needed by state-aware retrieval and display."""

    id: str
    grandeza: str
    severidade: str
    valor_max: float
    unidade: str
    inicio: datetime
    dominio_falha: str


@dataclass(frozen=True)
class EstadoOperacional:
    """The active alert set for one asset at a specific instant."""

    ativo: str
    instante: datetime
    alertas_ativos: tuple[AlertaOperacional, ...]
    severidade_geral: str
    operacao_normal: bool

    def texto(self) -> str:
        """Render the snapshot from its stored alert facts, in stable order."""
        if self.operacao_normal:
            return f"{self.ativo}: operação normal em {self.instante.isoformat(timespec='seconds')}."
        alert_texts = [_format_alert(alerta) for alerta in self.alertas_ativos]
        return f"{self.ativo}: severidade geral {self.severidade_geral}. " + " ".join(alert_texts)


def construir_estado_operacional(
    alertas: Iterable[Alerta], instante: datetime
) -> EstadoOperacional:
    """Select episodes active at the requested instant and summarize their severity."""
    instante_utc = _normalizar_instante(instante)
    alertas_ativos = tuple(
        sorted(
            (_converter_alerta(alerta) for alerta in alertas if _esta_ativo(alerta, instante_utc)),
            key=lambda alerta: (alerta.inicio, alerta.id),
        )
    )
    severidade = _severidade_geral(alertas_ativos)
    return EstadoOperacional(
        ativo=f"{ACTIVE_ASSET_NAME} ({ACTIVE_ASSET_LOCATION})",
        instante=instante_utc,
        alertas_ativos=alertas_ativos,
        severidade_geral=severidade,
        operacao_normal=not alertas_ativos,
    )


def _esta_ativo(alerta: Alerta, instante: datetime) -> bool:
    inicio = _normalizar_instante(alerta.inicio)
    fim = _normalizar_instante(alerta.fim)
    if inicio > fim:
        raise ValueError(f"O alerta {alerta.id} termina antes do início.")
    return inicio <= instante <= fim


def _converter_alerta(alerta: Alerta) -> AlertaOperacional:
    if alerta.severidade not in SEVERIDADE_ORDEM:
        raise ValueError(f"Severidade desconhecida no alerta {alerta.id}.")
    return AlertaOperacional(
        id=alerta.id,
        grandeza=alerta.grandeza,
        severidade=alerta.severidade,
        valor_max=float(alerta.valor_max),
        unidade=alerta.unidade,
        inicio=_normalizar_instante(alerta.inicio),
        dominio_falha=_dominio_da_grandeza(alerta.grandeza),
    )


def _dominio_da_grandeza(grandeza: str) -> str:
    normalizada = _normalizar_texto(grandeza)
    if "temperatura" in normalizada:
        return "térmica"
    if "corrente" in normalizada:
        return "elétrica"
    if "vibra" in normalizada or "velocidade" in normalizada:
        return "mecânica"
    raise ValueError(f"Não há domínio de falha definido para a grandeza {grandeza}.")


def _severidade_geral(alertas: tuple[AlertaOperacional, ...]) -> str:
    if not alertas:
        return "normal"
    return max((alerta.severidade for alerta in alertas), key=SEVERIDADE_ORDEM.__getitem__)


def _format_alert(alerta: AlertaOperacional) -> str:
    valor = f"{alerta.valor_max:g}"
    inicio = alerta.inicio.isoformat(timespec="seconds")
    return (
        f"Alerta {alerta.id}: {alerta.grandeza}, severidade {alerta.severidade}, "
        f"valor máximo {valor} {alerta.unidade}, início {inicio}."
    )


def _normalizar_instante(instante: datetime) -> datetime:
    if instante.tzinfo is None:
        return instante.replace(tzinfo=timezone.utc)
    return instante.astimezone(timezone.utc)


def _normalizar_texto(texto: str) -> str:
    decomposed = unicodedata.normalize("NFKD", texto.casefold())
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return "".join(char if char.isalnum() or char.isspace() else " " for char in without_marks)
