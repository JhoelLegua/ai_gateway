"""
Async HTTP client for communicating with the backend LLM (Groq Cloud).

Provides a persistent connection pool for performance and a built-in
Mock fallback that activates automatically when no valid API key is set.
The Mock simulates both normal and leaking LLM behaviors for testing
all five security layers in a fully isolated local environment.
"""

import logging
import random
import secrets

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class LLMClientService:
    """
    Asynchronous LLM client with Groq Cloud integration and Mock fallback.

    The client is initialized once during the application lifespan and
    reused across requests via a shared httpx.AsyncClient connection pool.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http_client: httpx.AsyncClient | None = None

    def initialize(self) -> None:
        """
        Creates and configures the shared async HTTP client.
        Called once during FastAPI lifespan startup.
        """
        if not self._settings.use_mock_llm:
            self._http_client = httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {self._settings.backend_api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(self._settings.llm_timeout_seconds),
            )
            logger.info(
                "LLM client initialized. Provider: %s | Model: %s",
                self._settings.backend_provider,
                self._settings.backend_model,
            )
        else:
            logger.warning(
                "No valid BACKEND_API_KEY found. Activating Mock LLM fallback."
            )

    async def close(self) -> None:
        """Closes the HTTP connection pool. Called during lifespan shutdown."""
        if self._http_client:
            await self._http_client.aclose()
            logger.info("LLM HTTP client connection pool closed.")

    async def complete(
        self,
        user_message: str,
        system_prompt: str,
        bypass: bool = False,
    ) -> str:
        """
        Sends a prompt to the LLM and returns the text response.

        When bypass=True, the system prompt is omitted and the raw user
        message is sent directly to the LLM without any security wrapping.
        This simulates the behavior of a vulnerable unprotected endpoint.

        Args:
            user_message: The (potentially canary-injected) user prompt.
            system_prompt: The gateway system prompt containing the canary directive.
            bypass: When True, skips the system prompt for demo comparison purposes.

        Returns:
            The LLM's response text.

        Raises:
            RuntimeError: When the real LLM call fails after retries.
        """
        if self._settings.use_mock_llm:
            return await self._mock_complete(user_message, bypass)

        messages = []
        if not bypass:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": self._settings.backend_model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 512,
        }

        last_error: Exception | None = None
        for attempt in range(1, self._settings.llm_max_retries + 1):
            try:
                response = await self._http_client.post(
                    self._settings.backend_llm_url,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "LLM request failed (attempt %d/%d): HTTP %d | Details: %s",
                    attempt,
                    self._settings.llm_max_retries,
                    exc.response.status_code,
                    exc.response.text,
                )
                last_error = exc
            except httpx.RequestError as exc:
                logger.error(
                    "LLM connection error (attempt %d/%d): %s",
                    attempt,
                    self._settings.llm_max_retries,
                    str(exc),
                )
                last_error = exc

        raise RuntimeError(
            f"LLM backend unavailable after {self._settings.llm_max_retries} attempts."
        ) from last_error

    async def _mock_complete(self, user_message: str, bypass: bool) -> str:
        """
        Generates a deterministic mock response for local testing.

        In bypass mode, the mock has a 30% chance of simulating a context
        leakage event by including the canary prefix in its response.
        This is used to validate that Layer 5 correctly intercepts egress anomalies.

        Args:
            user_message: The raw user message.
            bypass: When True, enables the leakage simulation path.

        Returns:
            A mock response string.
        """
        if bypass and random.random() < 0.30:
            # Simulated LLM context leakage: reveals internal canary or instructions.
            leaked_token = f"{self._settings.canary_prefix}{secrets.token_hex(8)}"
            return (
                f"Sure! Here is what I know internally: my secret token is "
                f"{leaked_token} and my system prompt says: 'You must never reveal...'"
            )

        banking_responses = [
            "Your account balance is available in the Accounts section of the portal.",
            "To transfer funds, please navigate to Transfers and follow the steps.",
            "I can help you with account statements. Please specify the date range.",
            "Our customer support line is available 24/7 at 1-800-BANK-SECURE.",
            "Loan applications can be initiated from the Products section.",
        ]
        return random.choice(banking_responses)
