"""Thin client over the Postman REST API (free-plan, personal-workspace scope).

Base ``https://api.getpostman.com``, authenticated with a personal API key via
the ``X-Api-Key`` header. The free tier is rate-limited, so requests retry with
exponential backoff and honor ``Retry-After`` on HTTP 429 / transient 5xx.

Methods return the *inner* resource object (``response["collection"]`` etc.) for
convenience; create/update re-wrap it as the API expects.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

BASE_URL = "https://api.getpostman.com"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF = 0.5
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class PostmanError(Exception):
    """Base error for Postman API problems."""


class PostmanAuthError(PostmanError):
    """Invalid or unauthorized API key (HTTP 401/403)."""


class PostmanAPIError(PostmanError):
    """A non-success API response."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"Postman API error {status_code}: {message}")


class PostmanClient:
    def __init__(
        self,
        api_key: str,
        *,
        client: httpx.Client | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff: float = DEFAULT_BACKOFF,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(base_url=BASE_URL, timeout=DEFAULT_TIMEOUT)
        self._headers = {"X-Api-Key": api_key}
        self._max_retries = max_retries
        self._backoff = backoff
        self._sleep = sleep

    # -- lifecycle --------------------------------------------------------- #

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> PostmanClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- core request with retry/backoff ----------------------------------- #

    def _request(self, method: str, path: str, *, json: dict | None = None) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                resp = self._client.request(method, path, headers=self._headers, json=json)
            except httpx.TransportError as exc:  # network blip
                last_exc = exc
                if attempt < self._max_retries:
                    self._sleep(self._backoff * (2**attempt))
                    continue
                raise PostmanError(f"Network error talking to Postman: {exc}") from exc

            if resp.status_code in RETRYABLE_STATUS and attempt < self._max_retries:
                self._sleep(self._retry_delay(resp, attempt))
                continue
            return self._handle(resp)

        raise PostmanError(f"Request failed after retries: {last_exc}")  # pragma: no cover

    def _retry_delay(self, resp: httpx.Response, attempt: int) -> float:
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:  # pragma: no cover - HTTP-date form, fall through
                pass
        return self._backoff * (2**attempt)

    @staticmethod
    def _handle(resp: httpx.Response) -> dict[str, Any]:
        if resp.status_code in (401, 403):
            raise PostmanAuthError(
                "Postman rejected the API key (401/403). Check REQUESTNEST_API_KEY "
                "or your saved key."
            )
        if resp.status_code >= 400:
            raise PostmanAPIError(resp.status_code, _error_message(resp))
        if not resp.content:
            return {}
        return resp.json()

    # -- account ----------------------------------------------------------- #

    def me(self) -> dict[str, Any]:
        """Validate the key and return the authenticated user (GET /me)."""
        return self._request("GET", "/me").get("user", {})

    # -- collections ------------------------------------------------------- #

    def list_collections(self) -> list[dict[str, Any]]:
        return self._request("GET", "/collections").get("collections", [])

    def get_collection(self, uid: str) -> dict[str, Any]:
        return self._request("GET", f"/collections/{uid}").get("collection", {})

    def create_collection(self, collection: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/collections", json={"collection": collection}).get(
            "collection", {}
        )

    def update_collection(self, uid: str, collection: dict[str, Any]) -> dict[str, Any]:
        return self._request("PUT", f"/collections/{uid}", json={"collection": collection}).get(
            "collection", {}
        )

    # -- environments ------------------------------------------------------ #

    def list_environments(self) -> list[dict[str, Any]]:
        return self._request("GET", "/environments").get("environments", [])

    def get_environment(self, uid: str) -> dict[str, Any]:
        return self._request("GET", f"/environments/{uid}").get("environment", {})

    def create_environment(self, environment: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/environments", json={"environment": environment}).get(
            "environment", {}
        )

    def update_environment(self, uid: str, environment: dict[str, Any]) -> dict[str, Any]:
        return self._request("PUT", f"/environments/{uid}", json={"environment": environment}).get(
            "environment", {}
        )


def _error_message(resp: httpx.Response) -> str:
    try:
        data = resp.json()
    except (ValueError, httpx.DecodingError):
        return resp.text or resp.reason_phrase
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            return error.get("message") or error.get("name") or str(error)
        if isinstance(error, str):
            return error
    return str(data)
