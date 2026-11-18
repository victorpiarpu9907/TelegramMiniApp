from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

import json

from backend.api.auth import require_admin
from backend.database.connection import db_connection


router = APIRouter(
    prefix="/api/channel",
    tags=["channel"]
)


class ChannelConfigUpdate(BaseModel):

    telegram_channel_id: int = Field(lt=0)
    title: str | None = Field(default=None, max_length=255)
    enabled: bool = True

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value):

        if value is None:
            return None

        value = value.strip()

        return value or None


class TrackingUpdate(BaseModel):
    enabled: bool


@router.get("")
def read_channel_config(
    admin: dict = Depends(require_admin)
):

    with db_connection() as conn:

        channel = conn.execute("""
            SELECT
                telegram_channel_id,
                title,
                enabled,
                updated_at
            FROM monitored_channel
            WHERE id = 1
        """).fetchone()

        if channel is None:
            raise HTTPException(
                status_code=500,
                detail="Channel configuration unavailable"
            )

        channel_id = channel["telegram_channel_id"]

        cursor = None

        if channel_id is not None:

            cursor = conn.execute("""
                SELECT
                    last_event_id,
                    history_backfill_completed,
                    last_sync_at
                FROM event_cursors
                WHERE channel_id = ?
            """, (channel_id,)).fetchone()

        runtime = conn.execute("""
            SELECT status, last_heartbeat_at
            FROM system_runtime
            WHERE component = 'event_collector'
        """).fetchone()

    configured = channel_id is not None

    return {
        "configured": configured,
        "channel": {
            "telegram_channel_id": channel_id,
            "title": channel["title"],
            "enabled": bool(channel["enabled"]),
            "updated_at": channel["updated_at"]
        },
        "collector": {
            "status": runtime["status"] if runtime else "not_configured",
            "last_heartbeat_at": (
                runtime["last_heartbeat_at"] if runtime else None
            )
        },
        "history": {
            "backfill_completed": (
                bool(cursor["history_backfill_completed"])
                if cursor else False
            ),
            "last_event_id": (
                cursor["last_event_id"] if cursor else 0
            ),
            "last_sync_at": (
                cursor["last_sync_at"] if cursor else None
            )
        },
        "telegram_validation": (
            "pending" if configured else "not_configured"
        )
    }


@router.put("")
def set_channel_config(
    payload: ChannelConfigUpdate,
    admin: dict = Depends(require_admin)
):

    with db_connection() as conn:

        current = conn.execute("""
            SELECT telegram_channel_id, title, enabled
            FROM monitored_channel
            WHERE id = 1
        """).fetchone()

        previous = (
            dict(current) if current else None
        )

        conn.execute("""
            INSERT INTO monitored_channel (
                id,
                telegram_channel_id,
                title,
                enabled,
                updated_at
            )
            VALUES (
                1, ?, ?, ?,
                strftime('%Y-%m-%dT%H:%M:%fZ','now')
            )

            ON CONFLICT(id) DO UPDATE SET
                telegram_channel_id = excluded.telegram_channel_id,
                title = excluded.title,
                enabled = excluded.enabled,
                updated_at = excluded.updated_at
        """, (
            payload.telegram_channel_id,
            payload.title,
            int(payload.enabled)
        ))

        changed = (
            previous is None
            or previous["telegram_channel_id"] != payload.telegram_channel_id
            or previous["title"] != payload.title
            or bool(previous["enabled"]) != payload.enabled
        )

        if changed:

            conn.execute("""
                INSERT INTO activity_logs (
                    category,
                    severity,
                    message,
                    details
                )
                VALUES (?, ?, ?, ?)
            """, (
                "channel",
                "INFO",
                "Monitored channel configuration updated",
                json.dumps({
                    "channel_id": payload.telegram_channel_id,
                    "title": payload.title,
                    "enabled": payload.enabled
                })
            ))

    return {
        "success": True,
        "message": "Channel configuration saved",
        "channel": {
            "telegram_channel_id": payload.telegram_channel_id,
            "title": payload.title,
            "enabled": payload.enabled
        },
        "telegram_validation": "pending"
    }


@router.patch("/tracking")
def update_tracking(
    payload: TrackingUpdate,
    admin: dict = Depends(require_admin)
):

    with db_connection() as conn:

        channel = conn.execute("""
            SELECT telegram_channel_id, enabled
            FROM monitored_channel
            WHERE id = 1
        """).fetchone()

        if (
            channel is None
            or channel["telegram_channel_id"] is None
        ):
            raise HTTPException(
                status_code=409,
                detail="Configure a channel before changing tracking."
            )

        previous = bool(channel["enabled"])

        conn.execute("""
            UPDATE monitored_channel
            SET enabled = ?,
                updated_at = strftime(
                    '%Y-%m-%dT%H:%M:%fZ','now'
                )
            WHERE id = 1
        """, (int(payload.enabled),))

        if previous != payload.enabled:

            action = (
                "activated" if payload.enabled else "paused"
            )

            conn.execute("""
                INSERT INTO activity_logs (
                    category,
                    severity,
                    message,
                    details
                )
                VALUES (?, ?, ?, ?)
            """, (
                "channel",
                "INFO",
                f"Channel tracking {action}",
                json.dumps({
                    "channel_id": channel["telegram_channel_id"],
                    "enabled": payload.enabled
                })
            ))

    return {
        "success": True,
        "tracking_enabled": payload.enabled,
        "message": (
            "Channel tracking activated"
            if payload.enabled
            else "Channel tracking paused"
        )
    }
