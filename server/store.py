"""HAND-WRITTEN, NOT generated. See server/README.md.

In-memory message store: the dedup record, the stored messages, and one FIFO queue
of undelivered message ids per recipient name.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class Message:
    id: str
    frm: str
    to: str
    text: str
    server_ts: int

    def to_frame(self) -> dict:
        """REQ-S2C-004. Field order is irrelevant (REQ-FRAME-006)."""
        return {
            "v": 1,
            "type": "msg",
            "id": self.id,
            "from": self.frm,
            "to": self.to,
            "text": self.text,
            "server_ts": self.server_ts,
        }


class Store:
    def __init__(self) -> None:
        # REQ-DEDUP-001: every accepted id, retained for the process lifetime --
        # including ids whose message has been delivered and dropped.
        self._seen_ids: set[str] = set()
        self._messages: dict[str, Message] = {}
        # REQ-SNF-003: one FIFO queue of undelivered ids per recipient name.
        # REQ-SNF-011 (via REQ-SNF-005): unbounded, never trimmed.
        self._queues: dict[str, list[str]] = {}
        self._last_ts = 0

    # -- deduplication ----------------------------------------------------------

    def has_seen(self, msg_id: str) -> bool:
        """REQ-DEDUP-002, REQ-DEDUP-004: keyed on id alone, no session context."""
        return msg_id in self._seen_ids

    # -- accept -----------------------------------------------------------------

    def _next_ts(self) -> int:
        """REQ-TIME-001, REQ-TIME-003: epoch ms, non-decreasing in accept order."""
        now = int(time.time() * 1000)
        if now < self._last_ts:
            now = self._last_ts
        self._last_ts = now
        return now

    def accept(self, msg_id: str, frm: str, to: str, text: str) -> Message:
        """REQ-SNF-001: durably record the message, then the caller acks.

        REQ-SNF-009 applies for free: an unknown recipient simply gets a queue.
        REQ-SNF-010 likewise, when ``to == frm``.
        """
        msg = Message(id=msg_id, frm=frm, to=to, text=text, server_ts=self._next_ts())
        self._messages[msg_id] = msg
        self._seen_ids.add(msg_id)
        self._queues.setdefault(to, []).append(msg_id)
        return msg

    # -- held queue -------------------------------------------------------------

    def pending_ids(self, name: str) -> list[str]:
        """REQ-SNF-007: accept order. A copy, so callers can snapshot it."""
        return list(self._queues.get(name, ()))

    def pending_count(self, name: str) -> int:
        """REQ-SYNC-004: the snapshot count reported in welcome."""
        return len(self._queues.get(name, ()))

    def message(self, msg_id: str) -> Message | None:
        return self._messages.get(msg_id)

    def confirm(self, name: str, msg_id: str) -> bool:
        """REQ-SNF-005: drop a held message, and only on delivered from its recipient.

        Returns True when something was dropped. REQ-SNF-008: an unknown id, an
        already-dropped id, or an id addressed to someone else is ignored.
        """
        msg = self._messages.get(msg_id)
        if msg is None or msg.to != name:
            return False
        queue = self._queues.get(name)
        if not queue or msg_id not in queue:
            return False
        queue.remove(msg_id)
        return True
