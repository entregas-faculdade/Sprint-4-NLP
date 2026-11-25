from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.pln.alertas import Alerta
from src.pln.estado import construir_estado_operacional


def _criar_alerta(grandeza: str, inicio: datetime, severidade: str = "critico") -> Alerta:
    fim = inicio + timedelta(minutes=5)
    return Alerta(
        id="A-0042",
        ativo="WEG W22 (fábrica)",
        sensor_id="sensor-1",
        grandeza=grandeza,
        unidade="A",
        severidade=severidade,
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


def test_estado_inclui_alerta_ativo_e_dominio_eletrico() -> None:
    inicio = datetime(2026, 8, 22, 12, tzinfo=timezone.utc)
    alerta = _criar_alerta("Corrente elétrica por fase", inicio)

    estado = construir_estado_operacional([alerta], inicio + timedelta(minutes=2))

    assert estado.operacao_normal is False
    assert estado.severidade_geral == "critico"
    assert estado.alertas_ativos[0].dominio_falha == "elétrica"
    assert "A-0042" in estado.texto()
    assert "160 A" in estado.texto()


def test_estado_normal_ignora_episodio_encerrado() -> None:
    inicio = datetime(2026, 8, 22, 12, tzinfo=timezone.utc)
    alerta = _criar_alerta("Temperatura do enrolamento", inicio)

    estado = construir_estado_operacional([alerta], inicio + timedelta(minutes=6))

    assert estado.operacao_normal is True
    assert estado.severidade_geral == "normal"
    assert estado.alertas_ativos == ()
    assert "operação normal" in estado.texto()


def test_estado_mapeia_grandezas_termica_e_mecanica() -> None:
    inicio = datetime(2026, 8, 22, 12, tzinfo=timezone.utc)
    alertas = [
        _criar_alerta("Temperatura do enrolamento", inicio, "moderado"),
        _criar_alerta("Vibração no mancal", inicio + timedelta(minutes=1), "leve"),
        _criar_alerta("Velocidade do eixo", inicio + timedelta(minutes=2), "critico"),
    ]

    estado = construir_estado_operacional(alertas, inicio + timedelta(minutes=3))

    assert [alerta.dominio_falha for alerta in estado.alertas_ativos] == [
        "térmica",
        "mecânica",
        "mecânica",
    ]
    assert estado.severidade_geral == "critico"
