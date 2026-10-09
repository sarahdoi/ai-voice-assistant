"""Retention: forget guests who have not started a call for a long time.

A guest exists only as their saved facts, so expiring a guest means deleting
those rows. The sweep runs from the agent itself, in the background, at most
once a day per worker process, so no extra scheduler or credentials are needed.
The query is one indexed range delete and normally removes nothing.
"""

import logging
import time
from collections.abc import Callable

from sarjy.services.memory import MemoryService

logger = logging.getLogger("sarjy.retention")

SWEEP_INTERVAL_S = 24 * 60 * 60


class RetentionSweeper:
    def __init__(
        self,
        interval_s: float = SWEEP_INTERVAL_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._interval_s = interval_s
        self._clock = clock
        self._last_sweep: float | None = None

    async def maybe_sweep(self, memory: MemoryService, days: int) -> int | None:
        """Delete inactive guests if a sweep is due. Returns rows deleted, or None if skipped."""
        if days <= 0:
            return None  # retention disabled
        now = self._clock()
        if self._last_sweep is not None and now - self._last_sweep < self._interval_s:
            return None
        self._last_sweep = now
        result = await memory.delete_inactive(days)
        if not result.ok:
            self._last_sweep = None  # try again with the next call
            logger.warning("retention sweep failed", extra={"error": result.error_code})
            return None
        deleted = result.data["rows"]
        if deleted:
            logger.info("retention sweep deleted inactive facts", extra={"rows": deleted})
        return deleted


SWEEPER = RetentionSweeper()
