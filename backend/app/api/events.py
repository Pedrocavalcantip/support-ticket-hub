import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core.broadcaster import broadcaster
from app.core.logging_config import get_logger


logger = get_logger(__name__)
router = APIRouter(tags=["events"])

_KEEPALIVE_TIMEOUT = 20  # segundos sem evento → envia comentário de keepalive


async def _event_generator(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    logger.info("[SSE CONNECTED]", extra={"client_ip": client_ip})
    q = broadcaster.subscribe()
    try:
        while True:
            try:
                payload = await asyncio.wait_for(q.get(), timeout=_KEEPALIVE_TIMEOUT)
                yield f"data: {payload}\n\n"
            except asyncio.TimeoutError:
                # Mantém a conexão viva para proxies e navegadores que fecham
                # conexões ociosas; comentários SSE são ignorados pelo cliente.
                yield ": keepalive\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        broadcaster.unsubscribe(q)
        logger.info("[SSE DISCONNECTED]", extra={"client_ip": client_ip})


@router.get("/events", summary="Stream de eventos SSE")
async def sse_endpoint(request: Request):
    return StreamingResponse(
        _event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # desativa buffer do nginx
        },
    )
