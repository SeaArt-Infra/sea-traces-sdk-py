"""Resolve Sealangfuse API keys into Langfuse project credentials."""

from dataclasses import dataclass
from threading import Lock
from typing import Dict, Optional, Tuple

import httpx

from langfuse.logger import langfuse_logger

DEFAULT_SEALANGFUSE_CREDENTIALS_URL = (
    "https://sealangfuse-web.us-west1.infra.seaart.dev"
    "/api/public/sea-project-api-credentials"
)
SEALANGFUSE_CREDENTIALS_PATH = "/api/public/sea-project-api-credentials"


@dataclass(frozen=True)
class SealangfuseCredentials:
    public_key: str
    secret_key: str
    base_url: str


_credentials_cache: Dict[Tuple[str, str], SealangfuseCredentials] = {}
_credentials_cache_lock = Lock()
_credentials_request_locks: Dict[Tuple[str, str], Lock] = {}


def clear_sealangfuse_credentials_cache() -> None:
    """Clear the in-process Sealangfuse credentials cache."""
    with _credentials_cache_lock:
        _credentials_cache.clear()
        _credentials_request_locks.clear()


def build_sealangfuse_credentials_url(base_url: str) -> str:
    """Build the credentials resolver endpoint from a Sealangfuse base URL."""
    return f"{base_url.rstrip('/')}{SEALANGFUSE_CREDENTIALS_PATH}"


def resolve_sealangfuse_credentials(
    *,
    api_key: str,
    credentials_url: Optional[str] = None,
    timeout: Optional[int] = None,
    httpx_client: Optional[httpx.Client] = None,
) -> SealangfuseCredentials:
    """Resolve a Sealangfuse API key into Langfuse project credentials."""
    resolved_credentials_url = credentials_url or DEFAULT_SEALANGFUSE_CREDENTIALS_URL
    cache_key = (api_key, resolved_credentials_url)

    with _credentials_cache_lock:
        cached_credentials = _credentials_cache.get(cache_key)

    if cached_credentials is not None:
        return cached_credentials

    request_lock = _get_credentials_request_lock(cache_key)

    with request_lock:
        with _credentials_cache_lock:
            cached_credentials = _credentials_cache.get(cache_key)

        if cached_credentials is not None:
            return cached_credentials

        langfuse_logger.debug(
            "Credentials: Resolving Sealangfuse API key via credentials endpoint | "
            f"api_key={_mask_api_key(api_key)} | endpoint={resolved_credentials_url}"
        )

        try:
            response = _get_credentials_response(
                api_key=api_key,
                credentials_url=resolved_credentials_url,
                timeout=timeout,
                httpx_client=httpx_client,
            )
            response.raise_for_status()
            payload = response.json()
            credentials = _parse_credentials_payload(payload)
        except Exception as error:
            message = (
                "Failed to resolve Sealangfuse API key into Langfuse credentials. "
                "Check SEA_TEAM_KEY, SEA_TRACES_BASE_URL, and SEALANGFUSE_CREDENTIALS_URL."
            )
            raise RuntimeError(message) from error

        with _credentials_cache_lock:
            _credentials_cache[cache_key] = credentials

        langfuse_logger.info(
            "Credentials: Successfully resolved Sealangfuse API key | "
            f"api_key={_mask_api_key(api_key)} | base_url={credentials.base_url}"
        )

        return credentials


def _get_credentials_request_lock(cache_key: Tuple[str, str]) -> Lock:
    with _credentials_cache_lock:
        request_lock = _credentials_request_locks.get(cache_key)

        if request_lock is None:
            request_lock = Lock()
            _credentials_request_locks[cache_key] = request_lock

        return request_lock


def _get_credentials_response(
    *,
    api_key: str,
    credentials_url: str,
    timeout: Optional[int],
    httpx_client: Optional[httpx.Client],
) -> httpx.Response:
    request_params = {"key": api_key}

    if httpx_client is not None:
        return httpx_client.get(
            credentials_url,
            params=request_params,
            timeout=timeout,
        )

    with httpx.Client(timeout=timeout) as client:
        return client.get(credentials_url, params=request_params)


def _parse_credentials_payload(payload: object) -> SealangfuseCredentials:
    if not isinstance(payload, dict):
        message = "Sealangfuse credentials response must be a JSON object."
        raise ValueError(message)

    status = payload.get("status")
    if status != "ACTIVE":
        message = "Sealangfuse API key is not active."
        raise ValueError(message)

    public_key = payload.get("publicKey")
    secret_key = payload.get("secretKey")
    base_url = payload.get("baseUrl")

    if not isinstance(public_key, str) or not public_key:
        message = "Sealangfuse credentials response is missing publicKey."
        raise ValueError(message)

    if not isinstance(secret_key, str) or not secret_key:
        message = "Sealangfuse credentials response is missing secretKey."
        raise ValueError(message)

    if not isinstance(base_url, str) or not base_url:
        message = "Sealangfuse credentials response is missing baseUrl."
        raise ValueError(message)

    return SealangfuseCredentials(
        public_key=public_key,
        secret_key=secret_key,
        base_url=base_url,
    )


def _mask_api_key(api_key: str) -> str:
    if len(api_key) <= 10:
        return "***"

    return f"{api_key[:6]}...{api_key[-4:]}"
