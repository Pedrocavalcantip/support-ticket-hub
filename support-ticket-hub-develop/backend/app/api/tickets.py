from fastapi import APIRouter, HTTPException, Query
from app.schemas.ticket_schema import (
    AbrirTicketRequest, PegarTicketRequest, FecharTicketRequest,
    TicketResponse, FilaStatusResponse,
)
from app.services import ticket_service

router = APIRouter(prefix="/tickets", tags=["tickets"])

@router.post("", response_model=TicketResponse, status_code=201)
def abrir_ticket(body: AbrirTicketRequest):
    return ticket_service.abrir_ticket(body.usuario, body.descricao)

@router.post("/pegar", response_model=TicketResponse)
def pegar_ticket(body: PegarTicketRequest):
    ticket = ticket_service.pegar_ticket(body.tecnico_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Nenhum chamado aguardando na fila.")
    return ticket

@router.post("/{ticket_id}/fechar")
def fechar_ticket(ticket_id: str, body: FecharTicketRequest):
    sucesso = ticket_service.fechar_ticket(ticket_id, body.tecnico_id)
    if not sucesso:
        raise HTTPException(status_code=400, detail="Não foi possível fechar o chamado.")
    return {"mensagem": f"Chamado {ticket_id} fechado com sucesso."}

@router.get("", response_model=list[TicketResponse])
def listar_tickets(status: str = Query(default="aberto")):
    try:
        return ticket_service.listar_tickets(status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/fila/status", response_model=FilaStatusResponse)
def status_fila():
    return ticket_service.status_fila()