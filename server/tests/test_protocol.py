"""HAND-WRITTEN, NOT generated. See server/README.md.

Wire-level tests: they speak raw WebSocket frames, never a generated client, so they
pin the server half of spec/core/protocol.md independently of any client code.
Each test names the requirement IDs it covers.
"""

from __future__ import annotations

import asyncio
import json
import socket
import uuid

import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from server.app import Server, _only_ws_path

TIMEOUT = 5.0


# -- harness ---------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Harness:
    """A running server plus helpers for raw client connections."""

    def __init__(self, port: int) -> None:
        self.port = port
        self.url = f"ws://127.0.0.1:{port}/ws"

    async def open(self):
        return await connect(self.url, open_timeout=TIMEOUT)

    @staticmethod
    async def send(ws, frame: dict) -> None:
        await ws.send(json.dumps(frame))

    @staticmethod
    async def recv(ws) -> dict:
        raw = await asyncio.wait_for(ws.recv(), TIMEOUT)
        return json.loads(raw)

    async def hello(self, name: str):
        """Connect and complete the handshake, returning (ws, welcome, replayed)."""
        ws = await self.open()
        await self.send(ws, {"v": 1, "type": "hello", "name": name})
        welcome = await self.recv(ws)
        assert welcome["type"] == "welcome", welcome
        replayed = []
        for _ in range(welcome["pending"]):
            replayed.append(await self.recv(ws))
        done = await self.recv(ws)
        assert done["type"] == "sync_done", done
        return ws, welcome, replayed


def run(coro):
    """Run one async test body on a fresh server, then shut everything down."""

    async def main():
        server = Server()
        port = _free_port()
        async with serve(
            server.handle, "127.0.0.1", port, process_request=_only_ws_path
        ):
            await coro(Harness(port), server)

    asyncio.run(asyncio.wait_for(main(), 30))


def mid() -> str:
    """A fresh client-generated id (REQ-MSGID-001, REQ-MSGID-002)."""
    return str(uuid.uuid4())


async def expect_closed(ws) -> None:
    with pytest.raises(ConnectionClosed):
        await asyncio.wait_for(ws.recv(), TIMEOUT)


async def expect_silence(ws, window: float = 0.4) -> None:
    """Nothing further arrives within the window."""
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(ws.recv(), window)


# -- handshake order -------------------------------------------------------------


def test_handshake_order_welcome_then_held_then_sync_done():
    """REQ-SYNC-003, REQ-SYNC-004, REQ-SYNC-005, REQ-SYNC-006, REQ-SNF-007."""

    async def body(h: Harness, _server):
        alice, _, _ = await h.hello("alice")
        ids = [mid(), mid(), mid()]
        for i, m in enumerate(ids):
            await h.send(alice, {"v": 1, "type": "send", "id": m, "to": "bob", "text": f"m{i}"})
            assert (await h.recv(alice)) == {"v": 1, "type": "ack", "id": m}

        bob = await h.open()
        await h.send(bob, {"v": 1, "type": "hello", "name": "bob"})

        welcome = await h.recv(bob)
        assert welcome["type"] == "welcome"
        assert welcome["name"] == "bob"
        assert welcome["pending"] == 3  # REQ-SYNC-004: snapshot count

        for i, m in enumerate(ids):  # REQ-SYNC-005 + REQ-SNF-007: accept order
            frame = await h.recv(bob)
            assert frame["type"] == "msg"
            assert frame["id"] == m
            assert frame["from"] == "alice"
            assert frame["to"] == "bob"
            assert frame["text"] == f"m{i}"
            assert isinstance(frame["server_ts"], int)

        assert (await h.recv(bob))["type"] == "sync_done"  # REQ-SYNC-006
        await expect_silence(bob)

    run(body)


def test_sync_done_immediate_when_nothing_pending():
    """REQ-SYNC-006: with pending 0, sync_done immediately follows welcome."""

    async def body(h: Harness, _server):
        ws = await h.open()
        await h.send(ws, {"v": 1, "type": "hello", "name": "carol"})
        assert (await h.recv(ws)) == {"v": 1, "type": "welcome", "name": "carol", "pending": 0}
        assert (await h.recv(ws)) == {"v": 1, "type": "sync_done"}

    run(body)


def test_message_accepted_during_replay_is_deferred():
    """REQ-SYNC-007: nothing may interleave between welcome and sync_done."""

    async def body(h: Harness, _server):
        alice, _, _ = await h.hello("alice")
        held = mid()
        await h.send(alice, {"v": 1, "type": "send", "id": held, "to": "bob", "text": "held"})
        await h.recv(alice)

        bob = await h.open()
        await h.send(bob, {"v": 1, "type": "hello", "name": "bob"})
        welcome = await h.recv(bob)
        assert welcome["pending"] == 1

        # Arrives while bob is replaying: it must not be counted or interleaved.
        during = mid()
        await h.send(alice, {"v": 1, "type": "send", "id": during, "to": "bob", "text": "during"})
        await h.recv(alice)

        first = await h.recv(bob)
        assert first["id"] == held
        assert (await h.recv(bob))["type"] == "sync_done"
        after = await h.recv(bob)  # pushed only once the window has closed
        assert after["type"] == "msg" and after["id"] == during

    run(body)


# -- store and forward -----------------------------------------------------------


def test_ack_precedes_push_and_online_delivery():
    """REQ-SNF-001, REQ-SNF-002."""

    async def body(h: Harness, _server):
        alice, _, _ = await h.hello("alice")
        bob, _, _ = await h.hello("bob")
        m = mid()
        await h.send(alice, {"v": 1, "type": "send", "id": m, "to": "bob", "text": "hi"})
        assert (await h.recv(alice)) == {"v": 1, "type": "ack", "id": m}
        pushed = await h.recv(bob)
        assert pushed["type"] == "msg" and pushed["id"] == m and pushed["text"] == "hi"

    run(body)


def test_send_to_unknown_name_is_accepted_and_held():
    """REQ-SNF-009: an unseen recipient is allowed; the message waits for them."""

    async def body(h: Harness, _server):
        alice, _, _ = await h.hello("alice")
        m = mid()
        await h.send(alice, {"v": 1, "type": "send", "id": m, "to": "nobody_yet", "text": "later"})
        assert (await h.recv(alice))["type"] == "ack"  # not an error
        await expect_silence(alice)

        _ws, welcome, replayed = await h.hello("nobody_yet")
        assert welcome["pending"] == 1
        assert replayed[0]["id"] == m

    run(body)


def test_self_send_follows_the_same_path():
    """REQ-SNF-010."""

    async def body(h: Harness, _server):
        alice, _, _ = await h.hello("alice")
        m = mid()
        await h.send(alice, {"v": 1, "type": "send", "id": m, "to": "alice", "text": "note"})
        assert (await h.recv(alice))["type"] == "ack"
        echoed = await h.recv(alice)
        assert echoed["type"] == "msg" and echoed["id"] == m and echoed["from"] == "alice"

    run(body)


def test_push_without_delivered_is_repushed_on_reconnect():
    """REQ-SNF-004 (via REQ-SNF-005), REQ-SNF-006, REQ-TIME-002."""

    async def body(h: Harness, _server):
        alice, _, _ = await h.hello("alice")
        bob, _, _ = await h.hello("bob")
        m = mid()
        await h.send(alice, {"v": 1, "type": "send", "id": m, "to": "bob", "text": "again"})
        await h.recv(alice)
        first = await h.recv(bob)
        assert first["id"] == m

        await bob.close()  # bob never confirmed it
        _bob2, welcome, replayed = await h.hello("bob")
        assert welcome["pending"] == 1  # still held
        assert replayed[0]["id"] == m
        assert replayed[0]["server_ts"] == first["server_ts"]  # REQ-TIME-002

    run(body)


def test_delivered_removes_the_held_message():
    """REQ-SNF-005, REQ-C2S-003."""

    async def body(h: Harness, _server):
        alice, _, _ = await h.hello("alice")
        m = mid()
        await h.send(alice, {"v": 1, "type": "send", "id": m, "to": "bob", "text": "once"})
        await h.recv(alice)

        bob, welcome, replayed = await h.hello("bob")
        assert welcome["pending"] == 1 and replayed[0]["id"] == m
        await h.send(bob, {"v": 1, "type": "delivered", "id": m})
        await asyncio.sleep(0.1)
        await bob.close()

        _bob2, welcome2, replayed2 = await h.hello("bob")
        assert welcome2["pending"] == 0  # dropped
        assert replayed2 == []

    run(body)


def test_delivered_for_unknown_or_foreign_id_is_ignored():
    """REQ-SNF-008: idempotent, and never an error."""

    async def body(h: Harness, _server):
        alice, _, _ = await h.hello("alice")
        m = mid()
        await h.send(alice, {"v": 1, "type": "send", "id": m, "to": "bob", "text": "x"})
        await h.recv(alice)

        await h.send(alice, {"v": 1, "type": "delivered", "id": mid()})  # unknown
        await h.send(alice, {"v": 1, "type": "delivered", "id": m})  # addressed to bob
        await expect_silence(alice)

        _bob, welcome, _ = await h.hello("bob")
        assert welcome["pending"] == 1  # alice could not confirm bob's message

    run(body)


# -- deduplication ---------------------------------------------------------------


def test_duplicate_id_is_reacked_and_delivered_once():
    """REQ-DEDUP-001, REQ-DEDUP-002, REQ-DEDUP-005."""

    async def body(h: Harness, _server):
        alice, _, _ = await h.hello("alice")
        bob, _, _ = await h.hello("bob")
        m = mid()
        frame = {"v": 1, "type": "send", "id": m, "to": "bob", "text": "original"}

        await h.send(alice, frame)
        assert (await h.recv(alice)) == {"v": 1, "type": "ack", "id": m}
        pushed = await h.recv(bob)
        assert pushed["text"] == "original"

        # Same id again, with different content: re-acked, and to/text ignored.
        await h.send(alice, {"v": 1, "type": "send", "id": m, "to": "carol", "text": "rewritten"})
        assert (await h.recv(alice)) == {"v": 1, "type": "ack", "id": m}
        await expect_silence(bob)  # not forwarded twice

        _carol, welcome, _ = await h.hello("carol")
        assert welcome["pending"] == 0  # REQ-DEDUP-005: the duplicate's `to` is ignored

    run(body)


def test_duplicate_after_delivery_and_drop_is_still_a_plain_ack():
    """REQ-DEDUP-002, REQ-DEDUP-003, REQ-DEDUP-004."""

    async def body(h: Harness, _server):
        alice, _, _ = await h.hello("alice")
        bob, _, _ = await h.hello("bob")
        m = mid()
        await h.send(alice, {"v": 1, "type": "send", "id": m, "to": "bob", "text": "done"})
        await h.recv(alice)
        await h.recv(bob)
        await h.send(bob, {"v": 1, "type": "delivered", "id": m})
        await asyncio.sleep(0.1)

        # REQ-DEDUP-004: survives the sender reconnecting on a new connection.
        await alice.close()
        alice2, _, _ = await h.hello("alice")
        await h.send(alice2, {"v": 1, "type": "send", "id": m, "to": "bob", "text": "done"})
        assert (await h.recv(alice2)) == {"v": 1, "type": "ack", "id": m}
        await expect_silence(bob)

    run(body)


# -- session replacement ---------------------------------------------------------


def test_newest_connection_wins():
    """REQ-SESSION-001, REQ-SESSION-002, REQ-SESSION-003."""

    async def body(h: Harness, _server):
        first, _, _ = await h.hello("alice")

        second = await h.open()
        await h.send(second, {"v": 1, "type": "hello", "name": "alice"})

        # REQ-SESSION-002: the older connection is told, then closed.
        err = await h.recv(first)
        assert err["type"] == "error" and err["code"] == "replaced"
        assert "ref_id" not in err  # REQ-ERR-002: not attributable to a message
        await expect_closed(first)

        # REQ-SESSION-004: the newer connection proceeds normally.
        welcome = await h.recv(second)
        assert welcome["type"] == "welcome" and welcome["name"] == "alice"
        assert (await h.recv(second))["type"] == "sync_done"

    run(body)


def test_replacement_keeps_unconfirmed_messages_held():
    """REQ-SESSION-005 (via REQ-SESSION-007), REQ-SNF-006."""

    async def body(h: Harness, _server):
        alice, _, _ = await h.hello("alice")
        bob1, _, _ = await h.hello("bob")
        m = mid()
        await h.send(alice, {"v": 1, "type": "send", "id": m, "to": "bob", "text": "hold me"})
        await h.recv(alice)
        assert (await h.recv(bob1))["id"] == m  # pushed but never confirmed

        _bob2, welcome, replayed = await h.hello("bob")  # replaces bob1
        assert (await h.recv(bob1))["code"] == "replaced"
        assert welcome["pending"] == 1
        assert replayed[0]["id"] == m

    run(body)


# -- framing, versioning, forward compatibility ----------------------------------


def test_unknown_type_is_ignored_silently():
    """REQ-FRAME-003: the forward-compatibility rule."""

    async def body(h: Harness, _server):
        ws, _, _ = await h.hello("alice")
        await h.send(ws, {"v": 1, "type": "reaction", "id": mid(), "emoji": "+1"})
        await expect_silence(ws)  # no error, no close
        m = mid()
        await h.send(ws, {"v": 1, "type": "send", "id": m, "to": "bob", "text": "still here"})
        assert (await h.recv(ws))["id"] == m  # the session is unharmed

    run(body)


def test_unknown_fields_are_ignored():
    """REQ-FRAME-004."""

    async def body(h: Harness, _server):
        ws, _, _ = await h.hello("alice")
        m = mid()
        await h.send(
            ws,
            {"v": 1, "type": "send", "id": m, "to": "bob", "text": "hi", "priority": "high"},
        )
        assert (await h.recv(ws)) == {"v": 1, "type": "ack", "id": m}

    run(body)


def test_bad_version_and_bad_frame():
    """REQ-FRAME-002, REQ-FRAME-005, REQ-WIRE-005, REQ-ERR-007."""

    async def body(h: Harness, _server):
        ws, _, _ = await h.hello("alice")

        await ws.send("not json at all")
        assert (await h.recv(ws))["code"] == "bad_frame"

        await ws.send(json.dumps([1, 2, 3]))  # top-level not an object
        assert (await h.recv(ws))["code"] == "bad_frame"

        await h.send(ws, {"type": "send"})  # no v
        assert (await h.recv(ws))["code"] == "bad_version"

        await h.send(ws, {"v": 2, "type": "send"})
        assert (await h.recv(ws))["code"] == "bad_version"

        m = mid()
        await h.send(ws, {"v": 1, "type": "send", "id": m, "to": "bob"})  # no text
        err = await h.recv(ws)
        assert err["code"] == "bad_frame" and err["ref_id"] == m  # REQ-ERR-002

        # REQ-ERR-007: after all that, the connection still works.
        m2 = mid()
        await h.send(ws, {"v": 1, "type": "send", "id": m2, "to": "bob", "text": "alive"})
        assert (await h.recv(ws))["id"] == m2

    run(body)


def test_send_before_hello_is_rejected():
    """REQ-C2S-005."""

    async def body(h: Harness, _server):
        ws = await h.open()
        await h.send(ws, {"v": 1, "type": "send", "id": mid(), "to": "bob", "text": "early"})
        assert (await h.recv(ws))["code"] == "no_hello"
        await h.send(ws, {"v": 1, "type": "delivered", "id": mid()})
        assert (await h.recv(ws))["code"] == "no_hello"

    run(body)


def test_second_hello_is_rejected_without_disturbing_the_session():
    """REQ-SYNC-011."""

    async def body(h: Harness, _server):
        ws, _, _ = await h.hello("alice")
        await h.send(ws, {"v": 1, "type": "hello", "name": "alice2"})
        assert (await h.recv(ws))["code"] == "already_hello"
        m = mid()
        await h.send(ws, {"v": 1, "type": "send", "id": m, "to": "bob", "text": "unchanged"})
        assert (await h.recv(ws))["id"] == m

    run(body)


# -- validation ------------------------------------------------------------------


@pytest.mark.parametrize("name", ["", "a" * 33, "bad name", "bad!", "sp ace", None, 42])
def test_invalid_hello_name_errors_then_closes(name):
    """REQ-NAME-001, REQ-SYNC-010."""

    async def body(h: Harness, _server):
        ws = await h.open()
        await h.send(ws, {"v": 1, "type": "hello", "name": name})
        err = await h.recv(ws)
        assert err["type"] == "error" and err["code"] == "bad_name"
        await expect_closed(ws)

    run(body)


def test_names_are_case_sensitive():
    """REQ-NAME-002."""

    async def body(h: Harness, _server):
        alice, _, _ = await h.hello("alice")
        m = mid()
        await h.send(alice, {"v": 1, "type": "send", "id": m, "to": "Bob", "text": "capital"})
        await h.recv(alice)

        _lower, welcome_lower, _ = await h.hello("bob")
        assert welcome_lower["pending"] == 0
        _upper, welcome_upper, replayed = await h.hello("Bob")
        assert welcome_upper["pending"] == 1 and replayed[0]["id"] == m

    run(body)


@pytest.mark.parametrize(
    "text,code",
    [
        ("", "bad_text"),
        ("x" * 4001, "bad_text"),
        ("\ud800", "bad_text"),
        (None, "bad_frame"),
    ],
)
def test_invalid_text_is_rejected_with_ref_id(text, code):
    """REQ-TEXT-001, REQ-TEXT-002, REQ-TEXT-005, REQ-NAME-005, REQ-ERR-002."""

    async def body(h: Harness, _server):
        ws, _, _ = await h.hello("alice")
        m = mid()
        await h.send(ws, {"v": 1, "type": "send", "id": m, "to": "bob", "text": text})
        err = await h.recv(ws)
        assert err["type"] == "error" and err["code"] == code
        assert err["ref_id"] == m

        # Not acked, not stored, and the id was not recorded as seen: a later,
        # valid send with the same id must be accepted for real.
        await h.send(ws, {"v": 1, "type": "send", "id": m, "to": "bob", "text": "fixed"})
        assert (await h.recv(ws)) == {"v": 1, "type": "ack", "id": m}
        _bob, welcome, replayed = await h.hello("bob")
        assert welcome["pending"] == 1 and replayed[0]["text"] == "fixed"

    run(body)


def test_invalid_to_is_rejected_with_ref_id():
    """REQ-NAME-005."""

    async def body(h: Harness, _server):
        ws, _, _ = await h.hello("alice")
        m = mid()
        await h.send(ws, {"v": 1, "type": "send", "id": m, "to": "not a name", "text": "hi"})
        err = await h.recv(ws)
        assert err["code"] == "bad_name" and err["ref_id"] == m

    run(body)


def test_non_uuid4_id_is_rejected():
    """REQ-MSGID-001, REQ-DEDUP-006."""

    async def body(h: Harness, _server):
        ws, _, _ = await h.hello("alice")
        for bad in ["not-a-uuid", str(uuid.uuid4()).upper(), uuid.uuid4().hex]:
            await h.send(ws, {"v": 1, "type": "send", "id": bad, "to": "bob", "text": "x"})
            err = await h.recv(ws)
            assert err["code"] == "bad_frame" and err["ref_id"] == bad

    run(body)


def test_text_is_preserved_code_point_identical():
    """REQ-TEXT-003, REQ-TEXT-004, REQ-SNF-012 (via REQ-TEXT-003)."""

    async def body(h: Harness, _server):
        payload = "  spaced  \n\ttabs \U0001f600 emoji é́ combining  "
        alice, _, _ = await h.hello("alice")
        m = mid()
        await h.send(alice, {"v": 1, "type": "send", "id": m, "to": "bob", "text": payload})
        await h.recv(alice)
        _bob, _welcome, replayed = await h.hello("bob")
        assert replayed[0]["text"] == payload

    run(body)


def test_max_length_text_is_accepted():
    """REQ-TEXT-001: 4000 code points is the inclusive upper bound, counted in code
    points rather than UTF-16 units -- 4000 non-BMP characters must still pass."""

    async def body(h: Harness, _server):
        alice, _, _ = await h.hello("alice")
        for payload in ["x" * 4000, "\U0001f600" * 4000]:
            m = mid()
            await h.send(alice, {"v": 1, "type": "send", "id": m, "to": "bob", "text": payload})
            assert (await h.recv(alice)) == {"v": 1, "type": "ack", "id": m}

    run(body)
