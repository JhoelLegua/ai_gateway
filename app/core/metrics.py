"""
Thread-safe in-memory metrics collector for the AI Gateway Perimetral.

Tracks request counts and latency statistics per security layer.
Designed as a singleton loaded during the application lifespan.
"""

import threading
import time
from dataclasses import dataclass, field


@dataclass
class LayerCounter:
    """Atomic counters and latency accumulator for one security layer."""

    name: str
    blocked: int = 0
    total_latency_ms: float = 0.0
    invocations: int = 0

    def record(self, latency_ms: float, blocked: bool) -> None:
        """Records a single layer invocation result."""
        self.invocations += 1
        self.total_latency_ms += latency_ms
        if blocked:
            self.blocked += 1

    @property
    def avg_latency_ms(self) -> float:
        """Returns the average latency across all invocations."""
        if self.invocations == 0:
            return 0.0
        return round(self.total_latency_ms / self.invocations, 2)


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
            A list of dicts compatible with the LayerStats schema.
        """
        with self._lock:
            return [
                {
                    "layer_name": counter.name,
                    "total_blocked": counter.blocked,
                    "avg_latency_ms": counter.avg_latency_ms,
                }
                for counter in self._layers.values()
            ]

    def reset(self) -> None:
        """Resets all counters. Used after a vault reset operation."""
        with self._lock:
            self._total_requests = 0
            self._clean_passed = 0
            self._start_time = time.monotonic()
            for counter in self._layers.values():
                counter.blocked = 0
                counter.total_latency_ms = 0.0
                counter.invocations = 0


# Module-level singleton instance.
metrics_collector = MetricsCollector()
