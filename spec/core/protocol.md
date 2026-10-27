# Core Spec: Wire Protocol

Status: normative. Protocol version: `v1`.

This document defines the wire protocol between a client and the server. It is
**platform-neutral**: it says nothing about languages, libraries, file layout, or build
systems. Those live in `spec/platforms/`.

The key words MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are to be interpreted as
described in RFC 2119. Every normative statement carries a stable ID. IDs are never
renumbered or reused; numbering may have gaps where requirements were consolidated.

Terminology:

- **sender** — the client that issued a `send`.
- **recipient** — the client named by `send.to`.
- **session** — one WebSocket connection that has completed a successful `hello`.
- **held message** — a message the server has accepted but not yet had confirmed by a
  `delivered` from its recipient.
- **code point** — one Unicode scalar value. Lengths are counted in code points unless
  stated otherwise.

---

## 1. Transport — `REQ-WIRE`

- **REQ-WIRE-001** The transport MUST be WebSocket. The server MUST expose exactly one
  endpoint at path `/ws`; clients MUST connect to a URL of the form
  `ws://<host>:<port>/ws`.
- **REQ-WIRE-002** Each WebSocket **text** frame MUST contain exactly one complete JSON
  object. Implementations MUST NOT pack multiple objects into one frame, MUST NOT split
  one object across frames, and MUST NOT rely on newline delimiting inside a frame.
- **REQ-WIRE-003** All frames MUST be WebSocket text frames encoded as UTF-8. Endpoints
  MUST NOT send binary frames; a received binary frame MUST be ignored.
- **REQ-WIRE-005** Frame payloads MUST be JSON conforming to RFC 8259, and the top-level
  value MUST be an object — an array, string, number, or `null` at top level is invalid.
  On receiving a text frame that is not well-formed JSON, or whose top-level value is not
  an object, the server MUST reply `error{code:"bad_frame"}` and MUST keep the connection
  open (REQ-ERR-007). A client receiving such a frame MUST ignore it and MUST NOT close
  the connection.
- **REQ-WIRE-006** Endpoints MUST NOT make operation conditional on WebSocket
  subprotocols, extensions, or compression negotiation; a connection offering none MUST
  be accepted.
- **REQ-WIRE-007** There is no application-level heartbeat in `v1`. Endpoints MAY use
  WebSocket ping/pong; liveness MUST NOT be inferred from application frames.

## 2. Frame envelope — `REQ-FRAME`

- **REQ-FRAME-001** Every frame MUST contain `"v"` (JSON number, exactly `1`) and
  `"type"` (non-empty JSON string). All other fields are type-specific.
- **REQ-FRAME-002** A frame whose `v` is missing, not a number, or not `1` MUST be
  rejected by the server with `error{code:"bad_version"}` and MUST NOT be acted on. A
  client MUST ignore such a frame.
- **REQ-FRAME-003** A frame whose `type` is a valid string but unrecognised MUST be
  **ignored silently** by the receiver — no error, no close, no state change. This is the
  forward-compatibility rule: a `v1` endpoint MUST tolerate frame types added later.
- **REQ-FRAME-004** Unrecognised **fields** on a recognised `type` MUST be ignored. An
  endpoint MUST NOT reject, error on, or echo back unknown fields.
- **REQ-FRAME-005** A recognised `type` that is missing a required field, or whose field
  has the wrong JSON type, MUST be rejected by the server with `error{code:"bad_frame"}`,
  including `ref_id` when the frame carried a usable `id`. The frame MUST NOT be acted on.
- **REQ-FRAME-006** Implementations MUST NOT depend on the order of keys in a JSON
  object, nor on whitespace inside a frame.
- **REQ-FRAME-007** Senders MUST NOT emit fields beyond those defined here for a `v1`
  frame type. (Receivers still tolerate them per REQ-FRAME-004.)

## 3. Client-to-server frames — `REQ-C2S`

- **REQ-C2S-001** `hello` — `{"v":1,"type":"hello","name":<string>}`. `name` is required
  and MUST satisfy REQ-NAME-001. It claims an identity for this connection.
- **REQ-C2S-002** `send` — `{"v":1,"type":"send","id":<string>,"to":<string>,"text":<string>}`.
  All three fields are required. `id` MUST satisfy REQ-MSGID-001, `to` MUST satisfy
  REQ-NAME-001, `text` MUST satisfy REQ-TEXT-001.
- **REQ-C2S-003** `delivered` — `{"v":1,"type":"delivered","id":<string>}`. `id` is
  required. It confirms that the client has durably accepted the message with that id,
  and releases the server's copy.
- **REQ-C2S-004** A client MUST NOT send any frame type other than `hello`, `send`, and
  `delivered` in `v1`.
- **REQ-C2S-005** The server MUST reject a `send` or `delivered` received on a connection
  that has not completed a successful `hello` with `error{code:"no_hello"}`, and MUST NOT
  act on the frame.

## 4. Server-to-client frames — `REQ-S2C`

- **REQ-S2C-001** `welcome` — `{"v":1,"type":"welcome","name":<string>,"pending":<number>}`.
  `name` MUST be the accepted name echoed exactly from `hello`. `pending` MUST be a
  non-negative integer: the number of messages held for `name` at the moment `welcome` is
  emitted (REQ-SYNC-004).
- **REQ-S2C-002** `sync_done` — `{"v":1,"type":"sync_done"}`. No type-specific fields. It
  marks the end of the replay phase (REQ-SYNC-006).
- **REQ-S2C-003** `ack` — `{"v":1,"type":"ack","id":<string>}`. It tells the sender the
  server has taken durable responsibility for the message with that id.
- **REQ-S2C-004** `msg` — `{"v":1,"type":"msg","id":<string>,"from":<string>,"to":<string>,"text":<string>,"server_ts":<number>}`.
  `from` is the sender's name, `to` the recipient's name, `text` the sender's text
  unmodified, `server_ts` as defined by REQ-TIME-001.
- **REQ-S2C-005** `error` — `{"v":1,"type":"error","code":<string>,"message":<string>,"ref_id":<string>?}`.
  `code` and `message` are required; `ref_id` is optional per REQ-ERR-002.
- **REQ-S2C-006** The server MUST NOT send any frame type other than `welcome`,
  `sync_done`, `ack`, `msg`, and `error` in `v1`.

## 5. Message identity — `REQ-MSGID`

- **REQ-MSGID-001** A message `id` MUST be a UUID version 4 in canonical lowercase
  textual form: 36 characters, `8-4-4-4-12` lowercase hexadecimal digits separated by
  hyphens.
- **REQ-MSGID-002** The `id` MUST be generated by the **sending client**, at the moment
  the user issues the send — before the message is persisted and before any network
  attempt. The server MUST NOT generate, rewrite, or normalise ids at any point, from
  accept through every re-push.
- **REQ-MSGID-003** The `id` is the **deduplication key end to end**: sender outbox,
  server store, and recipient inbox all key on it. A retransmission MUST reuse the
  original id. A client MUST NOT reassign an id for any reason, including reconnect,
  restart, or an error response.
- **REQ-MSGID-004** Beyond the format check of REQ-MSGID-001, ids MUST be treated as
  opaque. No endpoint may derive ordering, timing, or identity information from an id.
- **REQ-MSGID-005** Two distinct messages MUST NOT share an id. Clients MUST generate ids
  from a randomness source sufficient to make collision negligible.

## 6. Server-side deduplication — `REQ-DEDUP`

- **REQ-DEDUP-001** The server MUST durably record the `id` of every `send` it accepts,
  and MUST retain that record for the server's lifetime — including after the message has
  been delivered and dropped.
- **REQ-DEDUP-002** A `send` carrying an already-seen `id` MUST be treated as **success**:
  the server MUST re-emit `ack{id}` to the requesting sender, and MUST NOT store the
  message again, MUST NOT forward it again, and MUST NOT increase any recipient's
  `pending` count. This holds in every state of the message — not yet pushed, pushed but
  unconfirmed, or confirmed and dropped — and the response is always a plain `ack{id}`,
  never an error.
- **REQ-DEDUP-004** Deduplication MUST be keyed on `id` alone, independent of connection,
  session, and sender identity, and MUST survive the sender disconnecting and
  reconnecting.
- **REQ-DEDUP-005** For a duplicate `send` the server MUST ignore the `to` and `text`
  fields and MUST NOT alter the stored message. The first accepted `send` for an id
  defines that message permanently.
- **REQ-DEDUP-006** The server MUST validate a duplicate `send`'s envelope and id format
  as usual (REQ-FRAME-005, REQ-MSGID-001) before applying REQ-DEDUP-002.

## 7. Store and forward — `REQ-SNF`

- **REQ-SNF-001** On accepting a valid, non-duplicate `send`, the server MUST, in this
  order: durably record the message with its id and a `server_ts`; emit `ack{id}` to the
  sender; then attempt delivery to the recipient. The `ack` MUST precede any `msg` push
  arising from that `send`.
- **REQ-SNF-002** If the recipient has a synced session (REQ-SYNC-006), the server MUST
  push `msg` to it immediately.
- **REQ-SNF-003** If the recipient has no session, or has one that has not yet synced,
  the server MUST hold the message in a per-recipient FIFO queue.
- **REQ-SNF-005** The server MUST drop a held message **only** on receiving
  `delivered{id}` from a session whose name equals that message's `to`. Pushing a `msg`
  is therefore not deleting it: the server MUST retain the message until the recipient
  confirms it, so that a push lost to a dropped connection is recoverable. No timeout,
  push count, or disconnect may drop a message; the server MUST NOT bound a recipient's
  held queue in `v1` and MUST NOT drop a held message for capacity reasons.
- **REQ-SNF-006** On a recipient's next successful `hello`, every message still held for
  that name MUST be re-pushed, including messages already pushed on an earlier connection.
- **REQ-SNF-007** Messages for a recipient MUST be pushed in the order the server
  accepted them (REQ-SNF-001), on every push and re-push.
- **REQ-SNF-008** `delivered{id}` for an unknown id, an already-dropped id, or an id
  whose `to` is not the sending session's name MUST be ignored: no error, no state
  change. `delivered` is idempotent.
- **REQ-SNF-009** A `send` to a name the server has never seen MUST be accepted and
  acked; the message is held under that name until a session claims it. The server MUST
  NOT return an error for an unknown recipient and MUST NOT require registration.
- **REQ-SNF-010** A `send` whose `to` equals the sender's own name MUST be accepted and
  MUST follow the identical path, held or pushed to that same name under the ordinary
  rules.

A message's `id`, `from`, `to`, and `text` are immutable from accept through every
re-push; this follows from REQ-MSGID-002, REQ-NAME-003, and REQ-TEXT-003.

## 8. Time — `REQ-TIME`

- **REQ-TIME-001** `msg.server_ts` MUST be an integer count of milliseconds since
  1970-01-01T00:00:00Z, assigned by the server at accept time (REQ-SNF-001) and stored
  with the message.
- **REQ-TIME-002** `server_ts` MUST be identical on every push and re-push of the same
  message.
- **REQ-TIME-003** `server_ts` values MUST be non-decreasing in accept order within one
  server run. Equal values for distinct messages are permitted; ordering MUST be taken
  from REQ-SNF-007, never from `server_ts`.
- **REQ-TIME-004** Clients MUST NOT surface `server_ts` in any stdout event, and MUST NOT
  use it for ordering, deduplication, or retry decisions.

## 9. Handshake and sync ordering — `REQ-SYNC`

This ordering is deterministic and testable. It is the contract that makes offline
delivery and outbox flushing observable.

- **REQ-SYNC-001** Immediately after the WebSocket connection opens, the client's first
  frame MUST be `hello`.
- **REQ-SYNC-002** The client MUST NOT send `send` or `delivered` frames before it has
  received `welcome` on that connection.
- **REQ-SYNC-003** On a valid `hello` the server MUST reply `welcome{name,pending}`
  before any other frame on that connection.
- **REQ-SYNC-004** `pending` MUST equal the number of messages held for that name at the
  instant `welcome` is emitted — a snapshot. Messages accepted after that instant MUST NOT
  be counted in it.
- **REQ-SYNC-005** After `welcome` the server MUST push exactly those `pending` held
  messages, in the order given by REQ-SNF-007, with no other frame interleaved.
- **REQ-SYNC-006** After the last replayed `msg` the server MUST send `sync_done`. When
  `pending` is `0`, `sync_done` MUST immediately follow `welcome`. A session is **synced**
  once `sync_done` has been sent.
- **REQ-SYNC-007** A message accepted for this recipient during the replay window — after
  `welcome`, before `sync_done` — MUST NOT be pushed inside the window. It MUST be held
  and pushed after `sync_done`.
- **REQ-SYNC-008** The client MUST NOT flush its outbox until it has received
  `sync_done`. The required order is:
  `hello` → `welcome{pending:N}` → N `msg` frames in original order → `sync_done` →
  **only then** the client's outbox flush. It follows that no `ack` for a send made on
  this connection can appear before `sync_done`.
- **REQ-SYNC-010** A `hello` whose `name` is missing, not a string, or invalid per
  REQ-NAME-001 MUST be answered with `error{code:"bad_name"}`, after which the server MUST
  close the connection. No session is created.
- **REQ-SYNC-011** A second `hello` on a connection that already has a session MUST be
  answered with `error{code:"already_hello"}` and otherwise ignored: the existing session,
  name, and sync state are unchanged.
- **REQ-SYNC-012** The server MUST NOT require or honour authentication in `v1`. A valid
  name is a sufficient claim to that identity.

## 10. Session replacement — `REQ-SESSION`

- **REQ-SESSION-001** The server MUST hold at most one active session per name.
- **REQ-SESSION-002** When a valid `hello` names an identity that already has an active
  session, the **newest connection wins**: the server MUST send `error{code:"replaced"}`
  on the older connection and then close it.
- **REQ-SESSION-003** The server MUST send `error{code:"replaced"}` and close the older
  connection **before** sending `welcome` on the newer one, so replacement is observable
  in a fixed order.
- **REQ-SESSION-004** After replacement the newer connection MUST proceed through the
  ordinary handshake of §9, with `pending` computed as of its own `welcome`.
- **REQ-SESSION-007** When a connection closes for any reason — including a close caused
  by replacement — the server MUST discard that session's connection state, and MUST NOT
  discard any held message, dedup record, or name binding. Messages pushed to the closed
  session but not confirmed therefore remain held, and are re-pushed to the next session
  for that name per REQ-SNF-006.

A client that receives `error{code:"replaced"}` must not reconnect automatically;
that obligation is normative in REQ-RECONNECT-006.

## 11. Names — `REQ-NAME`

- **REQ-NAME-001** A name MUST be 1 to 32 characters inclusive, each drawn from
  `[a-zA-Z0-9_-]` (ASCII letters, ASCII digits, underscore, hyphen).
- **REQ-NAME-002** Names are **case-sensitive**. `Alice` and `alice` are different
  identities with separate sessions and separate held queues.
- **REQ-NAME-003** Names MUST NOT be trimmed, case-folded, Unicode-normalised, or
  otherwise rewritten by any endpoint, at any point from accept through every re-push. A
  name with leading or trailing whitespace is invalid, not trimmable.
- **REQ-NAME-005** An invalid `to` in `send` MUST be answered with
  `error{code:"bad_name",ref_id:<id>}`. The server MUST NOT ack it, MUST NOT store it, and
  MUST NOT record its id as seen. (An invalid name in `hello` is handled by
  REQ-SYNC-010.)

## 12. Text — `REQ-TEXT`

- **REQ-TEXT-001** `send.text` MUST be 1 to 4000 **Unicode code points** inclusive.
  Length is counted in code points — **not** bytes and **not** UTF-16 code units. A
  non-BMP character (for example an emoji outside the BMP) counts as exactly one.
- **REQ-TEXT-002** Text of length 0, or longer than 4000 code points, MUST be answered
  with `error{code:"bad_text",ref_id:<id>}`; the message MUST NOT be acked, stored, or
  recorded as seen.
- **REQ-TEXT-003** Text is opaque payload. No endpoint may trim, normalise, re-encode,
  escape, sanitise, or truncate it, at any point from accept through every re-push. The
  `text` a recipient receives MUST be code-point identical to the `text` the sender sent.
- **REQ-TEXT-004** Any Unicode code point permitted in a JSON string is permitted in
  `text`, including newlines, tabs, control characters, and emoji. Escaping follows
  RFC 8259; the choice between an escape sequence and a literal character is not
  semantically significant.
- **REQ-TEXT-005** Unpaired UTF-16 surrogates are invalid text and MUST be rejected with
  `error{code:"bad_text",ref_id:<id>}`.

## 13. Errors — `REQ-ERR`

- **REQ-ERR-001** `error.code` MUST be a stable, machine-readable, lowercase
  `snake_case` token drawn from REQ-ERR-003. `error.message` is human-readable, carries no
  contract, and MUST NOT be parsed or compared by any implementation or test.
- **REQ-ERR-002** `error.ref_id` MUST be present when the error is attributable to a
  specific message id, and MUST equal that id; it MUST be absent otherwise. A client MUST
  tolerate an absent `ref_id`.
- **REQ-ERR-003** The `v1` server error codes are exactly:

  | `code` | Meaning | Closes connection? | `ref_id` |
  | --- | --- | --- | --- |
  | `bad_frame` | Not JSON, not an object, or a known type with a missing/mistyped field | no | when known |
  | `bad_version` | `v` missing or not `1` | no | no |
  | `bad_name` | Invalid name in `hello`, or invalid `to` in `send` | on `hello` only | on `send` |
  | `bad_text` | `text` violates REQ-TEXT-001 or REQ-TEXT-005 | no | yes |
  | `no_hello` | `send`/`delivered` before a successful `hello` | no | no |
  | `already_hello` | Second `hello` on a session | no | no |
  | `replaced` | This session was displaced by a newer one for the same name | yes | no |
  | `internal` | Server fault; the frame's effect is undefined | no | when known |

- **REQ-ERR-004** A client MUST tolerate an unknown `error.code`: it MUST surface it
  (REQ-EVENT-008) and MUST NOT crash, exit, or close the connection because of it.
- **REQ-ERR-005** An `error` carrying `ref_id` with code `bad_name`, `bad_text`, or
  `bad_frame` is a **permanent rejection**: the message can never succeed as sent. The
  client MUST drop that outbox entry (REQ-OUTBOX-009) rather than retry it forever.
- **REQ-ERR-006** An `error` with code `internal`, or with an unknown code, is **not**
  permanent. The client MUST leave the outbox entry in place for retry.
- **REQ-ERR-007** Except where REQ-ERR-003 states a connection closes, the server MUST
  keep the connection open after an error. One bad frame MUST NOT end a session.

## 14. Worked sequence (non-normative)

```
Bob is offline. Alice sends two messages, then Bob connects.

alice -> S  {"v":1,"type":"hello","name":"alice"}
S -> alice  {"v":1,"type":"welcome","name":"alice","pending":0}
S -> alice  {"v":1,"type":"sync_done"}
alice -> S  {"v":1,"type":"send","id":"7b1f...","to":"bob","text":"hi"}       # REQ-SNF-009
S -> alice  {"v":1,"type":"ack","id":"7b1f..."}                               # REQ-SNF-001
alice -> S  {"v":1,"type":"send","id":"9c22...","to":"bob","text":"you up?"}
S -> alice  {"v":1,"type":"ack","id":"9c22..."}

bob   -> S  {"v":1,"type":"hello","name":"bob"}
S -> bob    {"v":1,"type":"welcome","name":"bob","pending":2}                 # REQ-SYNC-004
S -> bob    {"v":1,"type":"msg","id":"7b1f...","from":"alice","to":"bob","text":"hi","server_ts":1761500000123}
S -> bob    {"v":1,"type":"msg","id":"9c22...","from":"alice","to":"bob","text":"you up?","server_ts":1761500000456}
S -> bob    {"v":1,"type":"sync_done"}                                        # REQ-SYNC-006
bob   -> S  {"v":1,"type":"delivered","id":"7b1f..."}                         # REQ-SNF-005
bob   -> S  {"v":1,"type":"delivered","id":"9c22..."}
            # only now may bob flush his own outbox                          # REQ-SYNC-008
```

