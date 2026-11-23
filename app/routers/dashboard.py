import json
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, Query
from app.auth import get_current_tenant
from app.database import get_db

router = APIRouter(prefix="/api/v1/dashboard", tags=["Owner Analytics & Submissions"])

@router.get("/stats")
def get_dashboard_stats(
    current_tenant: Dict[str, Any] = Depends(get_current_tenant)
):
    tenant_id = current_tenant["id"]
    with get_db() as conn:
        cursor = conn.cursor()

        # Total widgets
        cursor.execute("SELECT COUNT(*) AS count FROM widgets WHERE tenant_id = ?", (tenant_id,))
        total_widgets = cursor.fetchone()["count"]

        # Total submissions
        cursor.execute("SELECT COUNT(*) AS count FROM submissions WHERE tenant_id = ?", (tenant_id,))
        total_submissions = cursor.fetchone()["count"]

        # Submissions last 24 hours
        cursor.execute(
            """
            SELECT COUNT(*) AS count FROM submissions
            WHERE tenant_id = ? AND datetime(created_at) >= datetime('now', '-1 day')
            """,
            (tenant_id,)
        )
        submissions_24h = cursor.fetchone()["count"]

        # Submissions last 7 days
        cursor.execute(
            """
            SELECT COUNT(*) AS count FROM submissions
            WHERE tenant_id = ? AND datetime(created_at) >= datetime('now', '-7 days')
            """,
            (tenant_id,)
        )
        submissions_7d = cursor.fetchone()["count"]

        # Counts by widget
        cursor.execute(
            """
            SELECT w.id, w.name, w.type, COUNT(s.id) as submission_count
            FROM widgets w
            LEFT JOIN submissions s ON s.widget_id = w.id
            WHERE w.tenant_id = ?
            GROUP BY w.id, w.name, w.type
            ORDER BY submission_count DESC
            """,
            (tenant_id,)
        )
        by_widget = [dict(row) for row in cursor.fetchall()]

        # Geographic distribution (top countries)
        cursor.execute(
            """
            SELECT COALESCE(geo_country, 'Unknown') as country, COUNT(*) as count
            FROM submissions
            WHERE tenant_id = ?
            GROUP BY country
            ORDER BY count DESC
            LIMIT 10
            """,
            (tenant_id,)
        )
        geo_distribution = [dict(row) for row in cursor.fetchall()]

    return {
        "tenant_id": tenant_id,
        "tenant_name": current_tenant["name"],
        "total_widgets": total_widgets,
        "total_submissions": total_submissions,
        "submissions_24h": submissions_24h,
        "submissions_7d": submissions_7d,
        "by_widget": by_widget,
        "geo_distribution": geo_distribution
    }

@router.get("/submissions")
def list_submissions(
    widget_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_tenant: Dict[str, Any] = Depends(get_current_tenant)
):
    tenant_id = current_tenant["id"]
    with get_db() as conn:
        cursor = conn.cursor()

        if widget_id:
            cursor.execute(
                """
                SELECT s.*, w.name as widget_name
                FROM submissions s
                JOIN widgets w ON s.widget_id = w.id
                WHERE s.tenant_id = ? AND s.widget_id = ?
                ORDER BY s.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (tenant_id, widget_id, limit, offset)
            )
        else:
            cursor.execute(
                """
                SELECT s.*, w.name as widget_name
                FROM submissions s
                JOIN widgets w ON s.widget_id = w.id
                WHERE s.tenant_id = ?
                ORDER BY s.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (tenant_id, limit, offset)
            )
        rows = cursor.fetchall()

    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "widget_id": r["widget_id"],
            "widget_name": r["widget_name"],
            "payload": json.loads(r["payload"]),
            "ip_address": r["ip_address"],
            "origin": r["origin"],
            "geo": {
                "country": r["geo_country"],
                "city": r["geo_city"],
                "region": r["geo_region"],
                "provider": r["geo_provider"]
            },
            "created_at": r["created_at"]
        })
    return {"items": results, "count": len(results), "offset": offset, "limit": limit}
