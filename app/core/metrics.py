"""
Thread-safe in-memory metrics collector for the AI Gateway Perimetral.

Tracks request counts, per-layer latency samples and HTTP status codes.
Designed as a singleton loaded during the application lifespan.

Extended for Telescope:
    - P50 / P95 / Max latency percentiles per layer (deque, cap 10 000).
    - Global HTTP status-code histogram (200 / 400 / 500).
    - Rolling request event log (last 200 entries) for the live feed.
"""

import statistics
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque


# ---------------------------------------------------------------------------
# Per-layer counter
# ---------------------------------------------------------------------------
@dataclass
class LayerCounter:
    """Atomic counters, latency accumulator, and sample deque for one layer."""

    name: str
    blocked: int = 0
    total_latency_ms: float = 0.0
    invocations: int = 0
    # Rolling window of individual latency samples for percentile computation.
    # Capped at 10 000 to bound memory usage.
    _samples: Deque[float] = field(default_factory=lambda: deque(maxlen=10_000))

    def record(self, latency_ms: float, blocked: bool) -> None:
        """Records a single layer invocation result."""
        self.invocations += 1
        self.total_latency_ms += latency_ms
        self._samples.append(latency_ms)
        if blocked:
            self.blocked += 1

    # ------------------------------------------------------------------
    # Aggregated properties
    # ------------------------------------------------------------------
    @property
    def avg_latency_ms(self) -> float:
        """Average latency across all invocations."""
        if self.invocations == 0:
            return 0.0
        return round(self.total_latency_ms / self.invocations, 2)

    @property
    def p50_ms(self) -> float:
        """Median (P50) latency in ms."""
        if not self._samples:
            return 0.0
        return round(statistics.median(self._samples), 2)

    @property
    def p95_ms(self) -> float:
        """95th-percentile latency in ms."""
        s = sorted(self._samples)
        if not s:
            return 0.0
        idx = max(int(len(s) * 0.95) - 1, 0)
        return round(s[idx], 2)

    @property
    def max_ms(self) -> float:
        """Maximum observed latency in ms."""
        if not self._samples:
            return 0.0
        return round(max(self._samples), 2)

    def reset(self) -> None:
        """Resets all counters and samples."""
        self.blocked = 0
        self.total_latency_ms = 0.0
        self.invocations = 0
        self._samples.clear()


# ---------------------------------------------------------------------------
# Global collector
# ---------------------------------------------------------------------------
class MetricsCollector:
    """
    Singleton-friendly, thread-safe collector for gateway-wide metrics.

    All write operations are protected by a reentrant lock to ensure
    correctness under concurrent async requests handled by Uvicorn workers.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._start_time: float = time.monotonic()
        self._total_requests: int = 0
        self._clean_passed: int = 0

        # One counter per security layer.
        self._layers: dict[str, LayerCounter] = {
            "layer_1_heuristics": LayerCounter(name="layer_1_heuristics"),
            "layer_2_vectorial": LayerCounter(name="layer_2_vectorial"),
            "layer_3_intelligence": LayerCounter(name="layer_3_intelligence"),
            "layer_5_egress": LayerCounter(name="layer_5_egress"),
        }

        # HTTP status-code histogram (Telescope).
        self._http_status_counts: dict[int, int] = {200: 0, 400: 0, 500: 0}

        # Rolling request event log — last 200 events (Telescope live feed).
        self._request_log: Deque[dict] = deque(maxlen=200)

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------
    def record_request(self) -> None:
        """Increments the global request counter."""
        with self._lock:
            self._total_requests += 1

    def record_clean(self) -> None:
        """Increments the counter for requests that passed all layers cleanly."""
        with self._lock:
            self._clean_passed += 1

    def record_layer(
        self, layer_name: str, latency_ms: float, blocked: bool
    ) -> None:
        """
        Records the result of a single layer invocation.

        Args:
            layer_name: Identifier matching one of the keys in self._layers.
            latency_ms: Time spent in the layer in milliseconds.
            blocked: True if the layer blocked the request.
        """
        with self._lock:
            if layer_name in self._layers:
                self._layers[layer_name].record(latency_ms, blocked)

    def record_http_status(self, status_code: int) -> None:
        """
        Increments the HTTP status histogram bucket closest to status_code.

        Buckets: 200 (2xx success), 400 (4xx blocked), 500 (5xx egress error).
        """
        with self._lock:
            bucket = (status_code // 100) * 100
            if bucket in self._http_status_counts:
                self._http_status_counts[bucket] += 1
            elif status_code >= 500:
                self._http_status_counts[500] += 1
            elif status_code >= 400:
                self._http_status_counts[400] += 1
            else:
                self._http_status_counts[200] += 1

    def record_request_event(
        self,
        *,
        user_id: str,
        session_id: str,
        total_ms: float,
        http_status: int,
        blocked: bool,
        blocked_layer: str | None,
        layer_timings: dict[str, float] | None = None,
    ) -> None:
        """
        Appends a structured event to the rolling request log.

        Args:
            user_id: Requester identifier.
            session_id: Session identifier.
            total_ms: End-to-end processing time in milliseconds.
            http_status: Final HTTP status code returned to the client.
            blocked: True if the request was blocked.
            blocked_layer: Name of the blocking layer, or None.
            layer_timings: Optional dict of layer_name → latency_ms.
        """
        event = {
            "ts": time.time(),
            "user_id": user_id,
            "session_id": session_id,
            "total_ms": round(total_ms, 2),
            "http_status": http_status,
            "blocked": blocked,
            "blocked_layer": blocked_layer,
            "layer_timings": layer_timings or {},
        }
        with self._lock:
            self._request_log.appendleft(event)

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------
    @property
    def uptime_seconds(self) -> float:
        """Returns the number of seconds since the collector was initialized."""
        return round(time.monotonic() - self._start_time, 2)

    @property
    def total_requests(self) -> int:
        with self._lock:
            return self._total_requests

    @property
    def clean_passed(self) -> int:
        with self._lock:
            return self._clean_passed

    def get_layer_stats(self) -> list[dict]:
        """
        Returns a serializable list of per-layer statistics.

        Returns:
            A list of dicts compatible with the LayerStats schema,
            extended with p50_ms / p95_ms / max_ms for the Telescope.
        """
        with self._lock:
            return [
                {
                    "layer_name": counter.name,
                    "total_blocked": counter.blocked,
                    "avg_latency_ms": counter.avg_latency_ms,
                    "p50_ms": counter.p50_ms,
                    "p95_ms": counter.p95_ms,
                    "max_ms": counter.max_ms,
                    "invocations": counter.invocations,
                }
                for counter in self._layers.values()
            ]

    def get_http_status_counts(self) -> dict[int, int]:
        """Returns a copy of the HTTP status histogram."""
        with self._lock:
            return dict(self._http_status_counts)

    def get_request_log(self, limit: int = 50) -> list[dict]:
        """Returns the most recent `limit` request events."""
        with self._lock:
            return list(self._request_log)[:limit]

    def reset(self) -> None:
        """Resets all counters. Used after a vault reset operation."""
        with self._lock:
            self._total_requests = 0
            self._clean_passed = 0
            self._start_time = time.monotonic()
            self._http_status_counts = {200: 0, 400: 0, 500: 0}
            self._request_log.clear()
            for counter in self._layers.values():
                counter.reset()


# Module-level singleton instance.
metrics_collector = MetricsCollector()
