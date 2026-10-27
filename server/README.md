# server/ — HAND-WRITTEN, NOT GENERATED

**This directory is outside generator discipline.** It is written and maintained by hand.

- No file here carries the `GENERATED from spec/` header, and none ever should.
- A generation run MUST NOT create, edit, or delete anything here (CLAUDE.md §2).
- It has no requirement-ID citation obligation, though tests reference IDs so failures
  point back at the spec.

It is a reference implementation of the **server side** of `spec/core/protocol.md`,
written to give the generated clients something to talk to. The clients are the generated
artifact; this is scaffolding.

## Scope

- In-memory only. Nothing is persisted; restarting the server forgets every message,
  dedup record, and name binding.
- Single process, single event loop, no locking beyond per-connection send ordering.
- No authentication (REQ-SYNC-012), no authorization, no rate limiting, no TLS.
- Implements exactly `v1`: no frame type, field, or error code beyond the spec.

Not suitable for anything but local testing.

## Run

```bash
python -m server --port 8765
```

From the repository root. `--host` defaults to `127.0.0.1`; `--log-level` to `info`.
Human-readable structured logs go to **stderr**, one `key=value` record per line.

## Test

```bash
python -m pytest server/tests -q
```

The tests speak raw WebSocket frames — they do not use a client — so they pin the wire
contract independently of any generated code. Each test names the requirement IDs it
covers.

## Layout

| File | Role |
| --- | --- |
| `validate.py` | name / id / text validation per REQ-NAME, REQ-MSGID, REQ-TEXT |
| `store.py` | in-memory message store, dedup set, per-recipient FIFO queues |
| `app.py` | the connection handler: framing, handshake, store-and-forward |
| `__main__.py` | CLI entry point |
| `tests/` | pytest suite over raw frames |
