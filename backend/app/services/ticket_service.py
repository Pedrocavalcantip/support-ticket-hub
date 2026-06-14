from app.queue.redis_queue import FilaTickets
from app.core.config import settings

_fila = FilaTickets(host=settings.REDIS_HOST, port=settings.REDIS_PORT)


def abrir_ticket(ticket: dict) -> dict:
    return _fila.abrir(ticket)


def listar_tickets() -> list[dict]:
    return _fila.listar()


def pegar_ticket(tecnico: str) -> dict | None:
    return _fila.pegar(tecnico)


def fechar_ticket(ticket_id: str) -> bool:
    return _fila.fechar(ticket_id)
