from fastapi import FastAPI

app = FastAPI(
    title="Telegram Control Center",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "application": "Telegram Control Center",
        "version": "0.1.0"
    }
