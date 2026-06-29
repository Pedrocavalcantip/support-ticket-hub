"""
Testes do subsistema SSE.

Abordagem em dois níveis
------------------------
O `httpx.ASGITransport` não mantém conexões HTTP/1.1 keep-alive de longa
duração em testes (ele fecha o stream ASGI assim que o handler retorna o
status), por isso não é possível testar SSE end-to-end via ASGI transport.

Em vez disso, os testes são divididos em:

1. **Unidade** — testa `_event_generator` diretamente, sem HTTP.
   Injetamos eventos na queue do broadcaster e verificamos o formato SSE.

2. **Integração do broadcaster** — testa que `ticket_service.*` chama
   `broadcaster.publish_sync` com o tipo e stats corretos, usando um
   subscriber real na fila do broadcaster.
"""
import asyncio
import json

import pytest
import redis


# ── Fixture ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def wired_app():
    """Inicializa broadcaster com o loop do pytest-asyncio e limpa Redis."""
    try:
        from app.services import ticket_service
        from app.core.broadcaster import broadcaster
    except redis.exceptions.RedisError:
        pytest.skip("Redis nao esta acessivel (suba com 'docker compose up -d redis')")

    ticket_service._fila.limpar_tudo()

    loop = asyncio.get_event_loop()
    broadcaster._set_loop(loop)

    yield broadcaster, ticket_service

    broadcaster._clients.clear()
    ticket_service._fila.limpar_tudo()


# ── Testes de unidade: _event_generator ──────────────────────────────────────


@pytest.mark.asyncio
async def test_event_generator_entrega_evento_da_queue():
    """_event_generator deve formatar corretamente uma mensagem SSE `data:`."""
    from app.api.events import _event_generator
    from unittest.mock import MagicMock

    request = MagicMock()

    # Injeta um evento na queue antes de chamar o generator
    q: asyncio.Queue = asyncio.Queue()
    payload = json.dumps({"type": "ticket_created", "stats": {"pending": 1}})
    await q.put(payload)

    from app.core.broadcaster import broadcaster
    original_subscribe = broadcaster.subscribe
    original_unsubscribe = broadcaster.unsubscribe
    broadcaster.subscribe = lambda: q
    broadcaster.unsubscribe = lambda _q: None

    lines = []
    try:
        async for chunk in _event_generator(request):
            lines.append(chunk)
            break  # apenas o primeiro chunk
    finally:
        broadcaster.subscribe = original_subscribe
        broadcaster.unsubscribe = original_unsubscribe

    assert len(lines) == 1
    assert lines[0] == f"data: {payload}\n\n"



@pytest.mark.asyncio
async def test_event_generator_envia_keepalive_no_timeout():
    """`_event_generator` deve emitir `: keepalive\\n\\n` quando a queue fica vazia."""
    from app.api.events import _event_generator, _KEEPALIVE_TIMEOUT
    from unittest.mock import MagicMock, patch

    request = MagicMock()
    q: asyncio.Queue = asyncio.Queue()  # queue vazia → timeout imediato

    from app.core.broadcaster import broadcaster
    original_subscribe = broadcaster.subscribe
    original_unsubscribe = broadcaster.unsubscribe
    broadcaster.subscribe = lambda: q
    broadcaster.unsubscribe = lambda _q: None

    lines = []
    # Reduz o timeout para 0.1 s para o teste ser rápido
    with patch("app.api.events._KEEPALIVE_TIMEOUT", 0.1):
        gen = _event_generator(request)
        try:
            async for chunk in gen:
                lines.append(chunk)
                break  # apenas o primeiro chunk (keepalive)
        finally:
            broadcaster.subscribe = original_subscribe
            broadcaster.unsubscribe = original_unsubscribe

    assert len(lines) == 1
    assert lines[0] == ": keepalive\n\n"


# ── Testes de integração: broadcaster recebe eventos corretos ────────────────


@pytest.mark.asyncio
async def test_abrir_ticket_publica_ticket_created(wired_app):
    """ticket_service.abrir_ticket deve publicar evento 'ticket_created'."""
    broadcaster, ticket_service = wired_app

    q = broadcaster.subscribe()
    try:
        ticket_service.abrir_ticket({"usuario": "alice", "descricao": "Sem acesso"})

        # O evento é agendado via call_soon_threadsafe; cedemos o loop
        await asyncio.sleep(0)

        assert not q.empty(), "Nenhum evento publicado no broadcaster"
        evt = json.loads(await asyncio.wait_for(q.get(), timeout=1.0))
        assert evt["type"] == "ticket_created"
        assert "stats" in evt
        assert evt["stats"]["pending"] == 1
        assert evt["stats"]["in_progress"] == 0
        assert evt["stats"]["closed"] == 0
    finally:
        broadcaster.unsubscribe(q)


@pytest.mark.asyncio
async def test_pegar_ticket_publica_ticket_assigned(wired_app):
    """ticket_service.pegar_ticket deve publicar evento 'ticket_assigned'."""
    broadcaster, ticket_service = wired_app

    ticket_service.abrir_ticket({"usuario": "bob", "descricao": "CPU 100%"})

    q = broadcaster.subscribe()
    try:
        ticket_service.pegar_ticket("tech_01")

        await asyncio.sleep(0)

        assert not q.empty()
        evt = json.loads(await asyncio.wait_for(q.get(), timeout=1.0))
        assert evt["type"] == "ticket_assigned"
        assert evt["stats"]["pending"] == 0
        assert evt["stats"]["in_progress"] == 1
    finally:
        broadcaster.unsubscribe(q)


@pytest.mark.asyncio
async def test_fechar_ticket_publica_ticket_closed(wired_app):
    """ticket_service.fechar_ticket deve publicar evento 'ticket_closed'."""
    broadcaster, ticket_service = wired_app

    criado = ticket_service.abrir_ticket({"usuario": "carol", "descricao": "Impressora"})
    ticket_service.pegar_ticket("tech_02")

    q = broadcaster.subscribe()
    try:
        ticket_service.fechar_ticket(criado["ticket_id"])

        await asyncio.sleep(0)

        assert not q.empty()
        evt = json.loads(await asyncio.wait_for(q.get(), timeout=1.0))
        assert evt["type"] == "ticket_closed"
        assert evt["stats"]["closed"] == 1
        assert evt["stats"]["in_progress"] == 0
        assert evt["stats"]["pending"] == 0
    finally:
        broadcaster.unsubscribe(q)


@pytest.mark.asyncio
async def test_broadcaster_nao_publica_se_sem_subscribers(wired_app):
    """publish_sync não deve falhar quando não há subscribers (não levanta exceção)."""
    broadcaster, ticket_service = wired_app

    # Garante que broadcaster._clients está vazio
    broadcaster._clients.clear()

    # Deve executar sem erro
    ticket_service.abrir_ticket({"usuario": "dave", "descricao": "Mouse quebrado"})

    await asyncio.sleep(0)
    # Nenhum subscriber → nada para verificar; o teste passa se não houver exceção
    assert len(broadcaster._clients) == 0


@pytest.mark.asyncio
async def test_broadcaster_nao_publica_sem_loop_registrado(wired_app):
    """publish_sync deve ser tolerante a broadcaster._loop = None."""
    broadcaster, ticket_service = wired_app

    original_loop = broadcaster._loop
    broadcaster._loop = None

    try:
        # Não deve lançar exceção
        ticket_service.abrir_ticket({"usuario": "eve", "descricao": "Teclado"})
    finally:
        broadcaster._loop = original_loop
