import json
import uuid
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, Response, BackgroundTasks, HTTPException, Header, status
from app.config import settings
from app.database import get_db
from app.rate_limiter import rate_limiter
from app.geo_service import geo_service
from app.side_effects import execute_submission_side_effects
from app.schemas import PublicWidgetConfig, SubmissionResult

router = APIRouter(prefix="/api/v1/public", tags=["Public Widget Delivery & Submissions"])

@router.options("/submissions")
def preflight_submissions():
    """Explicit preflight handler for cross-origin submissions"""
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = (
        "Content-Type, Idempotency-Key, X-Mock-Provider-A, X-Mock-Provider-B, X-Mock-Side-Effect"
    )
    response.headers["Access-Control-Max-Age"] = "86400"
    return response

@router.get("/widgets/{widget_id}/config", response_model=PublicWidgetConfig)
def get_public_widget_config(widget_id: str, response: Response):
    """
    Public config endpoint.
    Serves cached, lightweight widget configuration for client-side rendering.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, type, title, description, fields_schema, button_text, display_options, is_active FROM widgets WHERE id = ?",
            (widget_id,)
        )
        row = cursor.fetchone()

    if not row or not row["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Widget not found or inactive.", "code": "WIDGET_NOT_FOUND"}
        )

    # Set cache headers and CORS
    response.headers["Cache-Control"] = "public, max-age=60"
    response.headers["Access-Control-Allow-Origin"] = "*"

    base = settings.BASE_URL.rstrip("/")
    return PublicWidgetConfig(
        id=row["id"],
        type=row["type"],
        title=row["title"],
        description=row["description"] or "",
        fields=json.loads(row["fields_schema"]),
        button_text=row["button_text"],
        display_options=json.loads(row["display_options"]),
        submission_url=f"{base}/api/v1/public/submissions"
    )

@router.post("/submissions", response_model=SubmissionResult, status_code=status.HTTP_201_CREATED)
async def submit_public_lead(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    x_mock_provider_a: Optional[str] = Header(None, alias="X-Mock-Provider-A"),
    x_mock_provider_b: Optional[str] = Header(None, alias="X-Mock-Provider-B"),
    x_mock_side_effect: Optional[str] = Header(None, alias="X-Mock-Side-Effect")
):
    """
    Hardened public submission endpoint:
    - Cross-origin enabled
    - Payload size limit checked
    - Malformed payload rejected with clean 4xx
    - Honeypot spam protection
    - Rate limiting per IP
    - Fallback geo enrichment (A -> B -> degrade)
    - Safe background side effect (never breaks response)
    - Idempotency support
    """
    response.headers["Access-Control-Allow-Origin"] = "*"

    # 1. Payload size check (prevent memory exhaustion attacks)
    raw_body = await request.body()
    if len(raw_body) > settings.MAX_PAYLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"error": f"Payload size exceeds maximum limit of {settings.MAX_PAYLOAD_SIZE_BYTES} bytes.", "code": "PAYLOAD_TOO_LARGE"}
        )

    # 2. Parse JSON safely (prevent 500 on malformed input)
    try:
        data = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Malformed JSON payload in request body.", "code": "INVALID_JSON"}
        )

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Request body must be a JSON object.", "code": "INVALID_PAYLOAD_TYPE"}
        )

    widget_id = data.get("widget_id")
    if not widget_id or not isinstance(widget_id, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Field 'widget_id' is required.", "code": "MISSING_WIDGET_ID"}
        )

    submission_data = data.get("data")
    if not isinstance(submission_data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Field 'data' must be an object containing form values.", "code": "INVALID_DATA_FIELD"}
        )

    # 3. Honeypot Anti-Spam Check
    # Bots automatically fill invisible fields. Real users leave them empty.
    trap_value = data.get("_hp_trap") or data.get("_hp_website") or submission_data.get("_hp_trap") or submission_data.get("_hp_website")
    if trap_value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Spam submission rejected by security filter.", "code": "SPAM_REJECTED"}
        )

    # 4. Rate Limiting Check
    client_ip = rate_limiter.get_client_ip(request)
    rate_limiter.check(f"ip:{client_ip}")

    # 5. Retrieve Widget and Validate Against Tenant & Schema
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, tenant_id, fields_schema, is_active FROM widgets WHERE id = ?", (widget_id,))
        widget_row = cursor.fetchone()

    if not widget_row or not widget_row["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Widget not found or inactive.", "code": "WIDGET_NOT_FOUND"}
        )

    tenant_id = widget_row["tenant_id"]
    fields_schema = json.loads(widget_row["fields_schema"])

    # Validate required fields
    for field in fields_schema:
        field_name = field.get("name")
        if field.get("required") and (field_name not in submission_data or not str(submission_data[field_name]).strip()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": f"Required field '{field_name}' is missing.", "code": "MISSING_REQUIRED_FIELD"}
            )

    # 6. Idempotency Check
    if idempotency_key:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, geo_country, geo_city, geo_region, geo_provider FROM submissions WHERE widget_id = ? AND idempotency_key = ?",
                (widget_id, idempotency_key)
            )
            existing = cursor.fetchone()
            if existing:
                response.status_code = status.HTTP_200_OK
                return SubmissionResult(
                    status="success",
                    submission_id=existing["id"],
                    message="Submission already recorded (idempotent replay).",
                    enriched=bool(existing["geo_country"]),
                    geo={
                        "country": existing["geo_country"],
                        "city": existing["geo_city"],
                        "region": existing["geo_region"],
                        "provider": existing["geo_provider"]
                    }
                )

    # 7. Geo Enrichment with Fallback Chain
    geo = await geo_service.enrich_ip(
        ip=client_ip,
        mock_a=x_mock_provider_a,
        mock_b=x_mock_provider_b
    )

    # 8. Store Submission
    submission_id = f"sub_{uuid.uuid4().hex[:12]}"
    user_agent = request.headers.get("User-Agent", "")
    origin = request.headers.get("Origin", "")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO submissions (
                id, widget_id, tenant_id, payload, ip_address,
                user_agent, origin, geo_country, geo_city,
                geo_region, geo_provider, idempotency_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                submission_id, widget_id, tenant_id, json.dumps(submission_data),
                client_ip, user_agent, origin, geo.country, geo.city,
                geo.region, geo.provider, idempotency_key
            )
        )

    # 9. Trigger Safe Side Effects (Non-blocking background task)
    simulate_fail = (x_mock_side_effect == "fail")
    background_tasks.add_task(
        execute_submission_side_effects,
        submission_id=submission_id,
        widget_id=widget_id,
        payload=submission_data,
        simulate_failure=simulate_fail
    )

    return SubmissionResult(
        status="success",
        submission_id=submission_id,
        message="Submission accepted and stored successfully.",
        enriched=geo.is_enriched,
        geo={
            "country": geo.country,
            "city": geo.city,
            "region": geo.region,
            "provider": geo.provider
        }
    )
