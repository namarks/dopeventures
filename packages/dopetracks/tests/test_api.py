"""
Tests for FastAPI endpoints defined in dopetracks.app.

Uses FastAPI's TestClient to exercise HTTP endpoints with mocked
dependencies (database, file system, settings).
"""
import os
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Build a lightweight test app that mirrors the real routes but skips the
# heavy lifespan (database init, periodic refresh, etc.).
# ---------------------------------------------------------------------------


def _build_test_app():
    """
    Build a clean FastAPI app with the real route handlers but no lifespan
    side-effects (database init, periodic refresh, etc.).
    """
    from dopetracks.routes import (
        spotify_router,
        chats_router,
        playlists_router,
        fts_router,
        system_router,
    )

    app = FastAPI()
    app.include_router(system_router)
    app.include_router(spotify_router)
    app.include_router(chats_router)
    app.include_router(playlists_router)
    app.include_router(fts_router)
    return app


@pytest.fixture(scope="module")
def test_app():
    """Module-scoped FastAPI app with mocked dependencies."""
    app = _build_test_app()
    return app


@pytest.fixture(scope="module")
def client(test_app):
    """Module-scoped TestClient."""
    with TestClient(test_app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------


class TestRootEndpoint:
    """Tests for GET /."""

    def test_root_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_root_contains_api_name(self, client):
        data = client.get("/").json()
        assert "name" in data
        assert "Dopetracks" in data["name"]

    def test_root_contains_version(self, client):
        data = client.get("/").json()
        assert "version" in data

    def test_root_contains_health_link(self, client):
        data = client.get("/").json()
        assert data.get("health") == "/health"


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_contains_status(self, client):
        data = client.get("/health").json()
        assert "status" in data

    def test_health_reports_environment(self, client):
        data = client.get("/health").json()
        assert data.get("environment") == "local"

    def test_health_contains_version(self, client):
        data = client.get("/health").json()
        assert "version" in data

    def test_health_contains_database_field(self, client):
        data = client.get("/health").json()
        assert "database" in data

    def test_health_contains_messages_db_field(self, client):
        data = client.get("/health").json()
        assert "messages_db" in data


# ---------------------------------------------------------------------------
# Get Client ID endpoint
# ---------------------------------------------------------------------------


class TestGetClientIdEndpoint:
    """Tests for GET /get-client-id."""

    def test_returns_client_id_when_configured(self, client):
        """When SPOTIFY_CLIENT_ID is set, endpoint should return it."""
        from dopetracks.config import Settings

        original_id = Settings.SPOTIFY_CLIENT_ID
        original_uri = Settings.SPOTIFY_REDIRECT_URI
        try:
            Settings.SPOTIFY_CLIENT_ID = "test_client_id_123"
            Settings.SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"
            response = client.get("/get-client-id")
            assert response.status_code == 200
            data = response.json()
            assert data["client_id"] == "test_client_id_123"
            assert "redirect_uri" in data
        finally:
            Settings.SPOTIFY_CLIENT_ID = original_id
            Settings.SPOTIFY_REDIRECT_URI = original_uri

    def test_returns_500_when_client_id_missing(self, client):
        """When SPOTIFY_CLIENT_ID is empty, should return 500."""
        from dopetracks.config import Settings

        original_id = Settings.SPOTIFY_CLIENT_ID
        try:
            Settings.SPOTIFY_CLIENT_ID = ""
            response = client.get("/get-client-id")
            assert response.status_code == 500
            assert "not configured" in response.json()["detail"]
        finally:
            Settings.SPOTIFY_CLIENT_ID = original_id

    def test_redirect_uri_returned(self, client):
        """Response should include the redirect_uri."""
        from dopetracks.config import Settings

        original_id = Settings.SPOTIFY_CLIENT_ID
        original_uri = Settings.SPOTIFY_REDIRECT_URI
        try:
            Settings.SPOTIFY_CLIENT_ID = "test_id"
            Settings.SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"
            response = client.get("/get-client-id")
            data = response.json()
            assert "127.0.0.1" in data["redirect_uri"]
        finally:
            Settings.SPOTIFY_CLIENT_ID = original_id
            Settings.SPOTIFY_REDIRECT_URI = original_uri

    def test_returns_oauth_state_token(self, client):
        """Response should include a state token for CSRF protection."""
        from dopetracks.config import Settings

        original_id = Settings.SPOTIFY_CLIENT_ID
        original_uri = Settings.SPOTIFY_REDIRECT_URI
        try:
            Settings.SPOTIFY_CLIENT_ID = "test_id"
            Settings.SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"
            response = client.get("/get-client-id")
            data = response.json()
            assert "state" in data
            assert len(data["state"]) > 20  # cryptographic token, not trivial
        finally:
            Settings.SPOTIFY_CLIENT_ID = original_id
            Settings.SPOTIFY_REDIRECT_URI = original_uri

    def test_returns_pkce_challenge(self, client):
        """Response should include PKCE code_challenge and method."""
        from dopetracks.config import Settings

        original_id = Settings.SPOTIFY_CLIENT_ID
        original_uri = Settings.SPOTIFY_REDIRECT_URI
        try:
            Settings.SPOTIFY_CLIENT_ID = "test_id"
            Settings.SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"
            response = client.get("/get-client-id")
            data = response.json()
            assert "code_challenge" in data
            assert data["code_challenge_method"] == "S256"
        finally:
            Settings.SPOTIFY_CLIENT_ID = original_id
            Settings.SPOTIFY_REDIRECT_URI = original_uri


# ---------------------------------------------------------------------------
# OAuth callback state validation
# ---------------------------------------------------------------------------


class TestOAuthCallbackValidation:
    """Tests for CSRF state validation on GET /callback."""

    def test_callback_rejects_missing_state(self, client):
        """Callback should reject requests with no state parameter."""
        response = client.get("/callback", params={"code": "test_code"})
        assert response.status_code == 400
        assert "state" in response.json().get("detail", "").lower()

    def test_callback_rejects_wrong_state(self, client):
        """Callback should reject requests with mismatched state."""
        from dopetracks.config import Settings

        original_id = Settings.SPOTIFY_CLIENT_ID
        original_uri = Settings.SPOTIFY_REDIRECT_URI
        try:
            Settings.SPOTIFY_CLIENT_ID = "test_id"
            Settings.SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"
            # First, get a valid state token
            client.get("/get-client-id")
            # Then try callback with wrong state
            response = client.get("/callback", params={"code": "test_code", "state": "wrong_state"})
            assert response.status_code == 400
            assert "state" in response.json().get("detail", "").lower()
        finally:
            Settings.SPOTIFY_CLIENT_ID = original_id
            Settings.SPOTIFY_REDIRECT_URI = original_uri


# ---------------------------------------------------------------------------
# Validate username endpoint (path traversal protection)
# ---------------------------------------------------------------------------


class TestValidateUsernameEndpoint:
    """Tests for GET /validate-username path traversal protection."""

    def test_rejects_path_traversal(self, client):
        """Should reject usernames containing path traversal characters."""
        response = client.get("/validate-username", params={"username": "../../../etc/passwd"})
        assert response.status_code == 400

    def test_rejects_slashes(self, client):
        """Should reject usernames containing slashes."""
        response = client.get("/validate-username", params={"username": "foo/bar"})
        assert response.status_code == 400

    def test_rejects_dots(self, client):
        """Should reject usernames containing dots."""
        response = client.get("/validate-username", params={"username": "foo.bar"})
        assert response.status_code == 400

    def test_accepts_valid_username(self, client):
        """Should accept valid alphanumeric usernames with hyphens/underscores."""
        response = client.get("/validate-username", params={"username": "valid-user_name123"})
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Prepared status endpoint
# ---------------------------------------------------------------------------


class TestPreparedStatusEndpoint:
    """Tests for GET /prepared-status."""

    def test_returns_200(self, client):
        response = client.get("/prepared-status")
        assert response.status_code == 200

    def test_contains_expected_fields(self, client):
        data = client.get("/prepared-status").json()
        assert "prepared_db_path" in data
        assert "staleness_seconds" in data


# ---------------------------------------------------------------------------
# Error handling for unknown routes
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for error responses."""

    def test_unknown_route_returns_404(self, client):
        response = client.get("/nonexistent-endpoint")
        assert response.status_code == 404

    def test_404_response_is_json(self, client):
        response = client.get("/nonexistent-endpoint")
        assert response.headers["content-type"].startswith("application/json")
