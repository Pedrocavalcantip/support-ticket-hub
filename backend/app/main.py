from fastapi import FastAPI

app = FastAPI(title="Vai ter ticket Hugo")

@app.get("/health")
async def health_check():
    return {"status": "ok"}