"""Test suite for Langfuse client initialization with Sea Traces configuration.

This test suite verifies that SEA_TEAM_KEY and SEA_TRACES_BASE_URL are required
for initializing the Sea Traces SDK.
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
            "SEA_TEAM_KEY": os.environ.get("SEA_TEAM_KEY"),
            "SEA_TRACES_BASE_URL": os.environ.get("SEA_TRACES_BASE_URL"),
            "SEALANGFUSE_API_KEY": os.environ.get("SEALANGFUSE_API_KEY"),
            "SEALANGFUSE_CREDENTIALS_URL": os.environ.get(
                "SEALANGFUSE_CREDENTIALS_URL"
            ),
        }

        # Remove URL and Sea Traces auth env vars for the test
        # but keep PUBLIC_KEY and SECRET_KEY if they exist
        for key in [
            "LANGFUSE_BASE_URL",
            "LANGFUSE_HOST",
            "SEA_TEAM_KEY",
            "SEA_TRACES_BASE_URL",
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
            "SEA_TEAM_KEY",
            "SEA_TRACES_BASE_URL",
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
        os.environ["SEA_TEAM_KEY"] = "team-test-key"

        client = Langfuse(
            base_url="http://param-base-url.com",
            public_key="test_pk",
            secret_key="test_sk",
        )

        assert client._base_url == "http://param-base-url.com"

    def test_legacy_base_url_cannot_replace_sea_traces_base_url(self, cleanup_env_vars):
        """Test that LANGFUSE_BASE_URL cannot replace required SEA_TRACES_BASE_URL."""
        os.environ["SEA_TEAM_KEY"] = "team-test-key"
        os.environ["LANGFUSE_BASE_URL"] = "http://env-base-url.com"

        client = Langfuse(
            public_key="test_pk",
            secret_key="test_sk",
        )

        assert client._resources is None

    def test_host_parameter_cannot_replace_sea_traces_base_url(self, cleanup_env_vars):
        """Test that host cannot replace required SEA_TRACES_BASE_URL."""
        os.environ["SEA_TEAM_KEY"] = "team-test-key"
        client = Langfuse(
            host="http://param-host.com",
            public_key="test_pk",
            secret_key="test_sk",
        )

        assert client._resources is None

    def test_env_host_cannot_replace_sea_traces_base_url(self, cleanup_env_vars):
        """Test that LANGFUSE_HOST cannot replace required SEA_TRACES_BASE_URL."""
        os.environ["SEA_TEAM_KEY"] = "team-test-key"
        os.environ["LANGFUSE_HOST"] = "http://env-host.com"

        client = Langfuse(
            public_key="test_pk",
            secret_key="test_sk",
        )

        assert client._resources is None

    def test_missing_required_sea_traces_config_disables_client(self, cleanup_env_vars):
        """Test that SDK is disabled when Sea Traces credentials are absent."""
        client = Langfuse(
            public_key="test_pk",
            secret_key="test_sk",
        )

        assert client._resources is None

    def test_empty_required_sea_traces_config_disables_client(self, cleanup_env_vars):
        """Test that empty Sea Traces config values are treated as missing."""
        os.environ["SEA_TEAM_KEY"] = ""
        os.environ["SEA_TRACES_BASE_URL"] = "   "

        client = Langfuse(
            public_key="test_pk",
            secret_key="test_sk",
        )

        assert client._resources is None

    def test_legacy_base_url_with_missing_team_key_disables_client(
        self, cleanup_env_vars
    ):
        """Test that LANGFUSE_BASE_URL cannot replace required SEA_TEAM_KEY."""
        os.environ["LANGFUSE_BASE_URL"] = "http://test-base-url.com"

        client = Langfuse(
            public_key="test_pk",
            secret_key="test_sk",
        )

        assert client._resources is None

    def test_sea_traces_base_url_env_var(self, cleanup_env_vars):
        """Test that SEA_TRACES_BASE_URL environment variable is used correctly."""
        os.environ["SEA_TEAM_KEY"] = "team-test-key"
        os.environ["SEA_TRACES_BASE_URL"] = "http://sea-traces-base-url.com"

        client = Langfuse(
            public_key="test_pk",
            secret_key="test_sk",
        )

        assert client._base_url == "http://sea-traces-base-url.com"

    def test_sea_traces_base_url_takes_precedence_over_legacy_env(
        self, cleanup_env_vars
    ):
        """Test that SEA_TRACES_BASE_URL takes precedence over LANGFUSE_BASE_URL."""
        os.environ["SEA_TEAM_KEY"] = "team-test-key"
        os.environ["SEA_TRACES_BASE_URL"] = "http://sea-traces-base-url.com"
        os.environ["LANGFUSE_BASE_URL"] = "http://legacy-base-url.com"

        client = Langfuse(
            public_key="test_pk",
            secret_key="test_sk",
        )

        assert client._base_url == "http://sea-traces-base-url.com"

    def test_host_env_var_cannot_replace_required_config(self, cleanup_env_vars):
        """Test that LANGFUSE_HOST cannot enable SDK without Sea Traces config."""
        os.environ["LANGFUSE_HOST"] = "http://test-host.com"

        client = Langfuse(
            public_key="test_pk",
            secret_key="test_sk",
        )

        assert client._resources is None

    def test_base_url_parameter(self, cleanup_env_vars):
        """Test that base_url parameter is used correctly."""
        client = Langfuse(
            api_key="team-test-key",
            base_url="http://param-base-url.com",
            public_key="test_pk",
            secret_key="test_sk",
        )

        assert client._base_url == "http://param-base-url.com"

    def test_precedence_order_all_set(self, cleanup_env_vars):
        """Test complete precedence order for Sea Traces base URL."""
        os.environ["SEA_TEAM_KEY"] = "team-test-key"
        os.environ["SEA_TRACES_BASE_URL"] = "http://sea-env-base-url.com"
        os.environ["LANGFUSE_BASE_URL"] = "http://env-base-url.com"
        os.environ["LANGFUSE_HOST"] = "http://env-host.com"

        # Case 1: base_url parameter wins
        client1 = Langfuse(
            base_url="http://param-base-url.com",
            host="http://param-host.com",
            public_key="test_pk",
            secret_key="test_sk",
        )
        assert client1._base_url == "http://param-base-url.com"

        # Case 2: SEA_TRACES_BASE_URL env var wins when base_url param not set
        client2 = Langfuse(
            public_key="test_pk",
            secret_key="test_sk",
        )
        assert client2._base_url == "http://sea-env-base-url.com"

    def test_precedence_without_base_url(self, cleanup_env_vars):
        """Test that no legacy fallback is used without SEA_TRACES_BASE_URL."""
        os.environ["SEA_TEAM_KEY"] = "team-test-key"
        os.environ["LANGFUSE_HOST"] = "http://env-host.com"

        client1 = Langfuse(
            host="http://param-host.com",
            public_key="test_pk",
            secret_key="test_sk",
        )
        assert client1._resources is None

        client2 = Langfuse(
            public_key="test_pk",
            secret_key="test_sk",
        )
        assert client2._resources is None

    def test_url_used_in_api_client(self, cleanup_env_vars):
        """Test that the resolved base_url is correctly passed to API clients."""
        test_url = "http://test-unique-api.com"
        # Use a unique public key to avoid singleton conflicts
        client = Langfuse(
            api_key="team-test-key",
            base_url=test_url,
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
            host="http://host.com",
            public_key="test_pk",
            secret_key="test_sk",
        )

        assert client._base_url == "http://base-url.com"

    def test_both_env_vars_set(self, cleanup_env_vars):
        """Test that legacy env vars do not enable SDK without Sea Traces config."""
        os.environ["LANGFUSE_BASE_URL"] = "http://base-url.com"
        os.environ["LANGFUSE_HOST"] = "http://host.com"

        client = Langfuse(
            public_key="test_pk",
            secret_key="test_sk",
        )

        assert client._resources is None

    def test_localhost_urls(self, cleanup_env_vars):
        """Test that localhost URLs work correctly."""
        # Test with base_url
        client1 = Langfuse(
            api_key="team-test-key",
            base_url="http://localhost:3000",
            public_key="test_pk",
            secret_key="test_sk",
        )
        assert client1._base_url == "http://localhost:3000"

        # Test with host (deprecated) cannot replace required Sea Traces base URL
        client2 = Langfuse(
            api_key="team-test-key",
            host="http://localhost:3000",
            public_key="test_pk",
            secret_key="test_sk",
        )
        assert client2._resources is None

        # Test with Sea Traces env var
        os.environ["SEA_TEAM_KEY"] = "team-test-key"
        os.environ["SEA_TRACES_BASE_URL"] = "http://localhost:3000"
        client3 = Langfuse(
            public_key="test_pk",
            secret_key="test_sk",
        )
        assert client3._base_url == "http://localhost:3000"

    def test_trailing_slash_handling(self, cleanup_env_vars):
        """Test that URLs with trailing slashes are handled correctly."""
        # URLs with trailing slashes should work
        client1 = Langfuse(
            api_key="team-test-key",
            base_url="http://test.com/",
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
            public_key="test_pk",
            secret_key="test_sk",
        )
        assert client1._base_url == "https://secure.com"

        # HTTP
        client2 = Langfuse(
            api_key="team-test-key",
            base_url="http://insecure.com",
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
        """Test that SEA_TEAM_KEY resolves Langfuse credentials."""
        os.environ["SEA_TEAM_KEY"] = "team-test-key"
        os.environ["SEA_TRACES_BASE_URL"] = "https://sea-traces.example.com"

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

        assert client._base_url == "https://sea-traces.example.com"
        assert client.api._client_wrapper._base_url == "https://sea-traces.example.com"

    def test_sea_team_key_takes_precedence_over_legacy_api_key_env(
        self, cleanup_env_vars, monkeypatch
    ):
        """Test that SEA_TEAM_KEY takes precedence over SEALANGFUSE_API_KEY."""
        os.environ["SEA_TEAM_KEY"] = "team-test-key"
        os.environ["SEALANGFUSE_API_KEY"] = "sa-legacy-key"
        os.environ["SEA_TRACES_BASE_URL"] = "https://sea-traces.example.com"

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

        assert client._base_url == "https://sea-traces.example.com"

    def test_sea_traces_base_url_used_for_credentials_url(
        self, cleanup_env_vars, monkeypatch
    ):
        """Test that SEA_TRACES_BASE_URL determines the default resolver endpoint."""
        os.environ["SEA_TEAM_KEY"] = "team-env-url-key"
        os.environ["SEA_TRACES_BASE_URL"] = "https://sea-traces.example.com/"

        def resolve_credentials(**kwargs):
            assert (
                kwargs["credentials_url"]
                == "https://sea-traces.example.com/api/public/sea-project-api-credentials"
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

        assert client._base_url == "https://sea-traces.example.com/"

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
            httpx_client=httpx_client,
        )

        assert client._base_url == "https://param.example.com"
        assert client.api._client_wrapper._base_url == "https://param.example.com"

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

        assert client._base_url == "https://explicit.example.com"
        assert client.api._client_wrapper._username == "pk-explicit"

    def test_sealangfuse_resolution_keeps_explicit_base_url(
        self, cleanup_env_vars, monkeypatch
    ):
        """Test that explicit base_url is not overwritten by resolved credentials."""

        def resolve_credentials(**kwargs):
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
        )

        assert client._base_url == "https://explicit-url.example.com"

    def test_sealangfuse_resolution_uses_base_url_for_credentials_url(
        self, cleanup_env_vars, monkeypatch
    ):
        """Test that base_url determines the default Sealangfuse resolver endpoint."""

        def resolve_credentials(**kwargs):
            assert (
                kwargs["credentials_url"]
                == "https://env.example.com/api/public/sea-project-api-credentials"
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
        )

        assert client._base_url == "https://env.example.com/"

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
        )

        assert client._resources is None
