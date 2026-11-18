from fastapi import APIRouter, HTTPException

from backend.database.connection import db_connection

router = APIRouter()


@router.get("/health")
def health():
    try:
        with db_connection() as conn:
            conn.execute("SELECT 1").fetchone()

        return {
            "status": "ok",
            "application": "Telegram Control Center",
            "database": "connected"
        }

    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable"
        )
