import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.auth import require_admin
from backend.database.connection import db_connection

router = APIRouter(
    prefix="/api/automations",
    tags=["automations"]
)

AUTOMATIONS = {
    "welcome_messages": {
        "name": "Mensajes de bienvenida",
        "description": (
            "Envía mensajes privados a nuevos miembros. "
            "El registro de entradas continúa aunque se pause."
        )
    },
    "departure_messages": {
        "name": "Mensajes de despedida",
        "description": (
            "Envía mensajes privados a quienes abandonan "
            "el canal. El registro de salidas continúa."
        )
    },
    "daily_summary": {
        "name": "Resumen diario",
        "description": (
            "Genera y envía el informe diario de actividad."
        )
    }
}


class AutomationUpdate(BaseModel):
    enabled: bool


@router.get("")
def list_automations(
    admin: dict = Depends(require_admin)
):
    with db_connection() as conn:
        rows = conn.execute("""
            SELECT automation_key, enabled, settings_json, updated_at
            FROM automation_settings
            ORDER BY automation_key
        """).fetchall()

    result = []

    for row in rows:
        metadata = AUTOMATIONS.get(row["automation_key"])

        if metadata is None:
            continue

        result.append({
            "key": row["automation_key"],
            "name": metadata["name"],
            "description": metadata["description"],
            "enabled": bool(row["enabled"]),
            "updated_at": row["updated_at"]
        })

    return {"items": result, "count": len(result)}


@router.patch("/{automation_key}")
def update_automation(
    automation_key: str,
    payload: AutomationUpdate,
    admin: dict = Depends(require_admin)
):
    if automation_key not in AUTOMATIONS:
        raise HTTPException(
            status_code=404,
            detail="Automation not found"
        )

    with db_connection() as conn:

        current = conn.execute("""
            SELECT enabled
            FROM automation_settings
            WHERE automation_key = ?
        """, (automation_key,)).fetchone()

        if current is None:
            raise HTTPException(
                status_code=404,
                detail="Automation not found"
            )

        previous = bool(current["enabled"])
        new_value = payload.enabled

        conn.execute("""
            UPDATE automation_settings
            SET enabled = ?,
                updated_at = strftime(
                    '%Y-%m-%dT%H:%M:%fZ','now'
                )
            WHERE automation_key = ?
        """, (int(new_value), automation_key))

        if previous != new_value:
            action = "activated" if new_value else "paused"

            conn.execute("""
                INSERT INTO activity_logs (
                    category,
                    severity,
                    message,
                    details
                )
                VALUES (?, ?, ?, ?)
            """, (
                "automation",
                "INFO",
                f"Automation {automation_key} {action}",
                json.dumps({
                    "automation_key": automation_key,
                    "enabled": new_value
                })
            ))

        updated = conn.execute("""
            SELECT updated_at
            FROM automation_settings
            WHERE automation_key = ?
        """, (automation_key,)).fetchone()

    return {
        "success": True,
        "automation_key": automation_key,
        "enabled": new_value,
        "updated_at": updated["updated_at"]
    }
