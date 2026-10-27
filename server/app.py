"""HAND-WRITTEN, NOT generated. See server/README.md.

The connection handler: framing, handshake ordering, store-and-forward.
Implements the server side of spec/core/protocol.md, v1, and nothing else.
"""

from __future__ import annotations

import asyncio
import json
import logging

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from .store import Message, Store
from .validate import is_valid_msg_id, is_valid_name, is_valid_text

log = logging.getLogger("server")

# REQ-C2S-004 / REQ-S2C-006: the v1 frame vocabulary.
CLIENT_FRAME_TYPES = frozenset({"hello", "send", "delivered"})


class Session:
    """One connection that has completed a successful hello (REQ-SESSION-001)."""

    def __init__(self, name: str, ws: ServerConnection) -> None:
        self.name = name
        self.ws = ws
        # REQ-SYNC-006: a session is synced once sync_done has been sent. Until then
        # it is not a push target (REQ-SNF-002, REQ-SYNC-007).
        self.synced = False
        self.pushed: set[str] = set()
        # Serialises every frame written to this connection, so a concurrent sender
        # cannot interleave with the handshake or reorder pushes (REQ-SNF-007).
        self.lock = asyncio.Lock()


class Server:
    def __init__(self) -> None:
        self.store = Store()
        self.sessions: dict[str, Session] = {}

    # -- frame output -----------------------------------------------------------

    async def _write(self, ws: ServerConnection, frame: dict) -> None:
        """One JSON object per text frame (REQ-WIRE-002, REQ-WIRE-003)."""
        await ws.send(json.dumps(frame, ensure_ascii=False, separators=(",", ":")))

    async def _send(self, session: Session, frame: dict) -> None:
        async with session.lock:
            await self._write(session.ws, frame)

    async def _error(
        self, ws: ServerConnection, code: str, message: str, ref_id: str | None = None
    ) -> None:
        """REQ-S2C-005, REQ-ERR-001. REQ-ERR-002: ref_id only when attributable."""
        frame: dict = {"v": 1, "type": "error", "code": code, "message": message}
        if ref_id is not None:
            frame["ref_id"] = ref_id
        log.info("error code=%s ref_id=%s detail=%s", code, ref_id, message)
        await self._write(ws, frame)

    # -- connection lifecycle ---------------------------------------------------

    async def handle(self, ws: ServerConnection) -> None:
        session: Session | None = None
        log.info("connection open peer=%s", ws.remote_address)
        try:
            async for raw in ws:
                # REQ-WIRE-003: a binary frame is ignored.
                if isinstance(raw, (bytes, bytearray)):
                    log.info("ignored binary frame")
                    continue
                session = await self._on_text(ws, session, raw)
        except ConnectionClosed:
            pass
        finally:
            # REQ-SESSION-007: discard the connection state, keep everything stored.
            if session is not None and self.sessions.get(session.name) is session:
                del self.sessions[session.name]
            log.info(
                "connection closed name=%s code=%s",
                session.name if session else None,
                ws.close_code,
            )

    async def _on_text(
        self, ws: ServerConnection, session: Session | None, raw: str
    ) -> Session | None:
        try:
            frame = json.loads(raw)
        except (ValueError, TypeError):
            # REQ-WIRE-005: malformed JSON, connection stays open (REQ-ERR-007).
            await self._error(ws, "bad_frame", "payload is not valid JSON")
            return session
        if not isinstance(frame, dict):
            # REQ-WIRE-005: top-level value must be an object.
            await self._error(ws, "bad_frame", "top-level JSON value is not an object")
            return session

        # REQ-FRAME-001/002: v must be the number 1. bool is excluded because it is a
        # subclass of int in Python but is not a JSON number.
        v = frame.get("v")
        if isinstance(v, bool) or not isinstance(v, int) or v != 1:
            await self._error(ws, "bad_version", "field v must be the number 1")
            return session

        ftype = frame.get("type")
        if not isinstance(ftype, str) or not ftype:
            await self._error(ws, "bad_frame", "field type must be a non-empty string")
            return session

        # REQ-FRAME-003: an unrecognised type is ignored silently -- no error, no
        # close, no state change. This is what makes v1 forward compatible.
        # REQ-FRAME-004: unknown fields are ignored simply by never reading them.
        if ftype not in CLIENT_FRAME_TYPES:
            log.info("ignored unknown frame type=%s", ftype)
            return session

        if ftype == "hello":
            return await self._on_hello(ws, session, frame)

        # REQ-C2S-005: send and delivered require a session.
        if session is None:
            await self._error(ws, "no_hello", "hello must be the first frame")
            return None
        if ftype == "send":
            await self._on_send(session, frame)
        else:
            await self._on_delivered(session, frame)
        return session

    # -- hello ------------------------------------------------------------------

    async def _on_hello(
        self, ws: ServerConnection, session: Session | None, frame: dict
    ) -> Session | None:
        # REQ-SYNC-011: a second hello leaves the existing session untouched.
        if session is not None:
            await self._error(ws, "already_hello", "this connection already has a session")
            return session

        name = frame.get("name")
        if not is_valid_name(name):
            # REQ-SYNC-010 / REQ-NAME-004: error, then close. No session is created.
            await self._error(ws, "bad_name", "name must match [a-zA-Z0-9_-]{1,32}")
            await ws.close()
            return None
        assert isinstance(name, str)

        # REQ-SESSION-002/003: newest connection wins, and the older one is told and
        # closed BEFORE welcome goes out on this one, so the order is observable.
        old = self.sessions.get(name)
        if old is not None:
            log.info("replacing session name=%s", name)
            try:
                async with old.lock:
                    await self._error(old.ws, "replaced", "replaced by a newer connection")
                    await old.ws.close()
            except ConnectionClosed:
                pass
            if self.sessions.get(name) is old:
                del self.sessions[name]

        session = Session(name, ws)
        self.sessions[name] = session
        await self._handshake(session)
        return session

    async def _handshake(self, session: Session) -> None:
        """REQ-SYNC-003/004/005/006: welcome, then the held messages, then sync_done.

        The lock is held for the whole sequence so nothing interleaves (REQ-SYNC-005).
        """
        name = session.name
        async with session.lock:
            replay = self.store.pending_ids(name)
            # REQ-SYNC-004: pending is a snapshot taken as welcome is emitted.
            await self._write(
                session.ws,
                {"v": 1, "type": "welcome", "name": name, "pending": len(replay)},
            )
            # REQ-SNF-006: everything still held is re-pushed, including messages
            # already pushed on an earlier connection. REQ-SNF-007: in accept order.
            for msg_id in replay:
                msg = self.store.message(msg_id)
                if msg is not None:
                    await self._write(session.ws, msg.to_frame())
                    session.pushed.add(msg_id)
            await self._write(session.ws, {"v": 1, "type": "sync_done"})
            session.synced = True
        log.info("synced name=%s replayed=%d", name, len(replay))

        # REQ-SYNC-007: anything accepted during the replay window was held rather
        # than pushed; deliver it now that sync_done has gone out.
        for msg_id in self.store.pending_ids(name):
            if msg_id not in session.pushed:
                msg = self.store.message(msg_id)
                if msg is not None:
                    await self._push(session, msg)

    # -- send -------------------------------------------------------------------

    async def _on_send(self, session: Session, frame: dict) -> None:
        msg_id = frame.get("id")
        ref = msg_id if isinstance(msg_id, str) else None

        # REQ-FRAME-005: required fields present and of the right type.
        if not isinstance(msg_id, str) or "to" not in frame or "text" not in frame:
            await self._error(
                session.ws, "bad_frame", "send requires id, to and text", ref
            )
            return
        # REQ-DEDUP-006: the envelope and the id format are validated as usual,
        # before the duplicate check.
        if not is_valid_msg_id(msg_id):
            await self._error(
                session.ws, "bad_frame", "id must be a lowercase UUIDv4", ref
            )
            return

        # REQ-DEDUP-002: an already-seen id is a success -- re-ack it, store nothing,
        # forward nothing. REQ-DEDUP-003: true in every state of the message, including
        # delivered and dropped. REQ-DEDUP-005: to and text are ignored entirely.
        if self.store.has_seen(msg_id):
            log.info("duplicate send id=%s from=%s", msg_id, session.name)
            await self._send(session, {"v": 1, "type": "ack", "id": msg_id})
            return

        to = frame.get("to")
        text = frame.get("text")
        # REQ-FRAME-005: a field of the wrong JSON type is a framing fault, which is
        # distinct from a well-typed but invalid value below.
        if not isinstance(to, str) or not isinstance(text, str):
            await self._error(
                session.ws, "bad_frame", "to and text must be strings", ref
            )
            return
        if not is_valid_name(to):
            # REQ-NAME-005: not acked, not stored, and the id is not recorded as seen.
            await self._error(session.ws, "bad_name", "to is not a valid name", ref)
            return
        if not is_valid_text(text):
            # REQ-TEXT-002 / REQ-TEXT-005.
            await self._error(
                session.ws, "bad_text", "text must be 1-4000 code points", ref
            )
            return

        # REQ-SNF-001: record, then ack the sender, then attempt delivery. The ack
        # always precedes any msg push arising from this send.
        msg = self.store.accept(msg_id, session.name, to, text)
        await self._send(session, {"v": 1, "type": "ack", "id": msg_id})
        log.info("accepted id=%s from=%s to=%s ts=%d", msg.id, msg.frm, msg.to, msg.server_ts)

        recipient = self.sessions.get(to)
        # REQ-SNF-002: push only to a synced session; otherwise it stays held
        # (REQ-SNF-003) and is replayed on the next hello.
        if recipient is not None and recipient.synced:
            await self._push(recipient, msg)

    async def _push(self, session: Session, msg: Message) -> None:
        """REQ-SNF-004 (via REQ-SNF-005): pushing is not deleting."""
        try:
            await self._send(session, msg.to_frame())
            session.pushed.add(msg.id)
            log.info("pushed id=%s to=%s", msg.id, session.name)
        except ConnectionClosed:
            # The message stays held; it is re-pushed on the next hello.
            log.info("push failed, still held id=%s to=%s", msg.id, session.name)

    # -- delivered --------------------------------------------------------------

    async def _on_delivered(self, session: Session, frame: dict) -> None:
        msg_id = frame.get("id")
        if not isinstance(msg_id, str):
            # REQ-FRAME-005.
            await self._error(session.ws, "bad_frame", "delivered requires id")
            return
        # REQ-SNF-005: the only thing that drops a held message.
        # REQ-SNF-008: anything else is ignored, with no error -- delivered is idempotent.
        if self.store.confirm(session.name, msg_id):
            session.pushed.discard(msg_id)
            log.info("confirmed id=%s by=%s", msg_id, session.name)
        else:
            log.info("ignored delivered id=%s by=%s", msg_id, session.name)


async def run(host: str, port: int) -> None:
    server = Server()
    # REQ-WIRE-001: exactly one endpoint, at /ws.
    async with serve(server.handle, host, port, process_request=_only_ws_path) as ws_server:
        log.info("listening host=%s port=%d path=/ws", host, port)
        await ws_server.serve_forever()


def _only_ws_path(connection, request):
    """REQ-WIRE-001: reject any path other than /ws before the handshake."""
    if request.path != "/ws":
        return connection.respond(404, "not found\n")
    return None
