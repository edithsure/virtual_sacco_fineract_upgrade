"""Small, configurable HTTP client for Apache Fineract.

This module intentionally exposes read-only integration methods first. Financial
write operations should be enabled only after loan-product rules, member identity
mapping, idempotency, reconciliation and approval controls have been validated.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import requests


class FineractError(RuntimeError):
    """Raised when Fineract is unavailable or returns an unexpected response."""


@dataclass
class FineractConfig:
    base_url: str = os.getenv("FINERACT_BASE_URL", "https://localhost:8443/fineract-provider")
    username: str = os.getenv("FINERACT_USERNAME", "mifos")
    password: str = os.getenv("FINERACT_PASSWORD", "")
    tenant_id: str = os.getenv("FINERACT_TENANT_ID", "default")
    verify_tls: bool = os.getenv("FINERACT_VERIFY_TLS", "true").lower() in {"1", "true", "yes"}
    timeout_seconds: float = float(os.getenv("FINERACT_TIMEOUT_SECONDS", "8"))


class FineractClient:
    def __init__(self, config: FineractConfig | None = None):
        self.config = config or FineractConfig()
        self.base_url = self.config.base_url.rstrip("/")
        self.api_url = self.base_url + "/api/v1/"
        self.session = requests.Session()
        self.session.auth = (self.config.username, self.config.password)
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Fineract-Platform-TenantId": self.config.tenant_id,
        })

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        if not self.config.password:
            raise FineractError("FINERACT_PASSWORD is not configured.")
        url = urljoin(self.api_url, path.lstrip("/"))
        try:
            response = self.session.request(
                method, url, timeout=self.config.timeout_seconds,
                verify=self.config.verify_tls, **kwargs
            )
        except requests.RequestException as exc:
            raise FineractError(f"Could not connect to Fineract: {exc.__class__.__name__}") from exc
        if not response.ok:
            # Avoid logging request credentials or full response payloads here.
            detail = f"HTTP {response.status_code} from Fineract"
            try:
                body = response.json()
                if isinstance(body, dict):
                    message = body.get("defaultUserMessage") or body.get("developerMessage")
                    if message:
                        detail += f": {str(message)[:240]}"
            except ValueError:
                pass
            raise FineractError(detail)
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise FineractError("Fineract returned a non-JSON response.") from exc

    def health(self) -> dict[str, Any]:
        """Check Fineract actuator health. This endpoint is outside /api/v1."""
        if not self.config.password:
            return {"ok": False, "message": "FINERACT_PASSWORD is not configured."}
        url = self.base_url + "/actuator/health"
        try:
            response = self.session.get(url, timeout=self.config.timeout_seconds,
                                        verify=self.config.verify_tls)
            if response.ok:
                payload = response.json()
                return {"ok": payload.get("status") == "UP", "status": payload.get("status", "UNKNOWN"),
                        "message": "Fineract health endpoint responded."}
            return {"ok": False, "status": "HTTP_ERROR", "message": f"Health endpoint returned HTTP {response.status_code}."}
        except (requests.RequestException, ValueError) as exc:
            return {"ok": False, "status": "UNAVAILABLE", "message": f"Fineract could not be reached ({exc.__class__.__name__})."}

    def get_loan_products(self) -> list[dict[str, Any]]:
        result = self._request("GET", "loanproducts")
        return result if isinstance(result, list) else []

    def get_client(self, client_id: int) -> dict[str, Any]:
        return self._request("GET", f"clients/{int(client_id)}")

    def get_loan(self, loan_id: int) -> dict[str, Any]:
        return self._request("GET", f"loans/{int(loan_id)}")

    def get_loans(self, client_id: int | None = None) -> list[dict[str, Any]]:
        params = {"clientId": int(client_id)} if client_id is not None else {}
        result = self._request("GET", "loans", params=params)
        if isinstance(result, dict):
            return result.get("pageItems", [])
        return result if isinstance(result, list) else []
