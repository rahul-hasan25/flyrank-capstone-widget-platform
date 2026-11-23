import json
import uuid
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from app.auth import get_current_tenant
from app.config import settings
from app.database import get_db
from app.schemas import WidgetCreate, WidgetUpdate, WidgetResponse

router = APIRouter(prefix="/api/v1/admin", tags=["Widget Management (Admin)"])

def generate_embed_snippet(widget_id: str) -> str:
    base = settings.BASE_URL.rstrip("/")
    return f'<script src="{base}/static/widget.v1.js?id={widget_id}" async defer></script>'

@router.post("/widgets", response_model=WidgetResponse, status_code=status.HTTP_201_CREATED)
def create_widget(
    payload: WidgetCreate,
    current_tenant: Dict[str, Any] = Depends(get_current_tenant)
):
    widget_id = f"wgt_{uuid.uuid4().hex[:12]}"
    tenant_id = current_tenant["id"]
    fields_json = json.dumps([f.model_dump() for f in payload.fields])
    display_json = json.dumps(payload.display_options.model_dump())

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO widgets (
                id, tenant_id, name, type, title, description,
                fields_schema, button_text, display_options, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                widget_id, tenant_id, payload.name, payload.type, payload.title,
                payload.description or "", fields_json, payload.button_text, display_json
            )
        )
        cursor.execute("SELECT * FROM widgets WHERE id = ?", (widget_id,))
        row = cursor.fetchone()

    snippet = generate_embed_snippet(widget_id)
    return WidgetResponse(
        id=row["id"],
        tenant_id=row["tenant_id"],
        name=row["name"],
        type=row["type"],
        title=row["title"],
        description=row["description"],
        fields=json.loads(row["fields_schema"]),
        button_text=row["button_text"],
        display_options=json.loads(row["display_options"]),
        is_active=bool(row["is_active"]),
        embed_snippet=snippet,
        created_at=row["created_at"],
        updated_at=row["updated_at"]
    )

@router.get("/widgets", response_model=List[WidgetResponse])
def list_widgets(
    current_tenant: Dict[str, Any] = Depends(get_current_tenant)
):
    tenant_id = current_tenant["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM widgets WHERE tenant_id = ? ORDER BY created_at DESC",
            (tenant_id,)
        )
        rows = cursor.fetchall()

    results = []
    for r in rows:
        snippet = generate_embed_snippet(r["id"])
        results.append(WidgetResponse(
            id=r["id"],
            tenant_id=r["tenant_id"],
            name=r["name"],
            type=r["type"],
            title=r["title"],
            description=r["description"],
            fields=json.loads(r["fields_schema"]),
            button_text=r["button_text"],
            display_options=json.loads(r["display_options"]),
            is_active=bool(r["is_active"]),
            embed_snippet=snippet,
            created_at=r["created_at"],
            updated_at=r["updated_at"]
        ))
    return results

@router.get("/widgets/{widget_id}", response_model=WidgetResponse)
def get_widget(
    widget_id: str,
    current_tenant: Dict[str, Any] = Depends(get_current_tenant)
):
    tenant_id = current_tenant["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM widgets WHERE id = ? AND tenant_id = ?",
            (widget_id, tenant_id)
        )
        row = cursor.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Widget not found or unauthorized.", "code": "WIDGET_NOT_FOUND"}
        )

    return WidgetResponse(
        id=row["id"],
        tenant_id=row["tenant_id"],
        name=row["name"],
        type=row["type"],
        title=row["title"],
        description=row["description"],
        fields=json.loads(row["fields_schema"]),
        button_text=row["button_text"],
        display_options=json.loads(row["display_options"]),
        is_active=bool(row["is_active"]),
        embed_snippet=generate_embed_snippet(row["id"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"]
    )

@router.put("/widgets/{widget_id}", response_model=WidgetResponse)
def update_widget(
    widget_id: str,
    payload: WidgetUpdate,
    current_tenant: Dict[str, Any] = Depends(get_current_tenant)
):
    tenant_id = current_tenant["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM widgets WHERE id = ? AND tenant_id = ?",
            (widget_id, tenant_id)
        )
        existing = cursor.fetchone()
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Widget not found or unauthorized.", "code": "WIDGET_NOT_FOUND"}
            )

        new_name = payload.name if payload.name is not None else existing["name"]
        new_type = payload.type if payload.type is not None else existing["type"]
        new_title = payload.title if payload.title is not None else existing["title"]
        new_desc = payload.description if payload.description is not None else existing["description"]
        new_fields = json.dumps([f.model_dump() for f in payload.fields]) if payload.fields is not None else existing["fields_schema"]
        new_btn = payload.button_text if payload.button_text is not None else existing["button_text"]
        new_disp = json.dumps(payload.display_options.model_dump()) if payload.display_options is not None else existing["display_options"]
        new_active = int(payload.is_active) if payload.is_active is not None else existing["is_active"]

        cursor.execute(
            """
            UPDATE widgets SET
                name = ?, type = ?, title = ?, description = ?,
                fields_schema = ?, button_text = ?, display_options = ?,
                is_active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
            """,
            (new_name, new_type, new_title, new_desc, new_fields, new_btn, new_disp, new_active, widget_id, tenant_id)
        )
        cursor.execute("SELECT * FROM widgets WHERE id = ?", (widget_id,))
        updated = cursor.fetchone()

    return WidgetResponse(
        id=updated["id"],
        tenant_id=updated["tenant_id"],
        name=updated["name"],
        type=updated["type"],
        title=updated["title"],
        description=updated["description"],
        fields=json.loads(updated["fields_schema"]),
        button_text=updated["button_text"],
        display_options=json.loads(updated["display_options"]),
        is_active=bool(updated["is_active"]),
        embed_snippet=generate_embed_snippet(updated["id"]),
        created_at=updated["created_at"],
        updated_at=updated["updated_at"]
    )

@router.delete("/widgets/{widget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_widget(
    widget_id: str,
    current_tenant: Dict[str, Any] = Depends(get_current_tenant)
):
    tenant_id = current_tenant["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM widgets WHERE id = ? AND tenant_id = ?",
            (widget_id, tenant_id)
        )
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Widget not found or unauthorized.", "code": "WIDGET_NOT_FOUND"}
            )
        cursor.execute("DELETE FROM widgets WHERE id = ? AND tenant_id = ?", (widget_id, tenant_id))
    return None

@router.get("/widgets/{widget_id}/snippet")
def get_snippet(
    widget_id: str,
    current_tenant: Dict[str, Any] = Depends(get_current_tenant)
):
    tenant_id = current_tenant["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM widgets WHERE id = ? AND tenant_id = ?", (widget_id, tenant_id))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Widget not found.", "code": "WIDGET_NOT_FOUND"}
            )
    return {"snippet": generate_embed_snippet(widget_id)}
