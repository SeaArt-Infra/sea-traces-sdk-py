"""Resolve Sea Traces API keys into Langfuse project credentials."""

from dataclasses import dataclass
from threading import Lock
from typing import Dict, Optional, Tuple

import httpx

from langfuse.logger import langfuse_logger

# 鉴权端点路径,拼接在网关 base_url 之后
SEALANGFUSE_CREDENTIALS_PATH = "/hub/sea-traces-api-key"


@dataclass(frozen=True)
class SealangfuseCredentials:
    public_key: str
    secret_key: str
    base_url: str


# 缓存 key 为 (api_key, project_id, credentials_url),避免同 key 不同 project 命中错误缓存
_CredentialsCacheKey = Tuple[str, str, str]
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
    project_id: str,
    credentials_url: Optional[str] = None,
    timeout: Optional[int] = None,
    httpx_client: Optional[httpx.Client] = None,
) -> SealangfuseCredentials:
    """Resolve a Sea Traces API key into Langfuse project credentials.

    向网关 ``POST {base_url}/hub/sea-traces-api-key`` 发起鉴权请求,JSON body 携带
    ``api_key`` / ``base_url`` / ``project_id`` 三个字段,鉴权通过后返回 Langfuse 上报凭证。
    """
    # credentials_url 允许通过环境变量显式覆盖,默认用入参网关 base_url 拼接
    resolved_credentials_url = credentials_url or build_sealangfuse_credentials_url(
        base_url
    )
    cache_key: _CredentialsCacheKey = (api_key, project_id, resolved_credentials_url)

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
            f"api_key={_mask_api_key(api_key)} | project_id={project_id} | "
            f"endpoint={resolved_credentials_url}"
        )

        try:
            response = _get_credentials_response(
                api_key=api_key,
                base_url=base_url,
                project_id=project_id,
                credentials_url=resolved_credentials_url,
                timeout=timeout,
                httpx_client=httpx_client,
            )
            response.raise_for_status()
            payload = response.json()
            credentials = _parse_credentials_payload(payload)
        except Exception as error:
            message = (
                "Failed to resolve Sea Traces API key into Langfuse credentials. "
                "Check SEA_TRACES_API_KEY, SEA_TRACES_BASE_URL, and SEA_TRACES_PROJECT_ID."
            )
            raise RuntimeError(message) from error

        with _credentials_cache_lock:
            _credentials_cache[cache_key] = credentials

        langfuse_logger.info(
            "Credentials: Successfully resolved Sea Traces API key | "
            f"api_key={_mask_api_key(api_key)} | base_url={credentials.base_url}"
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
    project_id: str,
    credentials_url: str,
    timeout: Optional[int],
    httpx_client: Optional[httpx.Client],
) -> httpx.Response:
    request_body = {
        "api_key": api_key,
        "base_url": base_url,
        "project_id": project_id,
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

    public_key = payload.get("publicKey")
    secret_key = payload.get("secretKey")
    base_url = payload.get("baseUrl")

    if not isinstance(public_key, str) or not public_key:
        message = "Sea Traces credentials response is missing publicKey."
        raise ValueError(message)

    if not isinstance(secret_key, str) or not secret_key:
        message = "Sea Traces credentials response is missing secretKey."
        raise ValueError(message)

    if not isinstance(base_url, str) or not base_url:
        message = "Sea Traces credentials response is missing baseUrl."
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
