"""UI events: what Sarjy actually did, sent to the browser over LiveKit.

The browser only renders these; it never writes memory. Every event says what
happened (saved, refused, failed), so the UI can prove a save rather than trust
what the model said. Values of refused facts are never sent.
"""

import json
import logging
from typing import Any, Protocol

from livekit import rtc

logger = logging.getLogger("sarjy.events")

EVENTS_TOPIC = "sarjy.events"
MEMORY_RPC_METHOD = "sarjy.memory_snapshot"
EVENTS_VERSION = 1


class EventSink(Protocol):
    async def emit(self, event: dict[str, Any]) -> None: ...


class NullEventSink:
    """Used in tests and when no room is attached."""

    async def emit(self, event: dict[str, Any]) -> None:
        return None


class RoomEventSink:
    """Publishes events to one participant only: the user this session belongs to."""

    def __init__(self, room: rtc.Room, user_identity: str) -> None:
        self._room = room
        self._user_identity = user_identity

    async def emit(self, event: dict[str, Any]) -> None:
        payload = json.dumps({"v": EVENTS_VERSION, **event})
        try:
            await self._room.local_participant.publish_data(
                payload,
                reliable=True,
                topic=EVENTS_TOPIC,
                destination_identities=[self._user_identity],
            )
        except Exception:  # UI events must never break the conversation
            logger.warning("could not publish UI event", extra={"type": event.get("type")})
