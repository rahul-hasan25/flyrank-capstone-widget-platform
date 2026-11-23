from fastapi import Header, HTTPException, status, Security
from fastapi.security import APIKeyHeader
from typing import Optional, Dict, Any
from app.database import get_db

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def get_current_tenant(
    x_api_key: Optional[str] = Security(api_key_header),
    authorization: Optional[str] = Header(None)
) -> Dict[str, Any]:
    token = None
    if x_api_key:
        token = x_api_key.strip()
    elif authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1].strip()
        else:
            token = authorization.strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Missing authentication credentials. Provide X-API-Key or Bearer token.", "code": "UNAUTHORIZED"}
        )

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, api_key, created_at FROM tenants WHERE api_key = ?", (token,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "Invalid API key.", "code": "INVALID_API_KEY"}
            )
        return dict(row)
