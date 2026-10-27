# GENERATED from spec/ by the generator - do not edit by hand
#
# The client state machine, outbox, inbound handling and reconnection
# (spec/core/client-behavior.md), plus the wire protocol (spec/core/protocol.md)
# and the observable event stream (spec/core/cli-contract.md).

from __future__ import annotations

import asyncio
import json
import logging
import sys
import uuid
from pathlib import Path

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from .persistence import Store, valid_name, valid_text

log = logging.getLogger("client")

# REQ-STATE-001: exactly these five names, used verbatim in events
# (REQ-EVENT-004, REQ-COMPARE-004).
NO_IDENTITY = "NO_IDENTITY"
OFFLINE = "OFFLINE"
CONNECTING = "CONNECTING"
SYNCING = "SYNCING"
ONLINE = "ONLINE"

# REQ-RECONNECT-002: fixed 1 second interval -- no backoff, no jitter, no cap.
RETRY_SECONDS = 1.0

# REQ-ERR-005: an error carrying ref_id with one of these codes is a permanent
# rejection; the message can never succeed as sent.
PERMANENT_CODES = frozenset({"bad_name", "bad_text", "bad_frame"})


class Replaced(Exception):
    """REQ-SESSION-002: this session was displaced by a newer one."""


def emit(event: dict) -> None:
    # REQ-STDIO-002: stdout carries only JSON Lines events, one object per line.
    # REQ-STDIO-003: flushed immediately -- the conformance runner reads stdout
    # synchronously and blocks on expected events.
    # REQ-STDIO-006: single line; newlines inside strings are escaped by json.dumps.
    print(json.dumps(event, ensure_ascii=False, separators=(",", ":")), flush=True)


class Client:
    def __init__(self, server_url: str, data_dir: Path) -> None:
        self.url = server_url
        self.store = Store(data_dir)
        # REQ-EVENT-002: ready reports NO_IDENTITY on a fresh data-dir, OFFLINE when
        # an identity was loaded (T1 / T2).
        self.state = OFFLINE if self.store.name else NO_IDENTITY
        # REQ-RECONNECT-001: the auto-reconnect armed flag.
        self.armed = False
        self.ws = None
        self.task: asyncio.Task | None = None
        self.quitting = False

    # -- state ----------------------------------------------------------------

    def set_state(self, new: str) -> None:
        # REQ-STATE-004: the single gate for every transition in the T1-T18 table.
        # REQ-STATE-005: NO_IDENTITY is a start state only -- nothing sets it again.
        # REQ-STATE-002: emit state{from,to} on every real transition.
        # REQ-STATE-003: never for a self-transition, so retrying a connection is
        # silent on stdout and the event stream stays bounded while the server is
        # unreachable (REQ-RECONNECT-009).
        if new == self.state:
            return
        emit({"type": "state", "from": self.state, "to": new})
        self.state = new

    # -- commands -------------------------------------------------------------

    async def command(self, line: str) -> None:
        # REQ-CMD-001: the whole grammar -- login, send, offline, online, quit.
        # REQ-CMD-007: no stdin content may crash, hang or exit the client; the
        # worst outcome is an error event.
        # REQ-EVENT-001: these handlers emit only the seven defined event types.
        # REQ-ERRCODE-001: and only the defined client error codes.
        # REQ-STDIO-001: one command per line; a trailing CR is stripped, nothing else.
        line = line.rstrip("\r")
        # REQ-CMD-004: a blank or all-spaces line is ignored entirely.
        if not line.strip(" "):
            return
        tokens = line.split()
        word = tokens[0]
        # REQ-CMD-002: command words are lowercase and case-sensitive.
        if word == "login":
            self._login(tokens)
        elif word == "send":
            await self._send(line, tokens)
        elif word == "offline":
            await self._offline(tokens)
        elif word == "online":
            self._online(tokens)
        elif word == "quit":
            self._quit(tokens)
        else:
            # REQ-CMD-005: unknown command word; never exit.
            emit({"type": "error", "code": "unknown_command",
                  "message": f"unknown command {word!r}"})

    def _login(self, tokens: list[str]) -> None:
        # REQ-IDENTITY-001: an identity is required before connecting or sending.
        # REQ-CMD-006: login takes exactly one argument.
        if len(tokens) != 2:
            emit({"type": "error", "code": "bad_args", "message": "usage: login <name>"})
            return
        # REQ-IDENTITY-005: identity is immutable, even for the same name.
        if self.store.name is not None:
            emit({"type": "error", "code": "already_logged_in",
                  "message": "identity is already set"})
            return
        # REQ-IDENTITY-003: validated locally, before persistence, never on the network.
        if not valid_name(tokens[1]):
            emit({"type": "error", "code": "bad_name",
                  "message": "name must match [a-zA-Z0-9_-]{1,32}"})
            return
        self.store.save_identity(tokens[1])
        emit({"type": "logged_in", "name": tokens[1]})
        # T4: persist, emit logged_in, arm retry, then CONNECTING.
        self._arm()

    async def _send(self, line: str, tokens: list[str]) -> None:
        # REQ-CMD-003: <to> is the token after the command word, and <text...> is the
        # entire remainder of the line after the single space following <to>, taken
        # verbatim -- no trimming, splitting, re-quoting or escape interpretation.
        rest = line.lstrip(" ")[len("send"):].lstrip(" ")
        if " " not in rest:
            emit({"type": "error", "code": "bad_args",
                  "message": "usage: send <to> <text...>"})
            return
        to, text = rest.split(" ", 1)
        # REQ-STATE-006: a send with no identity is rejected and never queued.
        if self.store.name is None:
            emit({"type": "error", "code": "not_logged_in", "message": "login first"})
            return
        # REQ-OUTBOX-012: validate locally before queueing; no entry, no id consumed,
        # no `queued`, and therefore no ref_id on the error.
        if not valid_name(to):
            emit({"type": "error", "code": "bad_name",
                  "message": "recipient is not a valid name"})
            return
        if not valid_text(text):
            emit({"type": "error", "code": "bad_text",
                  "message": "text must be 1-4000 code points"})
            return
        # REQ-OUTBOX-003 steps 2-5. REQ-MSGID-001, REQ-MSGID-002, REQ-MSGID-004,
        # REQ-MSGID-005: a unique, opaque, lowercase canonical UUIDv4,
        # generated here, at the moment the user issues the send.
        entry = {"id": str(uuid.uuid4()), "to": to, "text": text}
        self.store.outbox.append(entry)
        # REQ-OUTBOX-002: durably written BEFORE any network attempt.
        self.store.save_outbox()
        # REQ-EVENT-005: queued{id,to,text}, after the write, before transmission.
        emit({"type": "queued", **entry})
        # REQ-FLUSH-004: while ONLINE, transmit immediately; REQ-STATE-007 /
        # REQ-FLUSH-005: otherwise it is queued only, and that is not an error.
        if self.state == ONLINE and self.ws is not None:
            await self._transmit(entry)

    async def _offline(self, tokens: list[str]) -> None:
        if len(tokens) != 1:
            emit({"type": "error", "code": "bad_args", "message": "usage: offline"})
            return
        # REQ-TESTHOOK-001: offline/online simulate network loss deterministically.
        # REQ-TESTHOOK-006: neither hook touches persistent state.
        # REQ-TESTHOOK-007: there are no other hidden hooks or debug modes.
        # REQ-TESTHOOK-002: close the connection immediately and disarm reconnect.
        # REQ-TESTHOOK-004: a no-op that still disarms when already OFFLINE (T8),
        # which set_state makes silent.
        self.armed = False
        self._cancel_network()
        await self._drop_connection()
        self.set_state(OFFLINE)

    def _online(self, tokens: list[str]) -> None:
        if len(tokens) != 1:
            emit({"type": "error", "code": "bad_args", "message": "usage: online"})
            return
        self.armed = True
        # REQ-TESTHOOK-005: while CONNECTING/SYNCING/ONLINE this only arms the flag --
        # no state event, and the existing attempt is not disturbed.
        if self.state in (CONNECTING, SYNCING, ONLINE):
            return
        if self.store.name is None:
            return
        # T7 + REQ-RECONNECT-005: attempt immediately, without waiting out the interval.
        self._arm()

    def _quit(self, tokens: list[str]) -> None:
        if len(tokens) != 1:
            emit({"type": "error", "code": "bad_args", "message": "usage: quit"})
            return
        # REQ-CMD-008: exit 0 without waiting for acks, without flushing, without
        # dropping outbox entries -- all state is already durable. No state event.
        self.quitting = True

    # -- network --------------------------------------------------------------

    def _arm(self) -> None:
        # REQ-RECONNECT-001: arming starts the connection loop.
        self.armed = True
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._network())

    def _cancel_network(self) -> None:
        if self.task is not None:
            self.task.cancel()
            self.task = None

    async def _drop_connection(self) -> None:
        ws, self.ws = self.ws, None
        if ws is not None:
            try:
                await ws.close()
            except (ConnectionClosed, OSError):
                pass

    async def _network(self) -> None:
        # REQ-STATE-001 / REQ-RECONNECT-002: CONNECTING covers the whole attempt
        # period, including the gaps between retries, so a failed attempt never
        # leaves the state (T6, T10) and emits nothing.
        self.set_state(CONNECTING)
        while self.armed:
            try:
                # REQ-WIRE-006, REQ-WIRE-007: no subprotocol, extension or
                # compression requirement, and no application-level heartbeat.
                # REQ-RECONNECT-008: reconnecting never clears the outbox, the seen
                # set or the identity -- they live in the Store, untouched here.
                async with await connect(self.url, open_timeout=5) as ws:
                    self.ws = ws
                    await self._session(ws)
            except asyncio.CancelledError:
                raise
            except Replaced:
                # T17 + REQ-RECONNECT-006: disarm and go OFFLINE; reconnecting here
                # would make two clients evict each other indefinitely.
                self.armed = False
                await self._drop_connection()
                self.set_state(OFFLINE)
                return
            except Exception as exc:
                # REQ-RECONNECT-009: a connect failure emits no error event and no
                # state event; human detail goes to stderr (REQ-STDIO-005).
                log.info("connection attempt failed: %s: %s", type(exc).__name__, exc)
            finally:
                self.ws = None
            if not self.armed:
                return
            # T13 / T15: a disconnect from SYNCING or ONLINE is the one state event
            # for the loss; then the retry loop is silent.
            self.set_state(CONNECTING)
            # REQ-RECONNECT-003: measured from the end of the previous attempt.
            await asyncio.sleep(RETRY_SECONDS)

    async def _session(self, ws) -> None:
        # REQ-SYNC-001, REQ-SYNC-002: hello is the first frame, and no send or
        # delivered goes out before welcome. REQ-C2S-001: hello{name}.
        # REQ-C2S-004: hello, send and delivered are the only frames a client sends.
        # REQ-RECONNECT-007: every reconnection repeats this whole handshake.
        # REQ-INBOUND-005: frames are handled in arrival order, never reordered.
        await self._frame(ws, {"v": 1, "type": "hello", "name": self.store.name})
        async for raw in ws:
            # REQ-WIRE-003: a binary frame is ignored.
            if isinstance(raw, (bytes, bytearray)):
                continue
            try:
                frame = json.loads(raw)
            except ValueError:
                # REQ-WIRE-005: a malformed frame is ignored and the connection stays.
                continue
            # REQ-FRAME-001/002: v must be the number 1; otherwise ignore.
            # REQ-FRAME-002, REQ-FRAME-005, REQ-FRAME-006, REQ-FRAME-007: a frame
            # with a bad v or a missing field is ignored by a client; key order and
            # whitespace are never relied on, and no extra fields are ever emitted.
            if not isinstance(frame, dict) or frame.get("v") != 1:
                continue
            kind = frame.get("type")
            if kind == "welcome":
                self.set_state(SYNCING)  # T9
            elif kind == "sync_done":
                # T12 + REQ-SYNC-008 / REQ-FLUSH-001: only now may the outbox flush.
                self.set_state(ONLINE)
                await self._flush()
            elif kind == "msg":
                await self._on_msg(ws, frame)
            elif kind == "ack":
                self._on_ack(frame)
            elif kind == "error":
                if frame.get("code") == "replaced":
                    raise Replaced()
                self._on_error(frame)
            # REQ-FRAME-003: any other type is ignored silently -- no error, no close,
            # no state change. REQ-FRAME-004: unknown fields are never read.

    async def _frame(self, ws, payload: dict) -> None:
        # REQ-WIRE-002: exactly one JSON object per text frame.
        await ws.send(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))

    async def _transmit(self, entry: dict) -> None:
        if self.ws is None:
            return
        # REQ-C2S-002, REQ-MSGID-003: always the entry's original id.
        await self._frame(self.ws, {"v": 1, "type": "send", **entry})

    async def _flush(self) -> None:
        # REQ-FLUSH-006: never reorder -- a send issued during a flush was appended
        # at the tail, so it naturally goes out after these.
        # REQ-OUTBOX-008: entries restored from disk are live here, and emit no
        # queued of their own.
        # REQ-FLUSH-002: every entry, in FIFO order, with its original id.
        # REQ-FLUSH-003: entries already sent but unacked are re-sent with the same
        # id, which server-side dedup makes safe (REQ-DEDUP-002).
        # REQ-FLUSH-008 (via REQ-OUTBOX-004): flushing never removes entries.
        for entry in list(self.store.outbox):
            await self._transmit(entry)

    # -- inbound --------------------------------------------------------------

    async def _on_msg(self, ws, frame: dict) -> None:
        # REQ-INBOUND-002: deduplicated by id, persisted so it survives restarts.
        # REQ-INBOUND-007: to is informational -- never filter on it.
        # REQ-C2S-003: delivered{id} confirms durable acceptance.
        msg_id = frame.get("id")
        if not isinstance(msg_id, str):
            return
        if msg_id in self.store.seen:
            # REQ-INBOUND-004: a duplicate is still confirmed, so the server can drop
            # its copy, but it must not be displayed again.
            await self._frame(ws, {"v": 1, "type": "delivered", "id": msg_id})
            return
        # REQ-INBOUND-003: persist the id, THEN display, THEN confirm. Persisting
        # before confirming stops a crash in between from redisplaying the message.
        self.store.seen.add(msg_id)
        self.store.save_seen()
        # REQ-EVENT-007: id, from and text only -- `to` and `server_ts` are never
        # surfaced (REQ-TIME-004, REQ-COMPARE-003).
        emit({"type": "received", "id": msg_id, "from": frame.get("from"),
              "text": frame.get("text")})
        # REQ-INBOUND-001: reply delivered (REQ-SNF-005 needs it to release the copy).
        await self._frame(ws, {"v": 1, "type": "delivered", "id": msg_id})

    def _on_ack(self, frame: dict) -> None:
        msg_id = frame.get("id")
        remaining = [e for e in self.store.outbox if e["id"] != msg_id]
        if len(remaining) == len(self.store.outbox):
            # REQ-OUTBOX-006: an ack for an id not in the outbox is ignored -- no
            # `sent`, no error. This covers duplicate acks from REQ-DEDUP-002.
            return
        # REQ-OUTBOX-005: remove, persist, THEN emit sent -- at most once per id.
        self.store.outbox = remaining
        self.store.save_outbox()
        # REQ-EVENT-006: sent{id} means the server took responsibility, not that
        # the recipient has seen it.
        emit({"type": "sent", "id": msg_id})

    def _on_error(self, frame: dict) -> None:
        # REQ-ERR-001: code is the contract, message is not parsed.
        # REQ-ERR-002: ref_id may be absent and must be tolerated.
        # REQ-ERR-007: an error does not close the connection or exit.
        # REQ-EVENT-008, REQ-EVENT-009: error{code,message,ref_id?} and no more.
        # REQ-ERRCODE-002: the server's code is relayed verbatim, including codes
        # unknown to this client (REQ-ERR-004); never translated or remapped.
        code = frame.get("code")
        ref = frame.get("ref_id")
        event = {"type": "error", "code": code, "message": frame.get("message", "")}
        if isinstance(ref, str):
            # REQ-ERRCODE-003: ref_id is surfaced whenever the error concerns a
            # specific message id, so a dropped entry is visible and attributable.
            event["ref_id"] = ref
            if code in PERMANENT_CODES:
                # REQ-ERR-005 / REQ-OUTBOX-009: a permanent rejection can never
                # succeed, so drop the entry rather than retry it forever. No `sent`.
                remaining = [e for e in self.store.outbox if e["id"] != ref]
                if len(remaining) != len(self.store.outbox):
                    self.store.outbox = remaining
                    self.store.save_outbox()
            # REQ-ERR-006 / REQ-OUTBOX-010: any other code is retryable, so the
            # entry stays in the outbox.
        emit(event)

    # -- lifecycle ------------------------------------------------------------

    async def run(self) -> int:
        # REQ-EVENT-002: ready is the first line on stdout, exactly once, after the
        # persisted state is loaded (REQ-PERSIST-008) and before reading stdin.
        emit({"type": "ready", "state": self.state})
        if self.store.name is not None:
            # T2: an identity loaded from disk re-emits logged_in and auto-connects
            # without a login (REQ-IDENTITY-004, REQ-EVENT-003).
            emit({"type": "logged_in", "name": self.store.name})
            self._arm()

        lines: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def reader() -> None:
            # A dedicated thread, so a blocking stdin read never stalls the loop
            # (REQ-STDIO-009: stdin is read in every state).
            for line in sys.stdin:
                loop.call_soon_threadsafe(lines.put_nowait, line.rstrip("\n"))
            loop.call_soon_threadsafe(lines.put_nowait, None)

        import threading

        threading.Thread(target=reader, daemon=True, name="stdin").start()

        while True:
            line = await lines.get()
            # REQ-STDIO-007: EOF on stdin is exactly the quit command (T18).
            if line is None:
                break
            # REQ-STDIO-008 / REQ-STATE-008: commands are processed strictly in order,
            # one at a time, on a single logical timeline, so the event stream is a
            # deterministic serialisation.
            await self.command(line)
            if self.quitting:
                break

        self.armed = False
        self._cancel_network()
        await self._drop_connection()
        return 0
