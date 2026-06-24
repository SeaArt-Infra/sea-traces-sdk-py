"""Test suite for Langfuse client initialization with Sea Traces configuration.

This test suite verifies both supported initialization paths:
Sea Traces gateway authentication and direct Langfuse credentials.
"""

import os

import httpx
import pytest

from langfuse import Langfuse
from langfuse._client.resource_manager import LangfuseResourceManager
from langfuse._client.sealangfuse_credentials import SealangfuseCredentials


class TestClientInitialization:
    """Tests for Langfuse client initialization with different URL configurations."""

    @pytest.fixture(autouse=True)
    def cleanup_env_vars(self):
        """Fixture to clean up environment variables and singleton cache before and after each test."""
        # Store original values
        original_values = {
            "LANGFUSE_BASE_URL": os.environ.get("LANGFUSE_BASE_URL"),
            "LANGFUSE_HOST": os.environ.get("LANGFUSE_HOST"),
            "LANGFUSE_PUBLIC_KEY": os.environ.get("LANGFUSE_PUBLIC_KEY"),
            "LANGFUSE_SECRET_KEY": os.environ.get("LANGFUSE_SECRET_KEY"),
            "SEATRACES_BASE_URL": os.environ.get("SEATRACES_BASE_URL"),
            "SEATRACES_PUBLIC_KEY": os.environ.get("SEATRACES_PUBLIC_KEY"),
            "SEATRACES_SECRET_KEY": os.environ.get("SEATRACES_SECRET_KEY"),
            "SEA_TRACES_API_KEY": os.environ.get("SEA_TRACES_API_KEY"),
            "SEA_TRACES_BASE_URL": os.environ.get("SEA_TRACES_BASE_URL"),
            "SEA_TRACES_PROJECT_ID": os.environ.get("SEA_TRACES_PROJECT_ID"),
            "SEALANGFUSE_API_KEY": os.environ.get("SEALANGFUSE_API_KEY"),
            "SEALANGFUSE_CREDENTIALS_URL": os.environ.get(
                "SEALANGFUSE_CREDENTIALS_URL"
            ),
        }

        # Remove auth env vars for the test.
        for key in [
            "LANGFUSE_BASE_URL",
            "LANGFUSE_HOST",
            "LANGFUSE_PUBLIC_KEY",
            "LANGFUSE_SECRET_KEY",
            "SEATRACES_BASE_URL",
            "SEATRACES_PUBLIC_KEY",
            "SEATRACES_SECRET_KEY",
            "SEA_TRACES_API_KEY",
            "SEA_TRACES_BASE_URL",
            "SEA_TRACES_PROJECT_ID",
            "SEALANGFUSE_API_KEY",
            "SEALANGFUSE_CREDENTIALS_URL",
        ]:
            if key in os.environ:
                del os.environ[key]

        yield

        # Clear the singleton cache to prevent test pollution
        with LangfuseResourceManager._lock:
            LangfuseResourceManager._instances.clear()

        # Restore original values - always remove any test values first
        for key in [
            "LANGFUSE_BASE_URL",
            "LANGFUSE_HOST",
            "LANGFUSE_PUBLIC_KEY",
            "LANGFUSE_SECRET_KEY",
            "SEATRACES_BASE_URL",
            "SEATRACES_PUBLIC_KEY",
            "SEATRACES_SECRET_KEY",
            "SEA_TRACES_API_KEY",
            "SEA_TRACES_BASE_URL",
            "SEA_TRACES_PROJECT_ID",
            "SEALANGFUSE_API_KEY",
            "SEALANGFUSE_CREDENTIALS_URL",
        ]:
            if key in os.environ:
                del os.environ[key]

        # Then restore original values
        for key, value in original_values.items():
            if value is not None:
                os.environ[key] = value

    def test_base_url_parameter_takes_precedence(self, cleanup_env_vars):
        """Test that base_url parameter takes highest precedence."""
        os.environ["SEA_TRACES_BASE_URL"] = "http://env-base-url.com"
        os.environ["SEA_TRACES_API_KEY"] = "team-test-key"
        os.environ["SEA_TRACES_PROJECT_ID"] = "project-test-id"

        client = Langfuse(
            base_url="http://param-base-url.com",
            public_key="test_pk",
            secret_key="test_sk",
        )

        assert client._base_url == "http://param-base-url.com"

    def test_seatraces_base_url_enables_direct_upload(self, cleanup_env_vars):
        """Test that SEATRACES_BASE_URL supports direct credentials."""
        os.environ["SEA_TRACES_API_KEY"] = "team-test-key"
        os.environ["SEATRACES_BASE_URL"] = "http://env-base-url.com"

        client = Langfuse(
            public_key="test_pk",
            secret_key="test_sk",
        )

        assert client._base_url == "http://env-base-url.com"

    def test_host_parameter_supports_direct_langfuse_upload(self, cleanup_env_vars):
        """Test that host still supports direct Langfuse credentials."""
        os.environ["SEA_TRACES_API_KEY"] = "team-test-key"
        client = Langfuse(
            host="http://param-host.com",
            public_key="test_pk",
            secret_key="test_sk",
        )

        assert client._base_url == "http://param-host.com"

    def test_env_host_supports_legacy_direct_upload(self, cleanup_env_vars):
        """Test that LANGFUSE_HOST remains a legacy direct credentials fallback."""
        os.environ["SEA_TRACES_API_KEY"] = "team-test-key"
        os.environ["LANGFUSE_HOST"] = "http://env-host.com"

        client = Langfuse(
            public_key="test_pk",
            secret_key="test_sk",
        )

        assert client._base_url == "http://env-host.com"

    def test_missing_required_sea_traces_config_disables_client(self, cleanup_env_vars):
        """Test that SDK is disabled when Sea Traces credentials are absent."""
        client = Langfuse(
            public_key="test_pk",
            secret_key="test_sk",
        )

        assert client._resources is None

    def test_empty_required_sea_traces_config_disables_client(self, cleanup_env_vars):
        """Test that empty Sea Traces config values are treated as missing."""
        os.environ["SEA_TRACES_API_KEY"] = ""
        os.environ["SEA_TRACES_BASE_URL"] = "   "

        client = Langfuse(
            public_key="test_pk",
            secret_key="test_sk",
        )

        assert client._resources is None

    def test_seatraces_base_url_with_direct_keys_does_not_need_team_key(
        self, cleanup_env_vars
    ):
        """Test that direct Sea Traces credentials do not require SEA_TRACES_API_KEY."""
        os.environ["SEATRACES_BASE_URL"] = "http://test-base-url.com"

        client = Langfuse(
            public_key="test_pk",
            secret_key="test_sk",
        )

        assert client._base_url == "http://test-base-url.com"

    def test_sea_traces_base_url_env_var(self, cleanup_env_vars, monkeypatch):
        """Test that SEA_TRACES_BASE_URL is used for gateway credential resolution."""
        os.environ["SEA_TRACES_API_KEY"] = "team-test-key"
        os.environ["SEA_TRACES_BASE_URL"] = "http://sea-traces-base-url.com"
        os.environ["SEA_TRACES_PROJECT_ID"] = "project-test-id"

        def resolve_credentials(**kwargs):
            assert kwargs["base_url"] == "http://sea-traces-base-url.com"
            return SealangfuseCredentials(
                public_key="pk-sea-env",
                secret_key="sk-sea-env",
                base_url="http://resolved-sea-traces-base-url.com",
            )

        monkeypatch.setattr(
            "langfuse._client.client.resolve_sealangfuse_credentials",
            resolve_credentials,
        )

        client = Langfuse()

        assert client._base_url == "http://resolved-sea-traces-base-url.com"

    def test_sea_traces_base_url_takes_precedence_over_legacy_env(
        self, cleanup_env_vars, monkeypatch
    ):
        """Test gateway auth uses SEA_TRACES_BASE_URL instead of LANGFUSE_BASE_URL."""
        os.environ["SEA_TRACES_API_KEY"] = "team-test-key"
        os.environ["SEA_TRACES_BASE_URL"] = "http://sea-traces-base-url.com"
        os.environ["SEA_TRACES_PROJECT_ID"] = "project-test-id"
        os.environ["LANGFUSE_BASE_URL"] = "http://legacy-base-url.com"

        def resolve_credentials(**kwargs):
            assert kwargs["base_url"] == "http://sea-traces-base-url.com"
            return SealangfuseCredentials(
                public_key="pk-sea-precedence",
                secret_key="sk-sea-precedence",
                base_url="http://resolved-sea-precedence.com",
            )

        monkeypatch.setattr(
            "langfuse._client.client.resolve_sealangfuse_credentials",
            resolve_credentials,
        )

        client = Langfuse()

        assert client._base_url == "http://resolved-sea-precedence.com"

    def test_host_env_var_supports_legacy_direct_upload(self, cleanup_env_vars):
        """Test that LANGFUSE_HOST supports legacy direct credentials."""
        os.environ["LANGFUSE_HOST"] = "http://test-host.com"

        client = Langfuse(
            public_key="test_pk",
            secret_key="test_sk",
        )

        assert client._base_url == "http://test-host.com"

    def test_base_url_parameter(self, cleanup_env_vars):
        """Test that base_url parameter is used correctly."""
        client = Langfuse(
            api_key="team-test-key",
            base_url="http://param-base-url.com",
            project_id="project-test-id",
            public_key="test_pk",
            secret_key="test_sk",
        )

        assert client._base_url == "http://param-base-url.com"

    def test_precedence_order_all_set(self, cleanup_env_vars):
        """Test complete precedence order for Sea Traces base URL."""
        os.environ["SEA_TRACES_API_KEY"] = "team-test-key"
        os.environ["SEA_TRACES_BASE_URL"] = "http://sea-env-base-url.com"
        os.environ["SEA_TRACES_PROJECT_ID"] = "project-test-id"
        os.environ["SEATRACES_BASE_URL"] = "http://env-base-url.com"
        os.environ["LANGFUSE_HOST"] = "http://env-host.com"

        # Case 1: base_url parameter wins
        client1 = Langfuse(
            base_url="http://param-base-url.com",
            host="http://param-host.com",
            public_key="test_pk",
            secret_key="test_sk",
        )
        assert client1._base_url == "http://param-base-url.com"

        # Case 2: direct Sea Traces env vars win when direct credentials are complete
        client2 = Langfuse(
            public_key="test_pk",
            secret_key="test_sk",
        )
        assert client2._base_url == "http://env-base-url.com"

    def test_direct_legacy_host_fallback_without_sea_traces_base_url(
        self, cleanup_env_vars
    ):
        """Test that direct credentials can use legacy host without Sea Traces config."""
        os.environ["SEA_TRACES_API_KEY"] = "team-test-key"
        os.environ["LANGFUSE_HOST"] = "http://env-host.com"

        client1 = Langfuse(
            host="http://param-host.com",
            public_key="test_pk",
            secret_key="test_sk",
        )
        assert client1._base_url == "http://param-host.com"

        client2 = Langfuse(
            public_key="test_pk",
            secret_key="test_sk",
        )
        assert client2._base_url == "http://env-host.com"

    def test_url_used_in_api_client(self, cleanup_env_vars):
        """Test that the resolved base_url is correctly passed to API clients."""
        test_url = "http://test-unique-api.com"
        # Use a unique public key to avoid singleton conflicts
        client = Langfuse(
            api_key="team-test-key",
            base_url=test_url,
            project_id="project-test-id",
            public_key=f"test_pk_{test_url}",
            secret_key="test_sk",
        )

        # Check that the API client has the correct base_url
        assert client.api._client_wrapper._base_url == test_url
        assert client.async_api._client_wrapper._base_url == test_url

    def test_url_used_in_trace_url_generation(self, cleanup_env_vars):
        """Test that the resolved base_url is stored correctly for trace URL generation."""
        test_url = "http://test-trace-api.com"
        # Use a unique public key to avoid singleton conflicts
        client = Langfuse(
            api_key="team-test-key",
            base_url=test_url,
            project_id="project-test-id",
            public_key=f"test_pk_{test_url}",
            secret_key="test_sk",
        )

        # Verify that the base_url is stored correctly and will be used for URL generation
        # We can't test the full URL generation without making network calls to get project_id
        # but we can verify the base_url is correctly set
        assert client._base_url == test_url

    def test_both_base_url_and_host_params(self, cleanup_env_vars):
        """Test that base_url parameter takes precedence over host parameter."""
        client = Langfuse(
            api_key="team-test-key",
            base_url="http://base-url.com",
            project_id="project-test-id",
            host="http://host.com",
            public_key="test_pk",
            secret_key="test_sk",
        )

        assert client._base_url == "http://base-url.com"

    def test_direct_seatraces_base_url_env_takes_precedence_over_host_env(
        self, cleanup_env_vars
    ):
        """Test direct Sea Traces base URL precedence over deprecated host."""
        os.environ["SEATRACES_BASE_URL"] = "http://base-url.com"
        os.environ["LANGFUSE_HOST"] = "http://host.com"

        client = Langfuse(
            public_key="test_pk",
            secret_key="test_sk",
        )

        assert client._base_url == "http://base-url.com"

    def test_localhost_urls(self, cleanup_env_vars, monkeypatch):
        """Test that localhost URLs work correctly."""
        # Test with base_url
        client1 = Langfuse(
            api_key="team-test-key",
            base_url="http://localhost:3000",
            project_id="project-test-id",
            public_key="test_pk",
            secret_key="test_sk",
        )
        assert client1._base_url == "http://localhost:3000"

        # Test with host (deprecated) for direct Langfuse credentials
        client2 = Langfuse(
            api_key="team-test-key",
            host="http://localhost:3000",
            public_key="test_pk",
            secret_key="test_sk",
        )
        assert client2._base_url == "http://localhost:3000"

        # Test with Sea Traces env var
        os.environ["SEA_TRACES_API_KEY"] = "team-test-key"
        os.environ["SEA_TRACES_BASE_URL"] = "http://localhost:3000"
        os.environ["SEA_TRACES_PROJECT_ID"] = "project-test-id"

        def resolve_credentials(**kwargs):
            assert kwargs["base_url"] == "http://localhost:3000"
            return SealangfuseCredentials(
                public_key="pk-localhost",
                secret_key="sk-localhost",
                base_url="http://resolved-localhost:3000",
            )

        monkeypatch.setattr(
            "langfuse._client.client.resolve_sealangfuse_credentials",
            resolve_credentials,
        )

        client3 = Langfuse()
        assert client3._base_url == "http://resolved-localhost:3000"

    def test_trailing_slash_handling(self, cleanup_env_vars):
        """Test that URLs with trailing slashes are handled correctly."""
        # URLs with trailing slashes should work
        client1 = Langfuse(
            api_key="team-test-key",
            base_url="http://test.com/",
            project_id="project-test-id",
            public_key="test_pk",
            secret_key="test_sk",
        )
        # The SDK should accept the URL as-is (API client will handle normalization)
        assert client1._base_url == "http://test.com/"

    def test_urls_with_paths(self, cleanup_env_vars):
        """Test that URLs with paths work correctly."""
        client = Langfuse(
            api_key="team-test-key",
            base_url="http://test.com/api/v1",
            project_id="project-test-id",
            public_key="test_pk",
            secret_key="test_sk",
        )
        assert client._base_url == "http://test.com/api/v1"

    def test_https_and_http_urls(self, cleanup_env_vars):
        """Test that both HTTPS and HTTP URLs work."""
        # HTTPS
        client1 = Langfuse(
            api_key="team-test-key",
            base_url="https://secure.com",
            project_id="project-test-id",
            public_key="test_pk",
            secret_key="test_sk",
        )
        assert client1._base_url == "https://secure.com"

        # HTTP
        client2 = Langfuse(
            api_key="team-test-key",
            base_url="http://insecure.com",
            project_id="project-test-id",
            public_key="test_pk",
            secret_key="test_sk",
        )
        assert client2._base_url == "http://insecure.com"

    def test_sealangfuse_api_key_resolves_credentials(
        self, cleanup_env_vars, monkeypatch
    ):
        """Test that legacy SEALANGFUSE_API_KEY no longer enables SDK."""
        os.environ["SEALANGFUSE_API_KEY"] = "sa-test-key"
        os.environ["SEA_TRACES_BASE_URL"] = "https://sea-traces.example.com"

        def resolve_credentials(**kwargs):
            raise AssertionError("Legacy SEALANGFUSE_API_KEY should not be resolved")

        monkeypatch.setattr(
            "langfuse._client.client.resolve_sealangfuse_credentials",
            resolve_credentials,
        )

        client = Langfuse()

        assert client._resources is None

    def test_sea_team_key_resolves_credentials(self, cleanup_env_vars, monkeypatch):
        """Test that SEA_TRACES_API_KEY resolves Langfuse credentials."""
        os.environ["SEA_TRACES_API_KEY"] = "team-test-key"
        os.environ["SEA_TRACES_BASE_URL"] = "https://sea-traces.example.com"
        os.environ["SEA_TRACES_PROJECT_ID"] = "project-test-id"

        def resolve_credentials(**kwargs):
            assert kwargs["api_key"] == "team-test-key"
            assert kwargs["base_url"] == "https://sea-traces.example.com"
            assert kwargs["project_id"] == "project-test-id"
            return SealangfuseCredentials(
                public_key="pk-resolved-team",
                secret_key="sk-resolved-team",
                base_url="https://resolved-team.example.com",
            )

        monkeypatch.setattr(
            "langfuse._client.client.resolve_sealangfuse_credentials",
            resolve_credentials,
        )

        client = Langfuse()

        # 上报地址使用 resolver 返回的 baseUrl,而非入参网关 base_url
        assert client._base_url == "https://resolved-team.example.com"
        assert (
            client.api._client_wrapper._base_url == "https://resolved-team.example.com"
        )
        assert client._project_id == "project-test-id"

    def test_gateway_credentials_override_incomplete_direct_credentials(
        self, cleanup_env_vars, monkeypatch
    ):
        """Test gateway auth does not mix stale direct credentials with resolved ones."""
        os.environ["SEATRACES_PUBLIC_KEY"] = "pk-stale-direct"
        os.environ["SEA_TRACES_API_KEY"] = "team-test-key"
        os.environ["SEA_TRACES_BASE_URL"] = "https://sea-traces.example.com"
        os.environ["SEA_TRACES_PROJECT_ID"] = "project-test-id"

        def resolve_credentials(**kwargs):
            return SealangfuseCredentials(
                public_key="pk-resolved-team",
                secret_key="sk-resolved-team",
                base_url="https://resolved-team.example.com",
            )

        monkeypatch.setattr(
            "langfuse._client.client.resolve_sealangfuse_credentials",
            resolve_credentials,
        )

        client = Langfuse()

        assert client.api._client_wrapper._username == "pk-resolved-team"
        assert client.api._client_wrapper._password == "sk-resolved-team"
        assert client._base_url == "https://resolved-team.example.com"

    def test_sea_team_key_takes_precedence_over_legacy_api_key_env(
        self, cleanup_env_vars, monkeypatch
    ):
        """Test that SEA_TRACES_API_KEY takes precedence over SEALANGFUSE_API_KEY."""
        os.environ["SEA_TRACES_API_KEY"] = "team-test-key"
        os.environ["SEALANGFUSE_API_KEY"] = "sa-legacy-key"
        os.environ["SEA_TRACES_BASE_URL"] = "https://sea-traces.example.com"
        os.environ["SEA_TRACES_PROJECT_ID"] = "project-test-id"

        def resolve_credentials(**kwargs):
            assert kwargs["api_key"] == "team-test-key"
            return SealangfuseCredentials(
                public_key="pk-resolved-team",
                secret_key="sk-resolved-team",
                base_url="https://resolved-team.example.com",
            )

        monkeypatch.setattr(
            "langfuse._client.client.resolve_sealangfuse_credentials",
            resolve_credentials,
        )

        client = Langfuse()

        assert client._base_url == "https://resolved-team.example.com"

    def test_sea_traces_base_url_used_for_credentials_url(
        self, cleanup_env_vars, monkeypatch
    ):
        """Test that SEA_TRACES_BASE_URL determines the default resolver endpoint."""
        os.environ["SEA_TRACES_API_KEY"] = "team-env-url-key"
        os.environ["SEA_TRACES_BASE_URL"] = "https://sea-traces.example.com/"
        os.environ["SEA_TRACES_PROJECT_ID"] = "project-test-id"

        def resolve_credentials(**kwargs):
            assert (
                kwargs["credentials_url"]
                == "https://sea-traces.example.com/hub/sea-traces-api-key"
            )
            return SealangfuseCredentials(
                public_key="pk-sea-traces-url",
                secret_key="sk-sea-traces-url",
                base_url="https://resolved-sea-traces.example.com",
            )

        monkeypatch.setattr(
            "langfuse._client.client.resolve_sealangfuse_credentials",
            resolve_credentials,
        )

        client = Langfuse()

        assert client._base_url == "https://resolved-sea-traces.example.com"

    def test_sealangfuse_api_key_parameter_resolves_credentials(
        self, cleanup_env_vars, monkeypatch
    ):
        """Test that the api_key parameter resolves Langfuse credentials."""
        httpx_client = httpx.Client()

        def resolve_credentials(**kwargs):
            assert kwargs["api_key"] == "sa-param-key"
            assert kwargs["httpx_client"] is httpx_client
            return SealangfuseCredentials(
                public_key="pk-resolved-param",
                secret_key="sk-resolved-param",
                base_url="https://resolved-param.example.com",
            )

        monkeypatch.setattr(
            "langfuse._client.client.resolve_sealangfuse_credentials",
            resolve_credentials,
        )

        client = Langfuse(
            api_key="sa-param-key",
            base_url="https://param.example.com",
            project_id="project-test-id",
            httpx_client=httpx_client,
        )

        # 上报地址使用 resolver 返回的 baseUrl
        assert client._base_url == "https://resolved-param.example.com"
        assert (
            client.api._client_wrapper._base_url == "https://resolved-param.example.com"
        )

    def test_explicit_credentials_skip_sealangfuse_resolution(
        self, cleanup_env_vars, monkeypatch
    ):
        """Test that explicit Langfuse credentials take precedence over api_key."""

        def resolve_credentials(**kwargs):
            raise AssertionError("Sealangfuse credentials should not be resolved")

        monkeypatch.setattr(
            "langfuse._client.client.resolve_sealangfuse_credentials",
            resolve_credentials,
        )

        client = Langfuse(
            public_key="pk-explicit",
            secret_key="sk-explicit",
            api_key="sa-unused",
            base_url="https://explicit.example.com",
        )

        # 显式传入 pk/sk 时跳过凭证解析,上报地址保持入参 base_url
        assert client._base_url == "https://explicit.example.com"
        assert client.api._client_wrapper._username == "pk-explicit"

    def test_direct_seatraces_env_credentials_skip_sea_traces_resolution(
        self, cleanup_env_vars, monkeypatch
    ):
        """Test internal direct Sea Traces env credentials do not need gateway config."""
        os.environ["SEATRACES_PUBLIC_KEY"] = "pk-env-direct"
        os.environ["SEATRACES_SECRET_KEY"] = "sk-env-direct"
        os.environ["SEATRACES_BASE_URL"] = "https://env-direct.example.com"

        def resolve_credentials(**kwargs):
            raise AssertionError("Sea Traces credentials should not be resolved")

        monkeypatch.setattr(
            "langfuse._client.client.resolve_sealangfuse_credentials",
            resolve_credentials,
        )

        client = Langfuse()

        assert client._base_url == "https://env-direct.example.com"
        assert client.api._client_wrapper._username == "pk-env-direct"

    def test_direct_seatraces_env_credentials_take_precedence_over_legacy_env(
        self, cleanup_env_vars, monkeypatch
    ):
        """Test Sea Traces direct env vars take precedence over legacy Langfuse env vars."""
        os.environ["SEATRACES_PUBLIC_KEY"] = "pk-seatraces"
        os.environ["SEATRACES_SECRET_KEY"] = "sk-seatraces"
        os.environ["SEATRACES_BASE_URL"] = "https://seatraces-direct.example.com"
        os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-legacy"
        os.environ["LANGFUSE_SECRET_KEY"] = "sk-legacy"
        os.environ["LANGFUSE_BASE_URL"] = "https://legacy-direct.example.com"

        def resolve_credentials(**kwargs):
            raise AssertionError(
                "Sea Traces gateway credentials should not be resolved"
            )

        monkeypatch.setattr(
            "langfuse._client.client.resolve_sealangfuse_credentials",
            resolve_credentials,
        )

        client = Langfuse()

        assert client._base_url == "https://seatraces-direct.example.com"
        assert client.api._client_wrapper._username == "pk-seatraces"

    def test_sealangfuse_resolution_uses_resolved_base_url_for_reporting(
        self, cleanup_env_vars, monkeypatch
    ):
        """Test that the resolved credentials baseUrl is used as the reporting base_url."""

        def resolve_credentials(**kwargs):
            assert kwargs["base_url"] == "https://explicit-url.example.com"
            assert kwargs["project_id"] == "project-test-id"
            return SealangfuseCredentials(
                public_key="pk-resolved-url",
                secret_key="sk-resolved-url",
                base_url="https://resolved-url.example.com",
            )

        monkeypatch.setattr(
            "langfuse._client.client.resolve_sealangfuse_credentials",
            resolve_credentials,
        )

        client = Langfuse(
            api_key="sa-url-key",
            base_url="https://explicit-url.example.com",
            project_id="project-test-id",
        )

        # 网关 base_url 仅用于鉴权请求,上报地址使用 resolver 返回的 baseUrl
        assert client._base_url == "https://resolved-url.example.com"

    def test_sealangfuse_resolution_uses_base_url_for_credentials_url(
        self, cleanup_env_vars, monkeypatch
    ):
        """Test that base_url determines the default Sealangfuse resolver endpoint."""

        def resolve_credentials(**kwargs):
            assert (
                kwargs["credentials_url"]
                == "https://env.example.com/hub/sea-traces-api-key"
            )
            return SealangfuseCredentials(
                public_key="pk-env-url",
                secret_key="sk-env-url",
                base_url="https://resolved-env.example.com",
            )

        monkeypatch.setattr(
            "langfuse._client.client.resolve_sealangfuse_credentials",
            resolve_credentials,
        )

        client = Langfuse(
            api_key="sa-env-url-key",
            base_url="https://env.example.com/",
            project_id="project-test-id",
        )

        assert client._base_url == "https://resolved-env.example.com"

    def test_failed_sealangfuse_resolution_disables_client(
        self, cleanup_env_vars, monkeypatch
    ):
        """Test that failed Sealangfuse credential resolution disables the client."""

        def resolve_credentials(**kwargs):
            raise RuntimeError("resolver unavailable")

        monkeypatch.setattr(
            "langfuse._client.client.resolve_sealangfuse_credentials",
            resolve_credentials,
        )

        client = Langfuse(
            api_key="sa-bad-key",
            base_url="https://sea-traces.example.com",
            project_id="project-test-id",
        )

        assert client._resources is None

    def test_missing_project_id_disables_client(self, cleanup_env_vars):
        """Test that SDK is disabled when SEA_TRACES_PROJECT_ID is absent."""
        os.environ["SEA_TRACES_API_KEY"] = "team-test-key"
        os.environ["SEA_TRACES_BASE_URL"] = "https://sea-traces.example.com"

        client = Langfuse(
            public_key="test_pk",
            secret_key="test_sk",
        )

        assert client._resources is None

    def test_project_id_param_sets_project_id(self, cleanup_env_vars, monkeypatch):
        """Test that the project_id parameter is applied without a network lookup."""

        def resolve_credentials(**kwargs):
            assert kwargs["project_id"] == "param-project-id"
            return SealangfuseCredentials(
                public_key="pk-project",
                secret_key="sk-project",
                base_url="https://resolved-project.example.com",
            )

        monkeypatch.setattr(
            "langfuse._client.client.resolve_sealangfuse_credentials",
            resolve_credentials,
        )

        client = Langfuse(
            api_key="sa-project-key",
            base_url="https://param.example.com",
            project_id="param-project-id",
        )

        assert client._project_id == "param-project-id"
