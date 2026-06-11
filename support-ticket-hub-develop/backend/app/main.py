from fastapi import FastAPI
from app.api.tickets import router as tickets_router

app = FastAPI(title="Support Ticket Hub")

app.include_router(tickets_router)

@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}