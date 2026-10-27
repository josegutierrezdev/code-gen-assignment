"""HAND-WRITTEN TEST FIXTURE, NOT generated and NOT a reference client.

!! DO NOT READ THIS WHEN GENERATING A CLIENT !!

This exists only so the conformance runner can be tested before any real client
exists. Behavior comes from spec/core/, never from code (CLAUDE.md §1); treating
this file as a model would defeat the point of the whole exercise. It is
deliberately minimal, single-file, and not held to the generated clients'
standards.

Usage:  python -m mock_client --server <ws-url> --data-dir <path>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import threading
import uuid
from pathlib import Path

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

NAME_OK = lambda s: bool(s) and len(s) <= 32 and all(  # noqa: E731
    c.isascii() and (c.isalnum() or c in "_-") for c in s
)
RETRY_S = 1.0


class Replaced(Exception):
    pass


def emit(event: dict) -> None:
    print(json.dumps(event, ensure_ascii=False, separators=(",", ":")), flush=True)


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return dict(default)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        emit({"type": "error", "code": "corrupt_state", "message": f"{path.name}: {exc}"})
        raise SystemExit(2)
    if not isinstance(data, dict) or data.get("v") != 1:
        emit({"type": "error", "code": "corrupt_state", "message": f"{path.name}: bad schema"})
        raise SystemExit(2)
    return data


def write_json(path: Path, data: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


class MockClient:
    def __init__(self, url: str, data_dir: Path) -> None:
        self.url = url
        self.dir = data_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        identity = read_json(self.dir / "identity.json", {"v": 1})
        self.name: str | None = identity.get("name")
        if self.name is not None and not NAME_OK(self.name):
            emit({"type": "error", "code": "corrupt_state", "message": "identity name"})
            raise SystemExit(2)
        self.outbox: list[dict] = read_json(
            self.dir / "outbox.json", {"v": 1, "entries": []}
        ).get("entries", [])
        self.seen: list[str] = read_json(
            self.dir / "seen.json", {"v": 1, "seen": []}
        ).get("seen", [])
        self.state = "OFFLINE" if self.name else "NO_IDENTITY"
        self.armed = False
        self.ws = None
        self.task: asyncio.Task | None = None
        self.stop = False

    # -- state / persistence ----------------------------------------------------

    def set_state(self, new: str) -> None:
        if new == self.state:
            return
        emit({"type": "state", "from": self.state, "to": new})
        self.state = new

    def save_outbox(self) -> None:
        write_json(self.dir / "outbox.json", {"v": 1, "entries": self.outbox})

    def save_seen(self) -> None:
        write_json(self.dir / "seen.json", {"v": 1, "seen": self.seen})

    # -- commands ---------------------------------------------------------------

    async def command(self, line: str) -> None:
        line = line.rstrip("\r")
        if not line.strip(" "):
            return
        tokens = line.split()
        word = tokens[0]
        if word == "login":
            if len(tokens) != 2:
                return emit({"type": "error", "code": "bad_args", "message": "login <name>"})
            if self.name is not None:
                return emit({"type": "error", "code": "already_logged_in", "message": "identity is fixed"})
            if not NAME_OK(tokens[1]):
                return emit({"type": "error", "code": "bad_name", "message": "invalid name"})
            self.name = tokens[1]
            write_json(self.dir / "identity.json", {"v": 1, "name": self.name})
            emit({"type": "logged_in", "name": self.name})
            self.arm()
        elif word == "send":
            rest = line.lstrip(" ")[len("send"):].lstrip(" ")
            if " " not in rest:
                return emit({"type": "error", "code": "bad_args", "message": "send <to> <text...>"})
            to, text = rest.split(" ", 1)
            await self.queue(to, text)
        elif word == "offline":
            if len(tokens) != 1:
                return emit({"type": "error", "code": "bad_args", "message": "offline"})
            self.armed = False
            if self.task is not None:
                self.task.cancel()
                self.task = None
            await self.drop_connection()
            self.set_state("OFFLINE")
        elif word == "online":
            if len(tokens) != 1:
                return emit({"type": "error", "code": "bad_args", "message": "online"})
            self.armed = True
            if self.state in ("CONNECTING", "SYNCING", "ONLINE"):
                return
            self.arm()
        elif word == "quit":
            if len(tokens) != 1:
                return emit({"type": "error", "code": "bad_args", "message": "quit"})
            self.stop = True
        else:
            emit({"type": "error", "code": "unknown_command", "message": word})

    async def queue(self, to: str, text: str) -> None:
        if self.name is None:
            return emit({"type": "error", "code": "not_logged_in", "message": "login first"})
        if not NAME_OK(to):
            return emit({"type": "error", "code": "bad_name", "message": "invalid recipient"})
        if not (1 <= len(text) <= 4000):
            return emit({"type": "error", "code": "bad_text", "message": "1-4000 code points"})
        entry = {"id": str(uuid.uuid4()), "to": to, "text": text}
        self.outbox.append(entry)
        self.save_outbox()
        emit({"type": "queued", **entry})
        if self.state == "ONLINE" and self.ws is not None:
            await self.transmit(entry)

    # -- network ----------------------------------------------------------------

    def arm(self) -> None:
        self.armed = True
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self.network())

    async def drop_connection(self) -> None:
        ws, self.ws = self.ws, None
        if ws is not None:
            try:
                await ws.close()
            except (ConnectionClosed, OSError):
                pass

    async def network(self) -> None:
        self.set_state("CONNECTING")
        while self.armed:
            try:
                async with await connect(self.url, open_timeout=5) as ws:
                    self.ws = ws
                    await self.session(ws)
            except Replaced:
                self.armed = False
                await self.drop_connection()
                self.set_state("OFFLINE")
                return
            except (OSError, ConnectionClosed, asyncio.TimeoutError, Exception) as exc:
                if isinstance(exc, asyncio.CancelledError):
                    raise
                log(f"connection attempt failed: {type(exc).__name__}: {exc}")
            finally:
                self.ws = None
            if not self.armed:
                return
            # Stay in CONNECTING across retries: a failed attempt is a
            # self-transition, so no state event is emitted.
            self.set_state("CONNECTING")
            await asyncio.sleep(RETRY_S)

    async def session(self, ws) -> None:
        await self.frame(ws, {"v": 1, "type": "hello", "name": self.name})
        async for raw in ws:
            if isinstance(raw, (bytes, bytearray)):
                continue
            try:
                frame = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(frame, dict) or frame.get("v") != 1:
                continue
            kind = frame.get("type")
            if kind == "welcome":
                self.set_state("SYNCING")
            elif kind == "sync_done":
                self.set_state("ONLINE")
                for entry in list(self.outbox):
                    await self.transmit(entry)
            elif kind == "msg":
                await self.on_msg(ws, frame)
            elif kind == "ack":
                self.on_ack(frame)
            elif kind == "error":
                if frame.get("code") == "replaced":
                    raise Replaced()
                self.on_error(frame)
            # any other type is ignored

    async def frame(self, ws, payload: dict) -> None:
        await ws.send(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))

    async def transmit(self, entry: dict) -> None:
        if self.ws is None:
            return
        await self.frame(self.ws, {"v": 1, "type": "send", **entry})

    async def on_msg(self, ws, frame: dict) -> None:
        msg_id = frame.get("id")
        if msg_id in self.seen:
            await self.frame(ws, {"v": 1, "type": "delivered", "id": msg_id})
            return
        self.seen.append(msg_id)
        self.save_seen()
        emit({
            "type": "received",
            "id": msg_id,
            "from": frame.get("from"),
            "text": frame.get("text"),
        })
        await self.frame(ws, {"v": 1, "type": "delivered", "id": msg_id})

    def on_ack(self, frame: dict) -> None:
        msg_id = frame.get("id")
        remaining = [e for e in self.outbox if e["id"] != msg_id]
        if len(remaining) == len(self.outbox):
            return
        self.outbox = remaining
        self.save_outbox()
        emit({"type": "sent", "id": msg_id})

    def on_error(self, frame: dict) -> None:
        code = frame.get("code")
        ref = frame.get("ref_id")
        event = {"type": "error", "code": code, "message": frame.get("message", "")}
        if ref is not None:
            event["ref_id"] = ref
            if code in ("bad_name", "bad_text", "bad_frame"):
                remaining = [e for e in self.outbox if e["id"] != ref]
                if len(remaining) != len(self.outbox):
                    self.outbox = remaining
                    self.save_outbox()
        emit(event)


async def amain(url: str, data_dir: Path) -> int:
    client = MockClient(url, data_dir)
    emit({"type": "ready", "state": client.state})
    if client.name is not None:
        emit({"type": "logged_in", "name": client.name})
        client.arm()

    lines: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def reader() -> None:
        for line in sys.stdin:
            loop.call_soon_threadsafe(lines.put_nowait, line.rstrip("\n"))
        loop.call_soon_threadsafe(lines.put_nowait, None)

    threading.Thread(target=reader, daemon=True).start()

    while True:
        line = await lines.get()
        if line is None:  # stdin EOF behaves as quit
            break
        await client.command(line)
        if client.stop:
            break

    client.armed = False
    if client.task is not None:
        client.task.cancel()
    await client.drop_connection()
    return 0


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="python -m mock_client", add_help=True)
    parser.add_argument("--server", required=True)
    parser.add_argument("--data-dir", required=True)
    args = parser.parse_args(argv)
    try:
        return asyncio.run(amain(args.server, Path(args.data_dir)))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
