import asyncio
import json
from typing import Dict, List, AsyncGenerator
from app.schemas.events import TelemetryEvent

class TelemetryEmitter:
    """
    In-memory Server-Sent Events (SSE) broadcaster.
    Allows real-time streaming of multi-agent thought logs, wire activities,
    and telemetry metrics per user session.
    """
    def __init__(self):
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}

    def subscribe(self, session_id: str) -> asyncio.Queue:
        """Subscribes an asyncio.Queue to receive events for session_id."""
        if session_id not in self._subscribers:
            self._subscribers[session_id] = []
        q = asyncio.Queue()
        self._subscribers[session_id].append(q)
        return q

    def unsubscribe(self, session_id: str, q: asyncio.Queue):
        """Unsubscribes and cleans up the queue for session_id."""
        if session_id in self._subscribers:
            if q in self._subscribers[session_id]:
                self._subscribers[session_id].remove(q)
            if not self._subscribers[session_id]:
                del self._subscribers[session_id]

    async def emit(self, event: TelemetryEvent):
        """Broadcasts a TelemetryEvent to all active subscribers of the session."""
        session_id = event.session_id
        if session_id in self._subscribers:
            for q in list(self._subscribers[session_id]):
                await q.put(event)

    async def subscribe_events(self, session_id: str) -> AsyncGenerator[str, None]:
        """
        Yields formatted SSE data strings for consumption by FastAPI EventSourceResponse.
        Automatically unsubscribes upon client disconnect or cancellation.
        """
        q = self.subscribe(session_id)
        try:
            # Send initial SSE comment to flush HTTP headers immediately
            yield ": connected\n\n"
            while True:
                event: TelemetryEvent = await q.get()
                payload_str = event.model_dump_json()
                yield f"data: {payload_str}\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            self.unsubscribe(session_id, q)

# Global singleton emitter instance
telemetry_emitter = TelemetryEmitter()
