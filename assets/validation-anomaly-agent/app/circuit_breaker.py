import asyncio, time
from dataclasses import dataclass
from typing import Callable

@dataclass
class _ModelState:
    consecutive_failures: int = 0
    open_until: float | None = None
    half_open: bool = False

class CircuitBreaker:
    def __init__(self, failure_threshold=3, cooldown_seconds=30.0, time_fn=time.monotonic):
        self._failure_threshold = max(1, failure_threshold)
        self._cooldown_seconds = max(0.0, cooldown_seconds)
        self._time_fn = time_fn
        self._states: dict[str, _ModelState] = {}
        self._lock = asyncio.Lock()

    async def allows(self, model):
        async with self._lock:
            s = self._states.get(model)
            if s is None or s.open_until is None: return True
            if self._time_fn() >= s.open_until:
                s.open_until = None; s.half_open = True; return True
            return False

    async def record_success(self, model):
        async with self._lock: self._states[model] = _ModelState()

    async def record_failure(self, model):
        async with self._lock:
            s = self._states.setdefault(model, _ModelState())
            if s.half_open:
                s.half_open = False; s.consecutive_failures = 0
                s.open_until = self._time_fn() + self._cooldown_seconds; return
            s.consecutive_failures += 1
            if s.consecutive_failures >= self._failure_threshold:
                s.consecutive_failures = 0
                s.open_until = self._time_fn() + self._cooldown_seconds
