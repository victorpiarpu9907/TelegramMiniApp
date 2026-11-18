from fastapi import APIRouter, Depends, HTTPException

from backend.api.auth import require_admin

from backend.services.userbot_manager import (
    userbot_manager,
    UserbotNotConfiguredError,
    UserbotConnectionError
)


router = APIRouter(
    prefix="/api/userbot",
    tags=["userbot"]
)


@router.get("/status")
def get_userbot_status(
    admin: dict = Depends(require_admin)
):
    return userbot_manager.get_status()


@router.post("/start")
async def start_userbot(
    admin: dict = Depends(require_admin)
):
    try:
        return await userbot_manager.start()

    except UserbotNotConfiguredError:
        raise HTTPException(
            status_code=503,
            detail="Userbot credentials are not configured."
        )

    except UserbotConnectionError:
        raise HTTPException(
            status_code=502,
            detail="Could not connect the Telegram userbot."
        )


@router.post("/stop")
async def stop_userbot(
    admin: dict = Depends(require_admin)
):
    return await userbot_manager.stop()
