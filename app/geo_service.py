import httpx
import logging
from typing import Optional, Dict, Any
from pydantic import BaseModel

logger = logging.getLogger("geo_service")

class GeoLocation(BaseModel):
    country: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    provider: Optional[str] = None
    is_enriched: bool = False

class GeoEnrichmentService:
    def __init__(self, timeout_seconds: float = 2.0):
        self.timeout = timeout_seconds

    async def _query_provider_a(self, ip: str, mock_status: Optional[str] = None) -> Optional[GeoLocation]:
        """Primary Geo Provider: ip-api.com"""
        if mock_status == "down":
            raise httpx.RequestError("Mocked Provider A failure: Service Unavailable")
        if mock_status == "success":
            return GeoLocation(
                country="United States",
                city="San Francisco",
                region="California",
                provider="provider_a (mocked)",
                is_enriched=True
            )

        # Do not query external API for private/loopback IPs
        if ip in ("127.0.0.1", "localhost", "::1", "testclient"):
            return GeoLocation(
                country="Localhost",
                city="Local City",
                region="Local Region",
                provider="provider_a (local)",
                is_enriched=True
            )

        url = f"http://ip-api.com/json/{ip}?fields=status,message,country,regionName,city"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    return GeoLocation(
                        country=data.get("country"),
                        city=data.get("city"),
                        region=data.get("regionName"),
                        provider="ip-api.com",
                        is_enriched=True
                    )
        raise ValueError(f"Provider A returned invalid or non-success response: {resp.status_code}")

    async def _query_provider_b(self, ip: str, mock_status: Optional[str] = None) -> Optional[GeoLocation]:
        """Secondary Fallback Provider: ipapi.co"""
        if mock_status == "down":
            raise httpx.RequestError("Mocked Provider B failure: Service Unavailable")
        if mock_status == "success":
            return GeoLocation(
                country="Canada",
                city="Toronto",
                region="Ontario",
                provider="provider_b (mocked)",
                is_enriched=True
            )

        if ip in ("127.0.0.1", "localhost", "::1", "testclient"):
            return GeoLocation(
                country="Localhost",
                city="Local City",
                region="Local Region",
                provider="provider_b (local)",
                is_enriched=True
            )

        url = f"https://ipapi.co/{ip}/json/"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, headers={"User-Agent": "WidgetPlatform/1.0"})
            if resp.status_code == 200:
                data = resp.json()
                if not data.get("error"):
                    return GeoLocation(
                        country=data.get("country_name"),
                        city=data.get("city"),
                        region=data.get("region"),
                        provider="ipapi.co",
                        is_enriched=True
                    )
        raise ValueError(f"Provider B returned invalid or non-success response: {resp.status_code}")

    async def enrich_ip(
        self,
        ip: str,
        mock_a: Optional[str] = None,
        mock_b: Optional[str] = None
    ) -> GeoLocation:
        """
        Fallback chain execution:
        1. Attempt Provider A
        2. On failure, attempt Provider B
        3. If all fail, degrade gracefully and return empty GeoLocation (never crash)
        """
        # Step 1: Provider A
        try:
            geo = await self._query_provider_a(ip, mock_status=mock_a)
            if geo and geo.is_enriched:
                return geo
        except Exception as e:
            logger.warning(f"Geo Provider A failed for IP {ip}: {e}. Triggering fallback to Provider B.")

        # Step 2: Fallback to Provider B
        try:
            geo = await self._query_provider_b(ip, mock_status=mock_b)
            if geo and geo.is_enriched:
                return geo
        except Exception as e:
            logger.warning(f"Geo Provider B failed for IP {ip}: {e}. All providers exhausted.")

        # Step 3: Graceful degradation (All providers down -> submission still succeeds)
        return GeoLocation(
            country=None,
            city=None,
            region=None,
            provider=None,
            is_enriched=False
        )

geo_service = GeoEnrichmentService()
