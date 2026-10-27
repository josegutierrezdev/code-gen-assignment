# GENERATED from spec/ by the generator - do not edit by hand
#
# On-disk state: identity, outbox, seen set (REQ-PERSIST-001).

from __future__ import annotations

import json
import os
import re
from pathlib import Path

# REQ-NAME-001: 1-32 chars from [a-zA-Z0-9_-]. REQ-NAME-002, REQ-NAME-003:
# case-sensitive, and never trimmed, case-folded or Unicode-normalised, so the
# pattern is anchored and total.
NAME_RE = re.compile(r"\A[A-Za-z0-9_-]{1,32}\Z")

TEXT_MIN = 1
TEXT_MAX = 4000


class CorruptState(Exception):
    """REQ-PERSIST-004: a state file exists but is unreadable or off-schema."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def valid_name(value: object) -> bool:
    # REQ-NAME-001
    return isinstance(value, str) and NAME_RE.match(value) is not None


def valid_text(value: object) -> bool:
    # REQ-TEXT-002: out-of-range length is invalid.
    # REQ-TEXT-003: text is opaque -- measured here, never rewritten.
    # REQ-TEXT-004: any JSON-legal code point is allowed, including newlines,
    # tabs, control characters and emoji.
    # REQ-TEXT-001: length is counted in Unicode code points, which is exactly what
    # len() measures in Python -- never len(text.encode()).
    # REQ-TEXT-005: lone surrogates are invalid.
    if not isinstance(value, str) or not (TEXT_MIN <= len(value) <= TEXT_MAX):
        return False
    return not any(0xD800 <= ord(ch) <= 0xDFFF for ch in value)


def write_atomic(path: Path, data: dict) -> None:
    # REQ-PERSIST-002: serialise in full to a temp file in the same directory, flush
    # it to durable storage, then rename over the target. Never modify in place,
    # never truncate-then-write, never append. os.replace is atomic AND overwrites
    # an existing file on Windows as well as POSIX.
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def read_json(path: Path) -> dict | None:
    # REQ-PERSIST-003: UTF-8 JSON objects carrying "v": 1. A missing file is empty
    # state, not an error.
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CorruptState(f"{path.name}: {exc}") from exc
    if not isinstance(data, dict) or data.get("v") != 1:
        raise CorruptState(f"{path.name}: not a v1 JSON object")
    return data


class Store:
    """The three state files and nothing else (REQ-PERSIST-001).

    REQ-PERSIST-006: everything is rooted at the given data-dir, so clients with
    different data-dirs share nothing and can run concurrently.
    REQ-PERSIST-007: sharing one data-dir between processes is unsupported, and
    this class does not try to detect it.
    REQ-INBOUND-006: the seen set is never evicted from.
    """

    def __init__(self, data_dir: Path) -> None:
        # REQ-PERSIST-005: create the data dir, including missing parents.
        self.dir = data_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.identity_path = self.dir / "identity.json"
        self.outbox_path = self.dir / "outbox.json"
        self.seen_path = self.dir / "seen.json"
        # REQ-PERSIST-008: everything is loaded before `ready` is emitted.
        self.name: str | None = None
        self.outbox: list[dict] = []
        self.seen: set[str] = set()
        self._load()

    def _load(self) -> None:
        identity = read_json(self.identity_path)
        if identity is not None:
            name = identity.get("name")
            # REQ-IDENTITY-002: a stored name that fails REQ-NAME-001 is corrupt state.
            if not valid_name(name):
                raise CorruptState("identity.json: name is not valid")
            self.name = name

        outbox = read_json(self.outbox_path)
        if outbox is not None:
            entries = outbox.get("entries")
            if not isinstance(entries, list):
                raise CorruptState("outbox.json: entries is not a list")
            for entry in entries:
                if (
                    not isinstance(entry, dict)
                    or not isinstance(entry.get("id"), str)
                    or not valid_name(entry.get("to"))
                    or not valid_text(entry.get("text"))
                ):
                    raise CorruptState("outbox.json: malformed entry")
            # REQ-OUTBOX-001: array order is queue order, preserved across restarts.
            self.outbox = [
                {"id": e["id"], "to": e["to"], "text": e["text"]} for e in entries
            ]

        seen = read_json(self.seen_path)
        if seen is not None:
            ids = seen.get("seen")
            if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
                raise CorruptState("seen.json: seen is not a list of strings")
            self.seen = set(ids)

    # -- writers ---------------------------------------------------------------

    def save_identity(self, name: str) -> None:
        # REQ-IDENTITY-002: persisted before `logged_in` and before any network attempt.
        self.name = name
        write_atomic(self.identity_path, {"v": 1, "name": name})

    def save_outbox(self) -> None:
        # REQ-OUTBOX-013
        write_atomic(self.outbox_path, {"v": 1, "entries": self.outbox})

    def save_seen(self) -> None:
        # REQ-INBOUND-008: array order is not significant.
        write_atomic(self.seen_path, {"v": 1, "seen": sorted(self.seen)})
