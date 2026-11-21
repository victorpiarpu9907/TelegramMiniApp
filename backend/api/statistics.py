"""Estadisticas historicas del canal principal, en UTC.

Solo se utilizan eventos registrados por el recolector. No se infiere
el numero total de miembros a partir de entradas y salidas.
"""

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query

from backend.api.auth import require_admin
from backend.database.connection import db_connection


router = APIRouter(prefix="/api/statistics", tags=["statistics"])


def _utc_start(day):
    return day.isoformat() + "T00:00:00Z"


@router.get("/summary")
def get_statistics_summary(
    days: Literal[7, 30, 90] = Query(default=7),
    admin: dict = Depends(require_admin),
):
    """Resumen por canal y periodo. Cada día sin eventos se rellena con cero."""

    # Funciona con los eventos UTC que almacena EventCollector.
    today = datetime.now(timezone.utc).date()
    start_day = today - timedelta(days=days - 1)
    previous_start = start_day - timedelta(days=days)

    start_utc = _utc_start(start_day)
    end_utc = _utc_start(today + timedelta(days=1))
    previous_start_utc = _utc_start(previous_start)

    with db_connection() as conn:
        configured_channel = conn.execute(
            """
            SELECT telegram_channel_id, title, enabled
            FROM monitored_channel
            WHERE id = 1
            """
        ).fetchone()

        channel_id = (
            configured_channel["telegram_channel_id"]
            if configured_channel else None
        )

        runtime = conn.execute(
            """
            SELECT status FROM system_runtime
            WHERE component = 'event_collector'
            """
        ).fetchone()

        collector_status = runtime["status"] if runtime else "not_configured"
        cursor = None
        daily_rows = []
        recent_rows = []
        previous_entries = 0
        previous_exits = 0

        if channel_id is not None:
            cursor = conn.execute(
                """
                SELECT last_sync_at, history_backfill_completed
                FROM event_cursors WHERE channel_id = ?
                """, (channel_id,)
            ).fetchone()

            daily_rows = conn.execute(
                """
                SELECT substr(event_at, 1, 10) AS day,
                       SUM(CASE WHEN event_type = 'entry' THEN 1 ELSE 0 END) AS entries,
                       SUM(CASE WHEN event_type = 'exit' THEN 1 ELSE 0 END) AS exits
                FROM channel_events
                WHERE channel_id = ? AND event_at >= ? AND event_at < ?
                GROUP BY substr(event_at, 1, 10)
                ORDER BY day
                """, (channel_id, start_utc, end_utc)
            ).fetchall()

            previous = conn.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN event_type = 'entry' THEN 1 ELSE 0 END), 0) AS entries,
                    COALESCE(SUM(CASE WHEN event_type = 'exit' THEN 1 ELSE 0 END), 0) AS exits
                FROM channel_events
                WHERE channel_id = ? AND event_at >= ? AND event_at < ?
                """, (channel_id, previous_start_utc, start_utc)
            ).fetchone()

            previous_entries = int(previous["entries"])
            previous_exits = int(previous["exits"])

            recent_rows = conn.execute(
                """
                SELECT telegram_event_id, event_type, telegram_user_id,
                       first_name, username, event_at
                FROM channel_events
                WHERE channel_id = ? AND event_at >= ? AND event_at < ?
                ORDER BY event_at DESC, id DESC
                LIMIT 15
                """, (channel_id, start_utc, end_utc)
            ).fetchall()

    by_day = {
        row["day"]: (int(row["entries"]), int(row["exits"]))
        for row in daily_rows
    }

    daily = []
    for offset in range(days):
        current_day = start_day + timedelta(days=offset)
        entries, exits = by_day.get(current_day.isoformat(), (0, 0))
        daily.append({
            "date": current_day.isoformat(),
            "entries": entries,
            "exits": exits,
            "net": entries - exits,
        })

    entries = sum(day["entries"] for day in daily)
    exits = sum(day["exits"] for day in daily)
    prev_net = previous_entries - previous_exits

    return {
        "period": {
            "days": days,
            "start_date": start_day.isoformat(),
            "end_date": today.isoformat(),
            "timezone": "UTC",
        },
        "channel": {
            "configured": channel_id is not None,
            "telegram_channel_id": channel_id,
            "title": configured_channel["title"] if configured_channel else None,
            "tracking_enabled": (
                bool(configured_channel["enabled"])
                if configured_channel and channel_id is not None else False
            ),
        },
        "metrics": {
            "entries": entries,
            "exits": exits,
            "net": entries - exits,
            "total_events": entries + exits,
            "active_days": sum(
                1 for day in daily if day["entries"] or day["exits"]
            ),
        },
        "comparison": {
            "previous_entries": previous_entries,
            "previous_exits": previous_exits,
            "previous_net": prev_net,
            "entries_difference": entries - previous_entries,
            "exits_difference": exits - previous_exits,
            "net_difference": entries - exits - prev_net,
        },
        "coverage": {
            "collector_status": collector_status,
            "history_backfill_completed": (
                bool(cursor["history_backfill_completed"]) if cursor else False
            ),
            "last_sync_at": cursor["last_sync_at"] if cursor else None,
            "members_count": None,
        },
        "daily": daily,
        "recent_events": [dict(row) for row in recent_rows],
    }
