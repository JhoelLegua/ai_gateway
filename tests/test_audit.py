"""
Unit & integration tests for Audit Dataset & HITL review API.
"""

from fastapi.testclient import TestClient


class TestAuditRBAC:
    """Tests for Admin Token authentication on audit routes."""

    def test_missing_admin_token_returns_403(self, client: TestClient):
        response = client.get("/v1/audit/records")
        assert response.status_code in [401, 403]

    def test_invalid_admin_token_returns_403(self, client: TestClient):
        response = client.get(
            "/v1/audit/records",
            headers={"Authorization": "Bearer bad_token"}
        )
        assert response.status_code in [401, 403]

    def test_records_endpoint_with_admin_token(self, client: TestClient):
        response = client.get(
            "/v1/audit/records",
            headers={"Authorization": "Bearer admin123"}
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_export_seed_with_admin_token(self, client: TestClient):
        response = client.get(
            "/v1/audit/export/seed",
            headers={"Authorization": "Bearer admin123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_exported" in data
        assert "entries" in data
        assert isinstance(data["entries"], list)
