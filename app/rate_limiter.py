import time
import threading
from typing import Dict, List, Optional
from fastapi import Request, HTTPException, status
from app.config import settings

class InMemoryRateLimiter:
    def __init__(self):
        self._records: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def get_client_ip(self, request: Request) -> str:
        # Check standard reverse proxy headers
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        if request.client and request.client.host:
            return request.client.host
        return "127.0.0.1"

    def check(
        self,
        key: str,
        max_requests: Optional[int] = None,
        window_seconds: Optional[int] = None
    ) -> None:
        limit = max_requests or settings.RATE_LIMIT_REQUESTS
        window = window_seconds or settings.RATE_LIMIT_WINDOW_SECONDS
        now = time.time()
        cutoff = now - window

        with self._lock:
            timestamps = self._records.setdefault(key, [])
            # Evict timestamps outside the sliding window
            self._records[key] = [t for t in timestamps if t > cutoff]

            if len(self._records[key]) >= limit:
                oldest = self._records[key][0]
                retry_after = max(1, int(oldest + window - now))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "Rate limit exceeded. Please slow down.",
                        "code": "RATE_LIMIT_EXCEEDED",
                        "retry_after_seconds": retry_after
                    },
                    headers={"Retry-After": str(retry_after)}
                )

            self._records[key].append(now)

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

rate_limiter = InMemoryRateLimiter()
