"""Client for interacting with the PseudoGram mock API."""

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class PseudoGramResponse:
    status_code: int
    data: Optional[dict] = None
    dm_id: Optional[str] = None
    dm_status: Optional[str] = None
    retry_after: Optional[int] = None
    error_message: Optional[str] = None


class PseudoGramClient:
    """HTTP client for PseudoGram DM endpoint."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 10.0,
    ):
        self.base_url = (base_url or settings.pseudogram_url).rstrip("/")
        self.api_key = api_key or settings.PSEUDOGRAM_API_KEY
        self.timeout = timeout

    def send_dm(
        self,
        recipient_user_id: str,
        message: str,
        comment_id: str,
        idempotency_key: Optional[str] = None,
    ) -> PseudoGramResponse:
        """Send a DM via PseudoGram API POST /v1/dm/send."""
        url = f"{self.base_url}/v1/dm/send"
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        payload = {
            "recipient_user_id": recipient_user_id,
            "message": message,
            "comment_id": comment_id,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload, headers=headers)

            status_code = response.status_code
            retry_after = None

            # Parse Retry-After header if present (for 429)
            retry_after_hdr = response.headers.get("Retry-After")
            if retry_after_hdr:
                try:
                    retry_after = int(retry_after_hdr)
                except ValueError:
                    retry_after = 60

            try:
                data = response.json()
            except Exception:
                data = None

            dm_id = data.get("dm_id") if isinstance(data, dict) else None
            dm_status = data.get("status") if isinstance(data, dict) else None

            error_msg = None
            if status_code >= 400:
                error_msg = f"HTTP {status_code}: {response.text}"

            return PseudoGramResponse(
                status_code=status_code,
                data=data,
                dm_id=dm_id,
                dm_status=dm_status,
                retry_after=retry_after,
                error_message=error_msg,
            )

        except httpx.RequestError as exc:
            logger.error(f"Network error when calling PseudoGram API: {exc}")
            return PseudoGramResponse(
                status_code=500,
                error_message=f"Network error: {str(exc)}",
            )

    def get_dm_status(self, dm_id: str) -> PseudoGramResponse:
        """Check delivery status of a DM via PseudoGram API GET /v1/dm/{dm_id}."""
        url = f"{self.base_url}/v1/dm/{dm_id}"
        headers = {
            "X-API-Key": self.api_key,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, headers=headers)

            status_code = response.status_code
            data = None
            try:
                data = response.json()
            except Exception:
                data = None

            dm_status = data.get("status") if isinstance(data, dict) else None
            error_msg = f"HTTP {status_code}: {response.text}" if status_code >= 400 else None

            return PseudoGramResponse(
                status_code=status_code,
                data=data,
                dm_id=dm_id,
                dm_status=dm_status,
                error_message=error_msg,
            )

        except httpx.RequestError as exc:
            logger.error(f"Network error when checking DM status {dm_id}: {exc}")
            return PseudoGramResponse(
                status_code=500,
                error_message=f"Network error: {str(exc)}",
            )

