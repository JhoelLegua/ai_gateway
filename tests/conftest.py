"""
Shared pytest fixtures and mock setup for AI Gateway Perimetral test suite.
"""

from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    """
    Creates a shared TestClient with mocked external dependencies (ChromaDB & LLM)
    so tests run fast and isolated without network calls or external disk I/O.
    """
    with (
        patch("app.services.vector_db.VectorDBService.initialize"),
        patch(
            "app.services.vector_db.VectorDBService.search_similar_attack",
            return_value=(False, 0.9, "irrelevant text"),
        ),
        patch(
            "app.services.vector_db.VectorDBService.get_signature_count",
            return_value=20,
        ),
        patch("app.core.pipeline.layer_3_intelligence.load_model"),
        patch("app.services.llm_client.LLMClientService.initialize"),
        patch(
            "app.services.llm_client.LLMClientService.complete",
            new_callable=AsyncMock,
            return_value="Your account balance is displayed in the Accounts section.",
        ),
    ):
        with TestClient(app) as test_client:
            yield test_client
