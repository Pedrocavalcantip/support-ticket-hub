from app.core.config import settings
from app.core.logging_config import get_logger
from app.queue.redis_queue import FilaTickets


logger = get_logger(__name__)
_fila = FilaTickets(host=settings.REDIS_HOST, port=settings.REDIS_PORT)


def abrir_ticket(ticket: dict) -> dict:
    ticket_criado = _fila.abrir(ticket)
    logger.info(
        "ticket_created",
        extra={
            "ticket_id": ticket_criado["ticket_id"],
            "usuario": ticket_criado["usuario"],
        },
    )
    return ticket_criado


def listar_tickets() -> list[dict]:
    return _fila.listar()


def pegar_ticket(tecnico: str) -> dict | None:
    ticket = _fila.pegar(tecnico)
    if ticket is None:
        logger.warning("empty_queue", extra={"tecnico": tecnico})
        return None

    logger.info(
        "ticket_assigned",
        extra={
            "ticket_id": ticket["ticket_id"],
            "tecnico": tecnico,
        },
    )
    return ticket


def fechar_ticket(ticket_id: str) -> bool:
    sucesso = _fila.fechar(ticket_id)
    if not sucesso:
        logger.warning("invalid_ticket_close", extra={"ticket_id": ticket_id})
        return False

    logger.info("ticket_closed", extra={"ticket_id": ticket_id})
    return True
