
import pytest
import redis

from app.core.config import settings
from app.queue.redis_queue import FilaTickets, STATUS_OPEN


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
