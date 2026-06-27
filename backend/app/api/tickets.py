from fastapi import APIRouter, HTTPException, Query

from app.schemas.ticket_schema import TicketAssign, TicketCreate, TicketResponse, TicketStatsResponse
from app.services import ticket_service


router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", response_model=TicketResponse, status_code=201)
def criar_ticket(body: TicketCreate):
    return ticket_service.abrir_ticket(body.model_dump())


@router.get("", response_model=list[TicketResponse])
def listar_tickets():
    return ticket_service.listar_tickets()


@router.get("/stats", response_model=TicketStatsResponse)
def stats_tickets():
    """Retorna a contagem de chamados por status: pending, in_progress, closed."""
    return ticket_service.get_stats()


@router.get("/status/{status}", response_model=list[TicketResponse])
def listar_por_status(status: str):
    """Lista chamados filtrando pelo status: OPEN, IN_PROGRESS ou CLOSED."""
    status_validos = {"OPEN", "IN_PROGRESS", "CLOSED"}
    if status.upper() not in status_validos:
        raise HTTPException(
            status_code=422,
            detail=f"Status invalido. Use um de: {', '.join(sorted(status_validos))}",
        )
    return ticket_service.listar_por_status(status.upper())


@router.patch("/next", response_model=TicketResponse)
def pegar_proximo_ticket(body: TicketAssign):
    ticket = ticket_service.pegar_ticket(body.tecnico)
    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail="Nenhum ticket pendente na fila.",
        )
    return ticket


@router.patch("/{ticket_id}/close")
def fechar_ticket(ticket_id: str):
    sucesso = ticket_service.fechar_ticket(ticket_id)
    if not sucesso:
        raise HTTPException(
            status_code=400,
            detail="Ticket inexistente ou nao esta em atendimento.",
        )
    return {"ticket_id": ticket_id, "status": "CLOSED"}


@router.get("/{ticket_id}", response_model=TicketResponse)
def buscar_ticket(ticket_id: str):
    """Busca um chamado pelo ID, independentemente do status."""
    ticket = ticket_service.buscar_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket nao encontrado.")
    return ticket
