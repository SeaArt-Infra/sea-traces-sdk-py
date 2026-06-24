"""Resolve Sea Traces API keys into Sea Traces project upload targets."""

from dataclasses import dataclass
from threading import Lock
from typing import Dict, Optional, Tuple

import httpx

from langfuse.logger import langfuse_logger

# 鉴权端点路径,拼接在网关 base_url 之后
SEALANGFUSE_CREDENTIALS_PATH = "/hub/sea-traces-api-key"


@dataclass(frozen=True)
class SealangfuseCredentials:
    project_id: str
    base_url: str


# 缓存 key 为 (api_key, credentials_url),避免重复请求网关鉴权接口
_CredentialsCacheKey = Tuple[str, str]
_credentials_cache: Dict[_CredentialsCacheKey, SealangfuseCredentials] = {}
_credentials_cache_lock = Lock()
_credentials_request_locks: Dict[_CredentialsCacheKey, Lock] = {}


def clear_sealangfuse_credentials_cache() -> None:
    """Clear the in-process Sealangfuse credentials cache."""
    with _credentials_cache_lock:
        _credentials_cache.clear()
        _credentials_request_locks.clear()


def build_sealangfuse_credentials_url(base_url: str) -> str:
    """Build the credentials resolver endpoint from a Sea Traces gateway base URL."""
    return f"{base_url.rstrip('/')}{SEALANGFUSE_CREDENTIALS_PATH}"


def resolve_sealangfuse_credentials(
    *,
    api_key: str,
    base_url: str,
    credentials_url: Optional[str] = None,
    timeout: Optional[int] = None,
    httpx_client: Optional[httpx.Client] = None,
) -> SealangfuseCredentials:
    """Resolve a Sea Traces API key into a noauth ingestion target.

    向网关 ``POST {base_url}/hub/sea-traces-api-key`` 发起鉴权请求,JSON body 携带
    ``api_key`` / ``base_url`` 两个字段,鉴权通过后返回项目 ID 和真正的上报地址。
    """
    # credentials_url 允许通过环境变量显式覆盖,默认用入参网关 base_url 拼接
    resolved_credentials_url = credentials_url or build_sealangfuse_credentials_url(
        base_url
    )
    cache_key: _CredentialsCacheKey = (api_key, resolved_credentials_url)

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
            "Credentials: Resolving Sea Traces API key via credentials endpoint | "
            f"api_key={_mask_api_key(api_key)} | endpoint={resolved_credentials_url}"
        )

        try:
            response = _get_credentials_response(
                api_key=api_key,
                base_url=base_url,
                credentials_url=resolved_credentials_url,
                timeout=timeout,
                httpx_client=httpx_client,
            )
            response.raise_for_status()
            payload = response.json()
            credentials = _parse_credentials_payload(payload)
        except Exception as error:
            message = (
                "Failed to resolve Sea Traces API key into noauth ingestion target. "
                "Check SEA_TRACES_API_KEY and SEA_TRACES_BASE_URL."
            )
            raise RuntimeError(message) from error

        with _credentials_cache_lock:
            _credentials_cache[cache_key] = credentials

        langfuse_logger.info(
            "Credentials: Successfully resolved Sea Traces API key | "
            f"api_key={_mask_api_key(api_key)} | project_id={credentials.project_id} | "
            f"base_url={credentials.base_url}"
        )

        return credentials


def _get_credentials_request_lock(cache_key: _CredentialsCacheKey) -> Lock:
    with _credentials_cache_lock:
        request_lock = _credentials_request_locks.get(cache_key)

        if request_lock is None:
            request_lock = Lock()
            _credentials_request_locks[cache_key] = request_lock

        return request_lock


def _get_credentials_response(
    *,
    api_key: str,
    base_url: str,
    credentials_url: str,
    timeout: Optional[int],
    httpx_client: Optional[httpx.Client],
) -> httpx.Response:
    request_body = {
        "api_key": api_key,
        "base_url": base_url,
    }

    if httpx_client is not None:
        return httpx_client.post(
            credentials_url,
            json=request_body,
            timeout=timeout,
        )

    with httpx.Client(timeout=timeout) as client:
        return client.post(credentials_url, json=request_body)


def _parse_credentials_payload(payload: object) -> SealangfuseCredentials:
    if not isinstance(payload, dict):
        message = "Sea Traces credentials response must be a JSON object."
        raise ValueError(message)

    project_id = payload.get("project_id")
    base_url = payload.get("base_url")

    if not isinstance(project_id, str) or not project_id:
        message = "Sea Traces credentials response is missing project_id."
        raise ValueError(message)

    if not isinstance(base_url, str) or not base_url:
        message = "Sea Traces credentials response is missing base_url."
        raise ValueError(message)

    return SealangfuseCredentials(
        project_id=project_id,
        base_url=base_url,
    )


def _mask_api_key(api_key: str) -> str:
    if len(api_key) <= 10:
        return "***"

    return f"{api_key[:6]}...{api_key[-4:]}"
