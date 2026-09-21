import asyncio
import time
from dataclasses import dataclass
from typing import Callable

@dataclass
class _ModelState:
    consecutive_failures: int = 0
    open_until: float | None = None
    half_open: bool = False

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 30.0, time_fn: Callable[[], float] = time.monotonic) -> None:
        self._failure_threshold = max(1, failure_threshold)
        self._cooldown_seconds = max(0.0, cooldown_seconds)
        self._time_fn = time_fn
        self._states: dict[str, _ModelState] = {}
        self._lock = asyncio.Lock()

    async def allows(self, model: str) -> bool:
        async with self._lock:
            state = self._states.get(model)
            if state is None or state.open_until is None:
                return True
            if self._time_fn() >= state.open_until:
                state.open_until = None
                state.half_open = True
                return True
            return False

    async def record_success(self, model: str) -> None:
        async with self._lock:
            self._states[model] = _ModelState()

    async def record_failure(self, model: str) -> None:
        async with self._lock:
            state = self._states.setdefault(model, _ModelState())
            if state.half_open:
                state.half_open = False
                state.consecutive_failures = 0
                state.open_until = self._time_fn() + self._cooldown_seconds
                return
            state.consecutive_failures += 1
            if state.consecutive_failures >= self._failure_threshold:
                state.consecutive_failures = 0
                state.open_until = self._time_fn() + self._cooldown_seconds
