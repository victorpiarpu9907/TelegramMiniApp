from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import (
    APP_NAME,
    APP_VERSION,
    CORS_ORIGINS
)

from backend.database.schema import init_db

from backend.api.health import router as health_router
from backend.api.auth import router as auth_router
from backend.api.dashboard import router as dashboard_router
from backend.api.statistics import router as statistics_router
from backend.api.automations import router as automations_router
from backend.api.userbot import router as userbot_router
from backend.api.channel import router as channel_router

from backend.services.userbot_manager import userbot_manager


@asynccontextmanager
async def lifespan(app: FastAPI):

    init_db()
    userbot_manager.initialize()

    try:
        yield
    finally:
        await userbot_manager.stop()


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"]
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(statistics_router)
app.include_router(automations_router)
app.include_router(userbot_router)
app.include_router(channel_router)
