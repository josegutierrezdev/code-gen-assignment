# Core Spec: CLI Contract

Status: normative. Protocol version: `v1`.

This document defines the **observable interface** every generated client MUST share:
invocation, stdin command grammar, and the JSON Lines event stream on stdout. It is the
surface the conformance runner drives and compares; two conformant clients are
indistinguishable through it.

It is **platform-neutral**. The concrete run command per platform lives in that
platform's manifest under `platforms/`; everything else here is identical across
platforms.

RFC 2119 keywords apply. Every normative statement carries a stable ID.

---

## 1. Invocation — `REQ-CLI`

- **REQ-CLI-001** The invocation MUST be:

  ```
  <run-cmd> --server <ws-url> --data-dir <path>
  ```

  Both flags are **required**. `<ws-url>` is a WebSocket URL per REQ-WIRE-001;
  `<path>` is the client's data directory (REQ-PERSIST-001).
- **REQ-CLI-002** `<run-cmd>` is platform-specific and MUST be declared in that
  platform's manifest. The flag names, their values, and every behavior in this document
  MUST be identical across platforms.
- **REQ-CLI-003** Flags MAY appear in any order. The separated form `--server <value>`
  MUST be supported; the joined form `--server=<value>` MAY be supported.
- **REQ-CLI-004** A missing required flag, a flag without a value, or an unrecognised
  flag MUST cause the client to write a human-readable message to **stderr** and exit
  with status `2`, having written **nothing** to stdout — in particular no `ready` event.
- **REQ-CLI-005** The client MUST create `<data-dir>` as specified in REQ-PERSIST-005. A
  `--data-dir` that exists but is not a directory, or is not writable, MUST be handled per
  REQ-CLI-004.
- **REQ-CLI-006** Exit statuses are exactly: `0` on `quit` or stdin EOF; `2` on a usage
  or startup error (REQ-CLI-004) or corrupt state (REQ-PERSIST-004); `1` on any other
  fatal fault. No other status may be used.
- **REQ-CLI-007** The client MUST NOT require the server to be reachable at startup. With
  an unreachable server it MUST still emit `ready`, accept commands, and queue sends.
- **REQ-CLI-008** The client MUST NOT read configuration from environment variables,
  config files outside `<data-dir>`, or interactive prompts. The two flags and stdin are
  the entire input surface.

## 2. stdin and stdout — `REQ-STDIO`

- **REQ-STDIO-001** stdin is a stream of commands, **one per line**, terminated by LF
  (`\n`). A trailing CR before the LF MUST be stripped. No other trimming is performed
  (REQ-CMD-003).
- **REQ-STDIO-002** stdout MUST carry **only** JSON Lines events: exactly one JSON object
  per line, UTF-8, terminated by a single LF. Nothing else may ever appear on stdout — no
  banners, no prompts, no progress output, no blank lines, no log lines, no
  pretty-printing.
- **REQ-STDIO-003** Each event MUST be flushed immediately on write. The client MUST NOT
  buffer events for later, batch them, or rely on process exit to flush, because the
  conformance runner reads stdout synchronously and blocks on expected events.
- **REQ-STDIO-005** All human-readable logging, diagnostics, stack traces, and library
  output MUST go to **stderr**. stderr content is never compared by tests, MUST NOT
  affect a verdict, and MAY be empty.
- **REQ-STDIO-006** Events MUST be single-line: the JSON MUST NOT contain literal
  newlines. Newlines inside string values MUST be escaped as `\n` per RFC 8259.
- **REQ-STDIO-007** EOF on stdin MUST be treated exactly as the `quit` command (T18).
- **REQ-STDIO-008** Commands MUST be processed strictly in the order read, one at a time.
  The client MUST NOT begin a command before the previous one's synchronous effects —
  including its durable writes and its emitted events — are complete.
- **REQ-STDIO-009** The client MUST continue reading stdin while offline, connecting,
  syncing, and online. Network state MUST NOT block command intake.

## 3. Commands — `REQ-CMD`

- **REQ-CMD-001** The command grammar is exactly:

  | Command | Form | Effect |
  | --- | --- | --- |
  | login | `login <name>` | establish identity (REQ-IDENTITY-002) |
  | send | `send <to> <text...>` | queue and possibly transmit a message (REQ-OUTBOX-003) |
  | offline | `offline` | simulate network loss (REQ-TESTHOOK-002) |
  | online | `online` | resume networking (REQ-RECONNECT-005) |
  | quit | `quit` | exit cleanly with status 0 |

- **REQ-CMD-002** Command words are lowercase and **case-sensitive**: `LOGIN` and `Login`
  are unknown commands. Tokens are separated by one or more spaces (`U+0020`).
- **REQ-CMD-003** For `send`, `<to>` is the token after the command word, and `<text...>`
  is the **entire remainder of the line** after the single space that follows `<to>`,
  taken verbatim — including further spaces, leading spaces within it, and any
  punctuation. The client MUST NOT trim, collapse, split, or re-quote it, and MUST NOT
  interpret quotes or backslashes.
- **REQ-CMD-004** An empty line, or a line containing only spaces, MUST be ignored: no
  event, no state change, no error.
- **REQ-CMD-005** An unrecognised command word MUST produce
  `error{code:"unknown_command"}`. The client MUST NOT exit and MUST continue reading
  stdin.
- **REQ-CMD-006** A recognised command with the wrong number of arguments — `login` with
  none or with extra tokens, `send` with fewer than two tokens after it, `offline` /
  `online` / `quit` with any argument — MUST produce `error{code:"bad_args"}` and MUST
  have no other effect.
- **REQ-CMD-007** The client MUST NOT crash, hang, or exit on any stdin content.
  Arbitrary bytes, very long lines, and invalid UTF-8 MUST produce an `error` event at
  worst (invalid UTF-8 on a line MUST be reported as `error{code:"bad_args"}`).
- **REQ-CMD-008** `quit` MUST close the connection and exit with status `0`. It MUST NOT
  wait for pending acks, MUST NOT flush the outbox, and MUST NOT drop outbox entries —
  all state is already durable (REQ-OUTBOX-002). `quit` MUST NOT emit a `state` event.

## 4. Event schemas — `REQ-EVENT`

Every event is a single-line JSON object with a `"type"` field. Field names and all enum
values are **exact and case-sensitive**. All field values are JSON strings unless stated
otherwise.

- **REQ-EVENT-001** Every event MUST have the form `{"type":"<name>", ...}` where
  `<name>` is one of: `ready`, `logged_in`, `state`, `queued`, `sent`, `received`,
  `error`. A client MUST NOT emit any other event type in `v1`.

- **REQ-EVENT-002** `ready` — `{"type":"ready","state":<string>}`

  | Field | Value |
  | --- | --- |
  | `state` | `"NO_IDENTITY"` or `"OFFLINE"` |

  MUST be emitted exactly once, as the **first** line on stdout, after loading persisted
  state (REQ-PERSIST-008) and before reading the first stdin command. `state` is
  `"NO_IDENTITY"` when no identity was loaded (T1) and `"OFFLINE"` when one was (T2).

- **REQ-EVENT-003** `logged_in` — `{"type":"logged_in","name":<string>}`

  Emitted when an identity becomes active: after a successful `login` (T4), and at
  startup when an identity is loaded from disk (T2, after `ready`). MUST be emitted at
  most once per process. `name` MUST be the exact stored name.

- **REQ-EVENT-004** `state` — `{"type":"state","from":<string>,"to":<string>}`

  | Field | Value |
  | --- | --- |
  | `from` | previous state |
  | `to` | new state |

  Both MUST be one of `"NO_IDENTITY"`, `"OFFLINE"`, `"CONNECTING"`, `"SYNCING"`,
  `"ONLINE"`, exactly as spelled. Emitted per REQ-STATE-002; never when `from` equals
  `to`, so retry attempts emit nothing (REQ-STATE-003, REQ-RECONNECT-009).

- **REQ-EVENT-005** `queued` — `{"type":"queued","id":<string>,"to":<string>,"text":<string>}`

  Emitted once per accepted `send`, after the outbox write succeeds and before any
  transmission (REQ-OUTBOX-003). `id` is the client-generated UUIDv4 (REQ-MSGID-001);
  `text` is verbatim per REQ-CMD-003. Not emitted for entries restored from disk
  (REQ-OUTBOX-008), nor for rejected sends (REQ-OUTBOX-012, REQ-STATE-006).

- **REQ-EVENT-006** `sent` — `{"type":"sent","id":<string>}`

  Emitted **only** on `ack{id}` from the server, for an id present in the outbox, after
  the outbox write that removes it, at most once per id (REQ-OUTBOX-005). It means the
  server has taken responsibility — not that the recipient has seen it.

- **REQ-EVENT-007** `received` — `{"type":"received","id":<string>,"from":<string>,"text":<string>}`

  Emitted once per distinct inbound message id (REQ-INBOUND-003), in arrival order
  (REQ-INBOUND-005). `text` MUST be code-point identical to what the sender sent
  (REQ-TEXT-003). The wire frame's `to` and `server_ts` MUST NOT be surfaced
  (REQ-TIME-004, REQ-EVENT-009).

- **REQ-EVENT-008** `error` — `{"type":"error","code":<string>,"message":<string>,"ref_id":<string>?}`

  | Field | Value |
  | --- | --- |
  | `code` | a stable token from REQ-ERRCODE-001, or a server code relayed verbatim (REQ-ERR-004) |
  | `message` | human-readable, free-form, never compared (REQ-COMPARE-007) |
  | `ref_id` | **optional**; the message id this error concerns, per REQ-ERRCODE-003 |

  An `error` MUST NOT terminate the process except where REQ-PERSIST-004 requires it.

- **REQ-EVENT-009** Events MUST NOT carry fields beyond those listed for their type in
  `v1`.

## 5. Client error codes — `REQ-ERRCODE`

- **REQ-ERRCODE-001** Client-originated `error.code` values are exactly:

  | `code` | Raised when | `ref_id` |
  | --- | --- | --- |
  | `unknown_command` | unrecognised command word (REQ-CMD-005) | no |
  | `bad_args` | wrong argument count, or an undecodable line (REQ-CMD-006, REQ-CMD-007) | no |
  | `bad_name` | invalid name in `login`, or invalid `<to>` in `send` (REQ-IDENTITY-003, REQ-OUTBOX-012) | no |
  | `bad_text` | `<text...>` violates REQ-TEXT-001 (REQ-OUTBOX-012) | no |
  | `not_logged_in` | `send` with no identity (REQ-STATE-006) | no |
  | `already_logged_in` | `login` when an identity exists (REQ-IDENTITY-005) | no |
  | `corrupt_state` | a state file fails to load (REQ-PERSIST-004) | no |

- **REQ-ERRCODE-002** A server `error` frame MUST be surfaced as an `error` event with
  the server's `code` relayed **verbatim**, including codes unknown to the client
  (REQ-ERR-004). The client MUST NOT translate, prefix, or remap server codes.
- **REQ-ERRCODE-003** `error.ref_id` MUST be present whenever the error concerns a
  specific message id, and MUST equal that id. In particular it MUST be present on:
  - every permanent rejection that drops an outbox entry (REQ-OUTBOX-009) — the drop
    MUST be visible and attributable to the exact message; and
  - every relayed server error that carried a `ref_id` (REQ-OUTBOX-010).

  It MUST be absent otherwise — for locally rejected commands (REQ-ERRCODE-001), which
  never consume an id (REQ-OUTBOX-012), and for server errors with no `ref_id`.

## 6. Comparison rules — `REQ-COMPARE`

These rules bind the conformance runner as much as the clients.

- **REQ-COMPARE-001** Tests compare an event's `type` plus the fields listed for that
  type in §4 — nothing else. Fields not listed for a type MUST be ignored by the
  comparison, so a future additive field cannot fail an existing test. An optional listed
  field (`error.ref_id`) MUST be compared when the expectation names it, including
  asserting its absence.
- **REQ-COMPARE-003** No event carries a timestamp in `v1`, and tests MUST NOT assert on
  wall-clock time or on elapsed duration (clients must not surface clock readings:
  REQ-TIME-004).
- **REQ-COMPARE-004** Field names and enum values are **exact and case-sensitive**:
  `"ONLINE"` is not `"online"`, `"logged_in"` is not `"loggedIn"`.
- **REQ-COMPARE-005** Event order is significant **within one client's stdout stream**
  and MUST be compared as a sequence. Across two clients, only causal order is
  guaranteed: a `received` on one client may interleave arbitrarily with unrelated events
  on another.
- **REQ-COMPARE-006** JSON key order within an event is insignificant, as is
  insignificant whitespace inside the line.
- **REQ-COMPARE-007** `error.message` MUST NOT be compared. `error.code` MUST be compared
  exactly.
- **REQ-COMPARE-008** Message ids are compared by **correlation**, not by literal value:
  an id observed in `queued` is matched against the id in the later `sent` or
  `error.ref_id` on that client, and against the `received` id on the recipient. Tests
  MUST NOT hard-code UUID values.

## 7. Worked session (non-normative)

```
$ <run-cmd> --server ws://127.0.0.1:8765/ws --data-dir .data/alice

stdout                                    stdin
{"type":"ready","state":"NO_IDENTITY"}
                                          login alice
{"type":"logged_in","name":"alice"}
{"type":"state","from":"NO_IDENTITY","to":"CONNECTING"}
{"type":"state","from":"CONNECTING","to":"SYNCING"}
{"type":"state","from":"SYNCING","to":"ONLINE"}
                                          offline
{"type":"state","from":"ONLINE","to":"OFFLINE"}
                                          send bob hey there
{"type":"queued","id":"7b1f9a3c-...","to":"bob","text":"hey there"}
                                          online
{"type":"state","from":"OFFLINE","to":"CONNECTING"}
{"type":"state","from":"CONNECTING","to":"SYNCING"}
{"type":"state","from":"SYNCING","to":"ONLINE"}
{"type":"sent","id":"7b1f9a3c-..."}
{"type":"received","id":"9c22b1de-...","from":"bob","text":"hi alice"}
                                          quit
```

Server killed while ONLINE, then restarted 30 s later — note the single `state` event
for the loss, and none for the ~30 retry attempts (REQ-RECONNECT-009):

```
{"type":"state","from":"ONLINE","to":"CONNECTING"}
                                          send bob still here?
{"type":"queued","id":"4d08c7e1-...","to":"bob","text":"still here?"}
{"type":"state","from":"CONNECTING","to":"SYNCING"}
{"type":"state","from":"SYNCING","to":"ONLINE"}
{"type":"sent","id":"4d08c7e1-..."}
```
