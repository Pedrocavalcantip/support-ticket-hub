from time import perf_counter

from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.tickets import router as tickets_router
from app.core.logging_config import get_logger


logger = get_logger(__name__)

app = FastAPI(title="Support Ticket Hub")

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


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}
