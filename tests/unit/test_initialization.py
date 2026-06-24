"""Test Langfuse client initialization with Sea Traces noauth configuration."""

import os

import httpx
import pytest

from langfuse import Langfuse
from langfuse._client.resource_manager import LangfuseResourceManager
from langfuse._client.sealangfuse_credentials import SealangfuseCredentials


class TestClientInitialization:
    @pytest.fixture(autouse=True)
    def cleanup_env_vars(self):
        original_values = {
            "LANGFUSE_BASE_URL": os.environ.get("LANGFUSE_BASE_URL"),
            "LANGFUSE_HOST": os.environ.get("LANGFUSE_HOST"),
            "LANGFUSE_PUBLIC_KEY": os.environ.get("LANGFUSE_PUBLIC_KEY"),
            "LANGFUSE_SECRET_KEY": os.environ.get("LANGFUSE_SECRET_KEY"),
            "SEATRACES_BASE_URL": os.environ.get("SEATRACES_BASE_URL"),
            "SEATRACES_PROJECT_ID": os.environ.get("SEATRACES_PROJECT_ID"),
            "SEA_TRACES_API_KEY": os.environ.get("SEA_TRACES_API_KEY"),
            "SEA_TRACES_BASE_URL": os.environ.get("SEA_TRACES_BASE_URL"),
            "SEA_TRACES_PROJECT_ID": os.environ.get("SEA_TRACES_PROJECT_ID"),
            "SEALANGFUSE_API_KEY": os.environ.get("SEALANGFUSE_API_KEY"),
            "SEALANGFUSE_CREDENTIALS_URL": os.environ.get(
                "SEALANGFUSE_CREDENTIALS_URL"
            ),
        }

        for key in original_values:
            os.environ.pop(key, None)

        yield

        LangfuseResourceManager.reset()

        for key in original_values:
            os.environ.pop(key, None)

        for key, value in original_values.items():
            if value is not None:
                os.environ[key] = value

    def test_internal_env_project_id_and_base_url_initialize_noauth_client(
        self, cleanup_env_vars, monkeypatch
    ):
        os.environ["SEATRACES_PROJECT_ID"] = "project-internal"
        os.environ["SEATRACES_BASE_URL"] = "https://internal.example.com"

        def resolve_credentials(**kwargs):
            raise AssertionError("Internal noauth config should not call gateway")

        monkeypatch.setattr(
            "langfuse._client.client.resolve_sealangfuse_credentials",
            resolve_credentials,
        )

        client = Langfuse()

        assert client._project_id == "project-internal"
        assert client._base_url == "https://internal.example.com"
        assert client.api._client_wrapper._username == "project-internal"
        assert client.api._client_wrapper._password == ""

    def test_internal_constructor_project_id_and_base_url_initialize_noauth_client(
        self, cleanup_env_vars, monkeypatch
    ):
        def resolve_credentials(**kwargs):
            raise AssertionError("Internal noauth config should not call gateway")

        monkeypatch.setattr(
            "langfuse._client.client.resolve_sealangfuse_credentials",
            resolve_credentials,
        )

        client = Langfuse(
            project_id="project-param",
            base_url="https://internal-param.example.com",
        )

        assert client._project_id == "project-param"
        assert client._base_url == "https://internal-param.example.com"

    def test_external_env_api_key_resolves_project_and_upload_base_url(
        self, cleanup_env_vars, monkeypatch
    ):
        os.environ["SEA_TRACES_API_KEY"] = "team-test-key"
        os.environ["SEA_TRACES_BASE_URL"] = "https://gateway.example.com"

        def resolve_credentials(**kwargs):
            assert kwargs["api_key"] == "team-test-key"
            assert kwargs["base_url"] == "https://gateway.example.com"
            assert "project_id" not in kwargs
            return SealangfuseCredentials(
                project_id="project-resolved",
                base_url="https://upload.example.com",
            )

        monkeypatch.setattr(
            "langfuse._client.client.resolve_sealangfuse_credentials",
            resolve_credentials,
        )

        client = Langfuse()

        assert client._project_id == "project-resolved"
        assert client._base_url == "https://upload.example.com"
        assert client.api._client_wrapper._username == "project-resolved"
        assert client.api._client_wrapper._password == ""

    def test_external_constructor_api_key_passes_httpx_client(
        self, cleanup_env_vars, monkeypatch
    ):
        httpx_client = httpx.Client()

        def resolve_credentials(**kwargs):
            assert kwargs["api_key"] == "sa-param-key"
            assert kwargs["base_url"] == "https://gateway-param.example.com"
            assert kwargs["httpx_client"] is httpx_client
            return SealangfuseCredentials(
                project_id="project-param-resolved",
                base_url="https://upload-param.example.com",
            )

        monkeypatch.setattr(
            "langfuse._client.client.resolve_sealangfuse_credentials",
            resolve_credentials,
        )

        client = Langfuse(
            api_key="sa-param-key",
            base_url="https://gateway-param.example.com",
            httpx_client=httpx_client,
        )

        assert client._project_id == "project-param-resolved"
        assert client._base_url == "https://upload-param.example.com"

    def test_external_api_key_takes_precedence_over_project_id_param(
        self, cleanup_env_vars, monkeypatch
    ):
        def resolve_credentials(**kwargs):
            assert kwargs["api_key"] == "sa-param-key"
            assert kwargs["base_url"] == "https://gateway-param.example.com"
            return SealangfuseCredentials(
                project_id="project-from-gateway",
                base_url="https://upload-param.example.com",
            )

        monkeypatch.setattr(
            "langfuse._client.client.resolve_sealangfuse_credentials",
            resolve_credentials,
        )

        client = Langfuse(
            api_key="sa-param-key",
            project_id="project-direct",
            base_url="https://gateway-param.example.com",
        )

        assert client._project_id == "project-from-gateway"
        assert client._base_url == "https://upload-param.example.com"

    def test_sea_traces_base_url_builds_default_credentials_url(
        self, cleanup_env_vars, monkeypatch
    ):
        os.environ["SEA_TRACES_API_KEY"] = "team-env-url-key"
        os.environ["SEA_TRACES_BASE_URL"] = "https://gateway.example.com/"

        def resolve_credentials(**kwargs):
            assert (
                kwargs["credentials_url"]
                == "https://gateway.example.com/hub/sea-traces-api-key"
            )
            return SealangfuseCredentials(
                project_id="project-url",
                base_url="https://upload-url.example.com",
            )

        monkeypatch.setattr(
            "langfuse._client.client.resolve_sealangfuse_credentials",
            resolve_credentials,
        )

        client = Langfuse()

        assert client._base_url == "https://upload-url.example.com"

    def test_failed_external_resolution_disables_client(
        self, cleanup_env_vars, monkeypatch
    ):
        def resolve_credentials(**kwargs):
            raise RuntimeError("resolver unavailable")

        monkeypatch.setattr(
            "langfuse._client.client.resolve_sealangfuse_credentials",
            resolve_credentials,
        )

        client = Langfuse(
            api_key="sa-bad-key",
            base_url="https://gateway.example.com",
        )

        assert client._resources is None

    def test_missing_auth_config_disables_client(self, cleanup_env_vars):
        client = Langfuse()

        assert client._resources is None

    def test_legacy_langfuse_credentials_remain_compatibility_path(
        self, cleanup_env_vars
    ):
        client = Langfuse(
            public_key="pk-explicit",
            secret_key="sk-explicit",
            base_url="https://legacy.example.com",
        )

        assert client._project_id == "pk-explicit"
        assert client._base_url == "https://legacy.example.com"
        assert client.api._client_wrapper._username == "pk-explicit"
