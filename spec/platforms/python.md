# Platform Spec: Python CLI

**Scope: idioms, libraries, and build only. This file defines no behavior.**

Every behavioral question — what an event contains, when it is emitted, what happens on
reconnect — is answered by `spec/core/`. If this file ever appears to contradict
`spec/core/`, the core spec wins and this file is the bug. If a behavior is missing from
`spec/core/`, stop and report the ambiguity (CLAUDE.md §2); do not settle it here.

Target directory: `clients/python/` (generated only).

## Toolchain

| Item | Requirement |
| --- | --- |
| Language | **Python 3.11+** (use `match`, `asyncio.TaskGroup`, `tomllib` freely) |
| Transport | the **`websockets`** package, asyncio API |
| JSON | **stdlib `json`** only |
| Packaging | `pyproject.toml` |
| Entry point | `python -m client` |

## Dependencies

Allowed: `websockets`, plus the standard library.

Forbidden:

- Any chat, messaging, or realtime SDK. The protocol is implemented directly from
  `spec/core/protocol.md`.
- Any other WebSocket library (`aiohttp`, `websocket-client`, …).
- Any third-party JSON library (`orjson`, `ujson`, `pydantic`, …) — stdlib `json` is
  required so number and string handling is identical across platforms.

## Layout

```
clients/python/
  pyproject.toml
  client/
    __init__.py
    __main__.py          # argparse, then hand off to the client
    …
```

The package directory MUST be named `client`, because `platforms/python.yaml` runs
`python -m client` with `clients/python/` as the working directory.

## Idioms

- Use `websockets.asyncio.client.connect` (the current asyncio API). Do not use the
  removed legacy `websockets.connect` interface.
- Run one event loop. Read stdin without blocking it: either
  `loop.connect_read_pipe` / `asyncio.StreamReader`, or a dedicated thread feeding an
  `asyncio.Queue` via `loop.call_soon_threadsafe`. A bare `input()` in a coroutine
  stalls the whole client and will fail conformance.
- Keep one owner of client state (a single coroutine consuming a command/frame queue), so
  the event stream is the deterministic serialisation REQ-STATE-008 and REQ-STDIO-008
  require.
- Emit events with `json.dumps(event, ensure_ascii=False, separators=(",", ":"))` then
  `print(..., flush=True)`. `flush=True` on every event satisfies REQ-STDIO-003; stdout
  is a pipe under the conformance runner, so it is block-buffered without it.
- Reconfigure the streams for UTF-8 explicitly:
  `sys.stdout.reconfigure(encoding="utf-8", newline="\n")` and the same for `stdin` and
  `stderr`. Do not rely on the host locale.
- Send human-readable logging to `stderr` via `logging` (REQ-STDIO-005).
- Catch `websockets.exceptions.ConnectionClosed` and `OSError` around the connection;
  neither may escape as a traceback on stdout.

## Atomic writes

The temp-file-plus-rename idiom of REQ-PERSIST-002:

```python
tmp = target.with_suffix(target.suffix + ".tmp")
with open(tmp, "w", encoding="utf-8", newline="\n") as f:
    json.dump(state, f, ensure_ascii=False)
    f.flush()
    os.fsync(f.fileno())
os.replace(tmp, target)
```

`os.replace` is required rather than `os.rename`: it is atomic **and** overwrites an
existing file on Windows as well as POSIX. Keep the temp file in the target directory.

## Text length

`len(str)` in Python counts **code points**, which is exactly the unit REQ-TEXT-001
specifies — no conversion needed. Do not measure with `len(text.encode())`.

## Build and run

```
python3 -m client --server ws://127.0.0.1:8765/ws --data-dir .data/alice    # posix
python  -m client --server ws://127.0.0.1:8765/ws --data-dir .data/alice    # windows
```

Both run with `clients/python/` as the working directory (`platforms/python.yaml`).
There is no compile step. The manifest's `build_cmd` is
`python -m pip install -e .`, run with `clients/python/` as the working directory, so the
generated `pyproject.toml` MUST be installable in editable mode:

- declare a PEP 517 `[build-system]` with a standard backend (`setuptools>=68` and
  `setuptools.build_meta` is fine);
- declare `requires-python = ">=3.11"` and `dependencies = ["websockets>=14"]`;
- make the `client` package discoverable, either by letting setuptools auto-discover it
  or with an explicit `[tool.setuptools] packages = ["client"]`.

The install puts the package in the interpreter that runs the build, which is what makes
`python -m client` resolve from any working directory.
