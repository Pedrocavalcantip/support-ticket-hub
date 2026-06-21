from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier

import pytest
import redis

from app.core.config import settings
from app.queue.redis_queue import (
    FilaTickets,
    STATUS_CLOSED,
    STATUS_IN_PROGRESS,
    STATUS_OPEN,
)


def assert_timestamp_utc(valor):
    timestamp = datetime.fromisoformat(valor)
    assert timestamp.utcoffset() == timedelta(0)


@pytest.fixture
def fila():
    try:
        f = FilaTickets(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
    except redis.exceptions.RedisError:
        pytest.skip("Redis nao esta acessivel (suba com 'docker compose up -d redis')")
    f.limpar_tudo()
    yield f
    f.limpar_tudo()


def test_abrir_enfileira_com_os_campos_exigidos(fila):
    ticket = fila.abrir({"usuario": "joao", "descricao": "Notebook nao liga"})

    # Os campos que o enunciado exige nao podem vir vazios.
    for campo in ("ticket_id", "usuario", "descricao", "status", "timestamp_abertura"):
        assert campo in ticket and ticket[campo] != ""

    assert ticket["status"] == STATUS_OPEN
    assert_timestamp_utc(ticket["timestamp_abertura"])
    assert fila.tamanho_fila() == 1

    abertos = fila.listar()
    assert len(abertos) == 1
    assert abertos[0]["ticket_id"] == ticket["ticket_id"]


def test_mantem_ordem_de_chegada_fifo(fila):
    primeiro = fila.abrir({"usuario": "ana", "descricao": "Sem acesso ao email"})
    segundo = fila.abrir({"usuario": "bia", "descricao": "Impressora travada"})

    abertos = fila.listar()
    ids_na_fila = [t["ticket_id"] for t in abertos]

    assert ids_na_fila == [primeiro["ticket_id"], segundo["ticket_id"]]
    assert fila.tamanho_fila() == 2


def test_pegar_proximo_ticket_respeita_fifo_e_atualiza_estado(fila):
    primeiro = fila.abrir({"usuario": "ana", "descricao": "Sem acesso ao email"})
    segundo = fila.abrir({"usuario": "bia", "descricao": "Impressora travada"})

    atribuido = fila.pegar("tecnico-01")

    assert atribuido is not None
    assert atribuido["ticket_id"] == primeiro["ticket_id"]
    assert atribuido["status"] == STATUS_IN_PROGRESS
    assert atribuido["tecnico"] == "tecnico-01"
    assert_timestamp_utc(atribuido["timestamp_atendimento"])
    assert fila.tamanho_fila() == 1
    assert [ticket["ticket_id"] for ticket in fila.listar()] == [
        segundo["ticket_id"]
    ]

    em_atendimento = fila.listar_tickets(STATUS_IN_PROGRESS)
    assert len(em_atendimento) == 1
    assert em_atendimento[0]["ticket_id"] == primeiro["ticket_id"]


def test_fechar_ticket_em_atendimento(fila):
    aberto = fila.abrir({"usuario": "carla", "descricao": "VPN indisponivel"})
    atribuido = fila.pegar("tecnico-02")

    assert atribuido is not None
    assert fila.fechar(aberto["ticket_id"]) is True

    fechados = fila.listar_tickets(STATUS_CLOSED)
    assert len(fechados) == 1
    assert fechados[0]["ticket_id"] == aberto["ticket_id"]
    assert fechados[0]["status"] == STATUS_CLOSED
    assert_timestamp_utc(fechados[0]["timestamp_fechamento"])
    assert fila.listar_tickets(STATUS_IN_PROGRESS) == []


def test_pegar_ticket_com_fila_vazia_retorna_none(fila):
    assert fila.pegar("tecnico-03") is None


def test_fechar_ticket_inexistente_retorna_false(fila):
    assert fila.fechar("ticket-inexistente") is False


def test_nao_fecha_ticket_que_ainda_esta_aberto(fila):
    aberto = fila.abrir({"usuario": "diego", "descricao": "Mouse com defeito"})

    assert fila.fechar(aberto["ticket_id"]) is False
    assert fila.tamanho_fila() == 1
    assert fila.listar()[0]["status"] == STATUS_OPEN


@pytest.mark.parametrize("campo", ["usuario", "descricao"])
@pytest.mark.parametrize("valor", ["", "   "])
def test_abrir_ticket_rejeita_campo_vazio(fila, campo, valor):
    dados = {"usuario": "elisa", "descricao": "Monitor piscando"}
    dados[campo] = valor

    with pytest.raises(ValueError):
        fila.abrir(dados)

    assert fila.tamanho_fila() == 0


@pytest.mark.parametrize("tecnico", ["", "   ", None])
def test_pegar_ticket_rejeita_tecnico_vazio_sem_consumir_fila(fila, tecnico):
    aberto = fila.abrir({"usuario": "fabio", "descricao": "Sistema lento"})

    with pytest.raises(ValueError, match="tecnico e obrigatorio"):
        fila.pegar(tecnico)

    assert fila.tamanho_fila() == 1
    assert fila.listar()[0]["ticket_id"] == aberto["ticket_id"]


def test_dois_tecnicos_nao_recebem_o_mesmo_ticket(fila):
    aberto = fila.abrir({"usuario": "gabi", "descricao": "Conta bloqueada"})
    barreira = Barrier(2)

    def consumir(tecnico):
        cliente = FilaTickets(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
        barreira.wait(timeout=5)
        return cliente.pegar(tecnico)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futuros = [
            executor.submit(consumir, "tecnico-a"),
            executor.submit(consumir, "tecnico-b"),
        ]
        resultados = [futuro.result(timeout=10) for futuro in futuros]

    atribuidos = [resultado for resultado in resultados if resultado is not None]

    assert len(atribuidos) == 1
    assert atribuidos[0]["ticket_id"] == aberto["ticket_id"]
    assert atribuidos[0]["tecnico"] in {"tecnico-a", "tecnico-b"}
    assert resultados.count(None) == 1
    assert fila.tamanho_fila() == 0

    em_atendimento = fila.listar_tickets(STATUS_IN_PROGRESS)
    assert len(em_atendimento) == 1
    assert em_atendimento[0]["ticket_id"] == aberto["ticket_id"]
