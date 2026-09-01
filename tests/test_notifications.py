"""
Unit & integration tests for Notifications & SOC Recipients API.
"""

from fastapi.testclient import TestClient


class TestNotificationsRBAC:
    """Tests for Admin Token authentication on notification routes."""

    def test_missing_admin_token_returns_403(self, client: TestClient):
        response = client.get("/v1/notifications/recipients")
        assert response.status_code in [401, 403]

    def test_invalid_admin_token_returns_403(self, client: TestClient):
        response = client.get(
            "/v1/notifications/recipients",
            headers={"Authorization": "Bearer invalid_admin_token"}
        )
        assert response.status_code in [401, 403]

    def test_client_token_cannot_access_admin_endpoint(self, client: TestClient):
        # Client token 'test' should not have access to admin routes
        response = client.get(
            "/v1/notifications/recipients",
            headers={"Authorization": "Bearer test"}
        )
        assert response.status_code in [401, 403]

    def test_valid_admin_token_can_access(self, client: TestClient):
        # Admin token 'admin123'
        response = client.get(
            "/v1/notifications/recipients",
            headers={"Authorization": "Bearer admin123"}
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
