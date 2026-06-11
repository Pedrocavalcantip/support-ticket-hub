from fastapi import APIRouter, HTTPException

from app.schemas.ticket_schema import TicketAssign, TicketCreate, TicketResponse
from app.services import ticket_service


router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", response_model=TicketResponse, status_code=201)
def criar_ticket(body: TicketCreate):
    return ticket_service.abrir_ticket(body.model_dump())


@router.get("", response_model=list[TicketResponse])
def listar_tickets():
    return ticket_service.listar_tickets()


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
