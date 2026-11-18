from fastapi import APIRouter, Depends, Query

from backend.api.auth import require_admin
from backend.database.connection import db_connection

router = APIRouter(
    prefix="/api/dashboard",
    tags=["dashboard"]
)


def get_runtime_status(conn, component):

    row = conn.execute("""
        SELECT status, last_heartbeat_at
        FROM system_runtime
        WHERE component = ?
    """, (component,)).fetchone()

    if row is None:
        return "not_configured"

    status = row["status"]

    if status in ("running", "reconnecting"):

        heartbeat = row["last_heartbeat_at"]

        if not heartbeat:
            return "offline"

        fresh = conn.execute("""
            SELECT CASE
                WHEN julianday(?) >= julianday('now', '-90 seconds')
                THEN 1 ELSE 0
            END
        """, (heartbeat,)).fetchone()[0]

        if not fresh:
            return "offline"

    return status


@router.get("/summary")
def get_dashboard_summary(
    admin: dict = Depends(require_admin)
):

    with db_connection() as conn:

        channel = conn.execute("""
            SELECT telegram_channel_id, title, enabled
            FROM monitored_channel
            WHERE id = 1
        """).fetchone()

        userbot_status = get_runtime_status(
            conn, "userbot"
        )

        collector_status = get_runtime_status(
            conn, "event_collector"
        )

        channel_id = (
            channel["telegram_channel_id"]
            if channel else None
        )

        if channel_id is not None:

            metrics = conn.execute("""
                SELECT
                    COALESCE(SUM(
                        CASE WHEN event_type = 'entry'
                        THEN 1 ELSE 0 END
                    ), 0) AS entries,

                    COALESCE(SUM(
                        CASE WHEN event_type = 'exit'
                        THEN 1 ELSE 0 END
                    ), 0) AS exits

                FROM channel_events
                WHERE channel_id = ?
                  AND date(event_at) = date('now')
            """, (channel_id,)).fetchone()

            trend_rows = conn.execute("""
                SELECT
                    date(event_at) AS day,

                    SUM(CASE WHEN event_type = 'entry'
                        THEN 1 ELSE 0 END) AS entries,

                    SUM(CASE WHEN event_type = 'exit'
                        THEN 1 ELSE 0 END) AS exits

                FROM channel_events
                WHERE channel_id = ?
                  AND date(event_at) >= date('now', '-6 days')
                GROUP BY date(event_at)
                ORDER BY day ASC
            """, (channel_id,)).fetchall()

        else:
            metrics = {"entries": 0, "exits": 0}
            trend_rows = []

        recent = conn.execute("""
            SELECT id, category, severity, message, created_at
            FROM activity_logs
            ORDER BY id DESC
            LIMIT 5
        """).fetchall()

        entries = int(metrics["entries"])
        exits = int(metrics["exits"])

        channel_configured = channel_id is not None

        if not channel_configured:
            tracking_status = "not_configured"
        elif not channel["enabled"]:
            tracking_status = "paused"
        elif collector_status == "running":
            tracking_status = "active"
        elif collector_status == "error":
            tracking_status = "error"
        else:
            tracking_status = "waiting_for_userbot"

        return {
            "userbot": {
                "status": userbot_status
            },
            "event_collector": {
                "status": collector_status
            },
            "channel": {
                "configured": channel_configured,
                "telegram_channel_id": channel_id,
                "title": channel["title"] if channel else None,
                "enabled": bool(channel["enabled"]) if channel else False
            },
            "tracking_status": tracking_status,
            "metrics": {
                "current_members": None,
                "entries_today": entries,
                "exits_today": exits,
                "net_change_today": entries - exits
            },
            "trend_7_days": [
                {
                    "date": row["day"],
                    "entries": row["entries"],
                    "exits": row["exits"]
                }
                for row in trend_rows
            ],
            "recent_activity": [
                dict(row) for row in recent
            ]
        }


@router.get("/activity")
def get_recent_activity(
    limit: int = Query(default=20, ge=1, le=100),
    admin: dict = Depends(require_admin)
):

    with db_connection() as conn:

        rows = conn.execute("""
            SELECT id, category, severity, message, created_at
            FROM activity_logs
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

    return {
        "items": [dict(row) for row in rows],
        "count": len(rows)
    }
