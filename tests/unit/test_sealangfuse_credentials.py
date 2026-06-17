import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from langfuse._client.sealangfuse_credentials import (
    clear_sealangfuse_credentials_cache,
    resolve_sealangfuse_credentials,
)


@pytest.fixture(autouse=True)
def clear_cache():
    clear_sealangfuse_credentials_cache()
    yield
    clear_sealangfuse_credentials_cache()


def test_resolve_sealangfuse_credentials_success():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        assert request.url.params["key"] == "sa-test"

        return httpx.Response(
            200,
            json={
                "publicKey": "pk-test",
                "secretKey": "sk-test",
                "baseUrl": "https://sealangfuse.example.com",
                "status": "ACTIVE",
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))

    credentials = resolve_sealangfuse_credentials(
        api_key="sa-test",
        credentials_url="https://resolver.example.com/api",
        httpx_client=client,
    )

    assert credentials.public_key == "pk-test"
    assert credentials.secret_key == "sk-test"
    assert credentials.base_url == "https://sealangfuse.example.com"
    assert calls == 1


def test_resolve_sealangfuse_credentials_uses_cache():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1

        return httpx.Response(
            200,
            json={
                "publicKey": "pk-cache",
                "secretKey": "sk-cache",
                "baseUrl": "https://cache.example.com",
                "status": "ACTIVE",
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))

    first_credentials = resolve_sealangfuse_credentials(
        api_key="sa-cache",
        credentials_url="https://resolver.example.com/api",
        httpx_client=client,
    )
    second_credentials = resolve_sealangfuse_credentials(
        api_key="sa-cache",
        credentials_url="https://resolver.example.com/api",
        httpx_client=client,
    )

    assert first_credentials == second_credentials
    assert calls == 1


def test_resolve_sealangfuse_credentials_singleflight_for_concurrent_calls():
    calls = 0
    calls_lock = threading.Lock()
    release_handler = threading.Event()
    worker_count = 8

    def handler(request):
        nonlocal calls
        with calls_lock:
            calls += 1

        release_handler.wait(timeout=5)

        return httpx.Response(
            200,
            json={
                "publicKey": "pk-concurrent",
                "secretKey": "sk-concurrent",
                "baseUrl": "https://concurrent.example.com",
                "status": "ACTIVE",
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    start_barrier = threading.Barrier(worker_count)

    def resolve_credentials():
        start_barrier.wait(timeout=5)
        return resolve_sealangfuse_credentials(
            api_key="sa-concurrent",
            credentials_url="https://resolver.example.com/api",
            httpx_client=client,
        )

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(resolve_credentials) for _ in range(worker_count)]

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with calls_lock:
                if calls == 1:
                    break
            time.sleep(0.01)

        release_handler.set()
        credentials = [future.result(timeout=5) for future in futures]

    assert all(credential.public_key == "pk-concurrent" for credential in credentials)
    assert calls == 1


def test_resolve_sealangfuse_credentials_rejects_inactive_key():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "publicKey": "pk-inactive",
                "secretKey": "sk-inactive",
                "baseUrl": "https://inactive.example.com",
                "status": "DISABLED",
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(RuntimeError):
        resolve_sealangfuse_credentials(
            api_key="sa-inactive",
            credentials_url="https://resolver.example.com/api",
            httpx_client=client,
        )
