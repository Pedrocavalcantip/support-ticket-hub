import asyncio

import httpx
import pytest
import redis


@pytest.fixture
def api_app():
    try:
        from app.main import app
        from app.services import ticket_service
    except redis.exceptions.RedisError:
        pytest.skip("Redis nao esta acessivel (suba com 'docker compose up -d redis')")

    ticket_service._fila.limpar_tudo()
    yield app
    ticket_service._fila.limpar_tudo()


def request(api_app, method, path, payload=None):
    async def send_request():
        transport = httpx.ASGITransport(app=api_app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            if payload is None:
                return await client.request(method, path)
            return await client.request(method, path, json=payload)

    return asyncio.run(send_request())


def test_api_retorna_404_ao_pegar_ticket_com_fila_vazia(api_app):
    response = request(
        api_app,
        "PATCH",
        "/tickets/next",
        {"tecnico": "tecnico-api"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Nenhum ticket pendente na fila."}


def test_api_retorna_400_ao_fechar_ticket_inexistente(api_app):
    response = request(api_app, "PATCH", "/tickets/ticket-inexistente/close")

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Ticket inexistente ou nao esta em atendimento."
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"usuario": "", "descricao": "Notebook nao liga"},
        {"usuario": "joao", "descricao": "   "},
    ],
)
def test_api_retorna_422_ao_abrir_ticket_com_campo_vazio(api_app, payload):
    response = request(api_app, "POST", "/tickets", payload)

    assert response.status_code == 422


@pytest.mark.parametrize("tecnico", ["", "   "])
def test_api_retorna_422_ao_pegar_ticket_com_tecnico_vazio(api_app, tecnico):
    response = request(
        api_app,
        "PATCH",
        "/tickets/next",
        {"tecnico": tecnico},
    )

    assert response.status_code == 422
