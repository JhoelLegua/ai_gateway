"""
Unit & integration tests for Telescope Observability & Stress-Lab endpoints.
"""

from fastapi.testclient import TestClient
from app.core.metrics import metrics_collector


class TestTelescopeMetricsCollector:
    """Unit tests for the thread-safe in-memory MetricsCollector."""

    def test_record_request_and_clean(self):
        metrics_collector.record_request()
        metrics_collector.record_clean()
        assert metrics_collector.total_requests >= 1
        assert metrics_collector.clean_passed >= 1

    def test_record_layer_percentiles(self):
        # Record sample latencies
        for lat in [10.0, 20.0, 30.0, 40.0, 50.0]:
            metrics_collector.record_layer("layer_1_heuristics", lat, blocked=False)
        stats = metrics_collector.get_layer_stats()
        l1 = next(l for l in stats if l["layer_name"] == "layer_1_heuristics")
        assert l1["invocations"] >= 5
        assert l1["p50_ms"] > 0
        assert l1["max_ms"] >= 50.0

    def test_record_http_status(self):
        metrics_collector.record_http_status(200)
        metrics_collector.record_http_status(400)
        metrics_collector.record_http_status(500)
        counts = metrics_collector.get_http_status_counts()
        assert counts[200] >= 1
        assert counts[400] >= 1
        assert counts[500] >= 1

    def test_record_request_event_rolling_log(self):
        metrics_collector.record_request_event(
            user_id="usr_test",
            session_id="ses_test",
            total_ms=45.2,
            http_status=200,
            blocked=False,
            blocked_layer=None,
        )
        history = metrics_collector.get_request_log(limit=10)
        assert len(history) >= 1
        assert history[0]["user_id"] == "usr_test"
        assert history[0]["http_status"] == 200


class TestTelescopeEndpoints:
    """Integration tests for the /v1/telescope HTTP routes."""

    def test_get_metrics_returns_200(self, client: TestClient):
        response = client.get("/v1/telescope/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "uptime_s" in data
        assert "total_requests" in data
        assert "layers" in data
        assert "http_status_counts" in data
        assert isinstance(data["layers"], list)

    def test_get_history_returns_200(self, client: TestClient):
        response = client.get("/v1/telescope/history?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert isinstance(data["events"], list)

    def test_get_stress_status_returns_200(self, client: TestClient):
        response = client.get("/v1/telescope/stress/status")
        assert response.status_code == 200
        data = response.json()
        assert "running" in data
        assert "total" in data
        assert "progress" in data

    def test_stress_stop_endpoint(self, client: TestClient):
        stop_resp = client.post("/v1/telescope/stress/stop")
        assert stop_resp.status_code == 200
        data = stop_resp.json()
        assert data["status"] in ["stop_requested", "no_job_running"]

    def test_stress_run_endpoint(self, client: TestClient):
        # Stop any existing job first
        client.post("/v1/telescope/stress/stop")
        run_resp = client.post("/v1/telescope/stress/run", json={
            "users": 2,
            "interval_ms": 100,
            "iterations": 1,
            "traffic_mix": {"clean": 0.5, "injection": 0.5},
            "token": "test",
        })
        assert run_resp.status_code in [202, 409]
        if run_resp.status_code == 202:
            assert run_resp.json()["status"] == "started"
            # Clean up by stopping
            client.post("/v1/telescope/stress/stop")
