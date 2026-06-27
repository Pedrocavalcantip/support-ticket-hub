import asyncio
from contextlib import asynccontextmanager
from time import perf_counter
from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from app.api.events import router as events_router
from app.api.tickets import router as tickets_router
from app.core.broadcaster import broadcaster
from app.core.logging_config import get_logger


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Registra o event loop para que código síncrono (ticket_service) possa
    # publicar eventos SSE de forma thread-safe via call_soon_threadsafe.
    broadcaster._set_loop(asyncio.get_event_loop())
    yield


app = FastAPI(title="Support Ticket Hub", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_http_request(request: Request, call_next):
    started_at = perf_counter()
    client_ip = request.client.host if request.client else "unknown"

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        logger.exception(
            "http_request_failed",
            extra={
                "method": request.method,
                "route": request.url.path,
                "client_ip": client_ip,
                "status_code": 500,
                "duration_ms": duration_ms,
            },
        )
        raise

    duration_ms = round((perf_counter() - started_at) * 1000, 2)
    matched_route = request.scope.get("route")
    route = getattr(matched_route, "path", request.url.path)
    logger.info(
        "http_request",
        extra={
            "method": request.method,
            "route": route,
            "client_ip": client_ip,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


app.include_router(tickets_router)
app.include_router(events_router)


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}
