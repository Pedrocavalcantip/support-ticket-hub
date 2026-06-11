from app.queue.redis_queue import FilaTickets
from app.core.config import settings

_fila = FilaTickets(host=settings.REDIS_HOST, port=settings.REDIS_PORT)

def abrir_ticket(usuario: str, descricao: str) -> dict:
    return _fila.abrir_ticket(usuario, descricao)

def pegar_ticket(tecnico_id: str) -> dict | None:
    return _fila.pegar_ticket(tecnico_id)

def fechar_ticket(ticket_id: str, tecnico_id: str) -> bool:
    return _fila.fechar_ticket(ticket_id, tecnico_id)

def listar_tickets(status: str = "aberto") -> list[dict]:
    return _fila.listar_tickets(status)

def status_fila() -> dict:
    tamanho = _fila.tamanho_fila()
    return {"tamanho": tamanho, "mensagem": f"{tamanho} chamado(s) aguardando."}