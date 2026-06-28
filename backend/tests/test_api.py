import asyncio
from typing import Literal

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


def test_api_retorna_404_ao_pegar_ticket_com_fila_vazia(api_app: Any):
    response = request(
        api_app,
        "PATCH",
        "/tickets/next",
        {"tecnico": "tecnico-api"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Nenhum ticket pendente na fila."}


def test_api_retorna_400_ao_fechar_ticket_inexistente(api_app: Any):
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
def test_api_retorna_422_ao_abrir_ticket_com_campo_vazio(api_app: Any, payload: dict[str, str]):
    response = request(api_app, "POST", "/tickets", payload)

    assert response.status_code == 422


@pytest.mark.parametrize("tecnico", ["", "   "])
def test_api_retorna_422_ao_pegar_ticket_com_tecnico_vazio(api_app: Any, tecnico: Literal[''] | Literal['   ']):
    response = request(
        api_app,
        "PATCH",
        "/tickets/next",
        {"tecnico": tecnico},
    )

    assert response.status_code == 422
#  NOVOS TESTES: ENTREGA 3 

def test_get_stats_empty_queue(api_app: Any):
    response = request(api_app, "GET", "/tickets/stats")
    assert response.status_code == 200
    assert response.json() == {"pending": 0, "in_progress": 0, "closed": 0}

def test_get_stats_after_create(api_app: Any):
    request(api_app, "POST", "/tickets", {"usuario": "teste", "descricao": "erro na rede"})
    
    response = request(api_app, "GET", "/tickets/stats")
    assert response.status_code == 200
    assert response.json()["pending"] == 1

def test_get_status_open_empty(api_app: Any):
    response = request(api_app, "GET", "/tickets/status/OPEN")
    assert response.status_code == 200
    assert response.json() == []

def test_get_status_open_after_create(api_app: Any):
    request(api_app, "POST", "/tickets", {"usuario": "teste", "descricao": "erro na rede"})
    
    response = request(api_app, "GET", "/tickets/status/OPEN")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == "OPEN"

def test_get_status_in_progress_after_assign(api_app: Any):
    request(api_app, "POST", "/tickets", {"usuario": "teste", "descricao": "erro na rede"})
    request(api_app, "PATCH", "/tickets/next", {"tecnico": "tech_01"})
    
    response = request(api_app, "GET", "/tickets/status/IN_PROGRESS")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == "IN_PROGRESS"

def test_get_status_invalid_returns_422(api_app: Any):
    response = request(api_app, "GET", "/tickets/status/INVALIDO")
    assert response.status_code == 422

def test_get_ticket_by_id_not_found(api_app: Any):
    response = request(api_app, "GET", "/tickets/id-inexistente-123")
    assert response.status_code == 404

def test_get_ticket_by_id_success(api_app: Any):
    cria_resp = request(api_app, "POST", "/tickets", {"usuario": "teste", "descricao": "erro na rede"})
    ticket_id = cria_resp.json()["ticket_id"]
    
    response = request(api_app, "GET", f"/tickets/{ticket_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["ticket_id"] == ticket_id
    assert data["usuario"] == "teste"
    assert data["descricao"] == "erro na rede"
    assert data["status"] == "OPEN"
    assert "timestamp_abertura" in data


