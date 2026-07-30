from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx


class SeaTracesAPI:
    """Gateway-authenticated client for project and trace APIs."""

    def __init__(self, base_url: str, token: str, *, timeout: float = 60.0):
        if not base_url.strip() or not token.strip():
            raise ValueError("base_url and token are required")
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SeaTracesAPI":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self._client.request(method, path, **kwargs)
        if response.is_error:
            raise RuntimeError(f"Sea Traces API request failed ({response.status_code}): {response.text}")
        return response.json()

    def list_projects(self) -> dict[str, Any]:
        return self._request("GET", "/api/internal/projects")

    def create_project(self, name: str) -> dict[str, Any]:
        return self._request("POST", "/api/internal/projects", json={"name": name})

    def update_project(self, project_id: str, name: str) -> dict[str, Any]:
        return self._request("PATCH", f"/api/internal/projects/{project_id}", json={"name": name})

    def ingest(self, project_id: str, batch: list[dict[str, Any]]) -> dict[str, Any]:
        return self._request("POST", f"/api/internal/projects/{project_id}/ingestion", json={"batch": batch})

    def list_traces(
        self,
        project_id: str,
        *,
        trace_id: str | None = None,
        from_timestamp: datetime | str | None = None,
        to_timestamp: datetime | str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> dict[str, Any]:
        def date_value(value: datetime | str | None) -> str | None:
            return value.isoformat() if isinstance(value, datetime) else value

        params = {"page": page, "limit": limit}
        if trace_id:
            params["traceId"] = trace_id
        if from_timestamp:
            params["fromTimestamp"] = date_value(from_timestamp)
        if to_timestamp:
            params["toTimestamp"] = date_value(to_timestamp)
        return self._request("GET", f"/api/internal/projects/{project_id}/traces", params=params)
