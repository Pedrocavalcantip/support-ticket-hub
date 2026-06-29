import asyncio
import json
from typing import Any

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
def test_api_retorna_422_ao_pegar_ticket_com_tecnico_vazio(api_app: Any, tecnico: str):
    response = request(
        api_app,
        "PATCH",
        "/tickets/next",
        {"tecnico": tecnico},
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# NOVOS TESTES: ENTREGA 3
# ---------------------------------------------------------------------------

# ── GET /tickets/stats ──────────────────────────────────────────────────────

def test_get_stats_empty_queue(api_app: Any):
    response = request(api_app, "GET", "/tickets/stats")
    assert response.status_code == 200
    assert response.json() == {"pending": 0, "in_progress": 0, "closed": 0}


def test_get_stats_after_create(api_app: Any):
    request(api_app, "POST", "/tickets", {"usuario": "teste", "descricao": "erro na rede"})

    response = request(api_app, "GET", "/tickets/stats")
    assert response.status_code == 200
    assert response.json()["pending"] == 1


def test_get_stats_closed_increments_after_full_flow(api_app: Any):
    """Stats.closed deve incrementar após o ciclo abrir → pegar → fechar."""
    cria = request(api_app, "POST", "/tickets", {"usuario": "lucas", "descricao": "HD com defeito"})
    ticket_id = cria.json()["ticket_id"]
    request(api_app, "PATCH", "/tickets/next", {"tecnico": "tech_stats"})
    request(api_app, "PATCH", f"/tickets/{ticket_id}/close")

    stats = request(api_app, "GET", "/tickets/stats").json()
    assert stats["pending"] == 0
    assert stats["in_progress"] == 0
    assert stats["closed"] == 1


# ── GET /tickets/status/{status} ────────────────────────────────────────────

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


def test_get_status_closed_after_full_flow(api_app: Any):
    """GET /tickets/status/CLOSED deve retornar o ticket após fechar."""
    cria = request(api_app, "POST", "/tickets", {"usuario": "ana", "descricao": "Sem internet"})
    ticket_id = cria.json()["ticket_id"]
    request(api_app, "PATCH", "/tickets/next", {"tecnico": "tech_close"})
    request(api_app, "PATCH", f"/tickets/{ticket_id}/close")

    response = request(api_app, "GET", "/tickets/status/CLOSED")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["ticket_id"] == ticket_id
    assert data[0]["status"] == "CLOSED"
    assert "timestamp_fechamento" in data[0]


def test_get_status_invalid_returns_422(api_app: Any):
    response = request(api_app, "GET", "/tickets/status/INVALIDO")
    assert response.status_code == 422


# ── GET /tickets/{ticket_id} ────────────────────────────────────────────────

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


# ── Fluxo E2E: abrir → pegar → fechar ───────────────────────────────────────

def test_fluxo_completo_abrir_pegar_fechar(api_app: Any):
    """Exercita o ciclo de vida completo de um ticket via camada HTTP."""
    # 1. Abrir
    cria = request(api_app, "POST", "/tickets", {"usuario": "bia", "descricao": "Mouse com defeito"})
    assert cria.status_code == 201
    ticket_id = cria.json()["ticket_id"]
    assert cria.json()["status"] == "OPEN"

    # 2. Pegar
    pega = request(api_app, "PATCH", "/tickets/next", {"tecnico": "tech_e2e"})
    assert pega.status_code == 200
    assert pega.json()["ticket_id"] == ticket_id
    assert pega.json()["status"] == "IN_PROGRESS"
    assert pega.json()["tecnico"] == "tech_e2e"

    # 3. Fechar
    fecha = request(api_app, "PATCH", f"/tickets/{ticket_id}/close")
    assert fecha.status_code == 200
    assert fecha.json() == {"ticket_id": ticket_id, "status": "CLOSED"}

    # 4. Verificar estado final via GET by ID
    busca = request(api_app, "GET", f"/tickets/{ticket_id}")
    assert busca.status_code == 200
    assert busca.json()["status"] == "CLOSED"
    assert "timestamp_fechamento" in busca.json()

    # 5. Fila deve estar vazia
    stats = request(api_app, "GET", "/tickets/stats").json()
    assert stats == {"pending": 0, "in_progress": 0, "closed": 1}


def test_fluxo_nao_pode_fechar_ticket_aberto_diretamente(api_app: Any):
    """Ticket OPEN não pode ser fechado sem passar por IN_PROGRESS."""
    cria = request(api_app, "POST", "/tickets", {"usuario": "carlos", "descricao": "VPN caiu"})
    ticket_id = cria.json()["ticket_id"]

    fecha = request(api_app, "PATCH", f"/tickets/{ticket_id}/close")
    assert fecha.status_code == 400


# ── Exclusividade atômica via HTTP (dois AsyncClient simultâneos) ────────────

def test_exclusividade_atomica_via_http(api_app: Any):
    """Dois clientes HTTP concorrentes só podem atribuir um ticket ao mesmo tempo.

    Usa asyncio diretamente para disparar ambas as requisições de PATCH /next
    no mesmo event loop, maximizando a concorrência sem precisar de threads.
    """
    from app.services import ticket_service

    # Garante exatamente 1 ticket na fila
    ticket_service._fila.limpar_tudo()
    request(api_app, "POST", "/tickets", {"usuario": "gabi", "descricao": "Conta bloqueada"})

    async def dois_clientes_simultaneos():
        transport = httpx.ASGITransport(app=api_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c1, \
                   httpx.AsyncClient(transport=transport, base_url="http://testserver") as c2:
            r1, r2 = await asyncio.gather(
                c1.patch("/tickets/next", json={"tecnico": "tecnico-a"}),
                c2.patch("/tickets/next", json={"tecnico": "tecnico-b"}),
            )
        return r1, r2

    r1, r2 = asyncio.run(dois_clientes_simultaneos())

    status_codes = {r1.status_code, r2.status_code}
    # Um deve ser 200 (atribuído) e o outro 404 (fila vazia)
    assert status_codes == {200, 404}

    # O ticket atribuído deve ter tecnico correto
    sucesso = r1 if r1.status_code == 200 else r2
    assert sucesso.json()["status"] == "IN_PROGRESS"
    assert sucesso.json()["tecnico"] in {"tecnico-a", "tecnico-b"}


# ── SSE /events ─────────────────────────────────────────────────────────────
