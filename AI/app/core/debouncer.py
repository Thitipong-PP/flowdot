import asyncio
from typing import Dict, List, Any, Optional, Callable
from app.config import settings

class DebounceManager:
    """
    Ingress Debounce Buffer with Per-User Concurrency Locks.
    Batches rapid sequential inputs (e.g., photo followed immediately by caption text)
    into a single cohesive multi-modal event payload within a 3-5s configurable window.
    """
    def __init__(self, wait_seconds: Optional[float] = None, on_flush_callback: Optional[Callable] = None):
        self.wait_seconds = wait_seconds if wait_seconds is not None else getattr(settings, "DEBOUNCE_WAIT_SECONDS", 3.0)
        self.on_flush_callback = on_flush_callback
        self.buffers: Dict[str, List[Any]] = {}
        self.timers: Dict[str, asyncio.Task] = {}
        self.locks: Dict[str, asyncio.Lock] = {}

    def get_lock(self, user_id: str) -> asyncio.Lock:
        """Retrieves or creates a dedicated asyncio.Lock for the user session."""
        if user_id not in self.locks:
            self.locks[user_id] = asyncio.Lock()
        return self.locks[user_id]

    async def add_event(self, user_id: str, event: Any):
        """
        Appends an incoming event to the user's buffer and resets the debounce timer.
        """
        if user_id not in self.buffers:
            self.buffers[user_id] = []
        self.buffers[user_id].append(event)

        # Cancel active timer if a new event arrives within the debounce window
        if user_id in self.timers and not self.timers[user_id].done():
            self.timers[user_id].cancel()

        self.timers[user_id] = asyncio.create_task(self._flush_after_delay(user_id))

    async def _flush_after_delay(self, user_id: str):
        """
        Awaits debounce delay, acquires concurrency lock, and executes the flush callback.
        """
        try:
            await asyncio.sleep(self.wait_seconds)
            lock = self.get_lock(user_id)
            async with lock:
                items = self.buffers.pop(user_id, [])
                if items and self.on_flush_callback:
                    await self.on_flush_callback(user_id, items)
        except asyncio.CancelledError:
            # Expected when subsequent events reset the debounce timer
            pass
