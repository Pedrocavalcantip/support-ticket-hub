from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.tickets import router as tickets_router

app = FastAPI(title="Support Ticket Hub")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tickets_router)

@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}
