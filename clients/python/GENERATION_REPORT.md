<!-- GENERATED from spec/ by the generator - do not edit by hand -->

# Generation Report — platform `python`

Generated 2026-10-27 by `/generate python`.

## Inputs

The only behavioural inputs, in manifest order, with SHA-256 content checksums
(first 16 hex chars) so this output is traceable to an exact spec revision.

| sha256 | file |
| --- | --- |
| `6f8c80b27b8d0512` | `spec/core/README.md` |
| `6020cfbb143129fe` | `spec/core/protocol.md` |
| `cecf8a35af189102` | `spec/core/client-behavior.md` |
| `4a86a39092ecb7ba` | `spec/core/cli-contract.md` |
| `da20af688d99d116` | `spec/platforms/python.md` |
| `b6975bcb0cb9faef` | `platforms/python.yaml` (manifest) |
| `04cc314c653a19b3` | `spec/extensions/enabled.txt` |

Enabled extensions: **none**.

Nothing under `clients/` was read (CLAUDE.md §1), and neither `server/` nor
`conformance/` was consulted for behaviour.

## Output

| file | role |
| --- | --- |
| `pyproject.toml` | editable-installable package metadata |
| `client/__init__.py` | package marker |
| `client/__main__.py` | CLI entry point, argument parsing, exit statuses |
| `client/persistence.py` | validation and the three atomic state files |
| `client/core.py` | state machine, outbox, inbound dedup, reconnection, wire |

Every file opens with the CLAUDE.md §3 header.

## Requirement coverage

**139 of 181** active core requirements are cited in the generated
code. The remaining 42 are not client obligations (see below).

| REQ ID | implemented at |
| --- | --- |
| REQ-C2S-001 | `clients/python/client/core.py:265` |
| REQ-C2S-002 | `clients/python/client/core.py:310` |
| REQ-C2S-003 | `clients/python/client/core.py:330` |
| REQ-C2S-004 | `clients/python/client/core.py:266` |
| REQ-CLI-001 | `clients/python/client/__main__.py:34` |
| REQ-CLI-002 | `clients/python/client/__main__.py:29` |
| REQ-CLI-003 | `clients/python/client/__main__.py:34` |
| REQ-CLI-004 | `clients/python/client/__main__.py:35`, `clients/python/client/__main__.py:50` |
| REQ-CLI-005 | `clients/python/client/__main__.py:50` |
| REQ-CLI-006 | `clients/python/client/__main__.py:55` |
| REQ-CLI-007 | `clients/python/client/__main__.py:42` |
| REQ-CLI-008 | `clients/python/client/__main__.py:31` |
| REQ-CMD-001 | `clients/python/client/core.py:81` |
| REQ-CMD-002 | `clients/python/client/core.py:93` |
| REQ-CMD-003 | `clients/python/client/core.py:131` |
| REQ-CMD-004 | `clients/python/client/core.py:88` |
| REQ-CMD-005 | `clients/python/client/core.py:105` |
| REQ-CMD-006 | `clients/python/client/core.py:111` |
| REQ-CMD-007 | `clients/python/client/core.py:82` |
| REQ-CMD-008 | `clients/python/client/core.py:201` |
| REQ-COMPARE-003 | `clients/python/client/core.py:344` |
| REQ-COMPARE-004 | `clients/python/client/core.py:24` |
| REQ-DEDUP-002 | `clients/python/client/core.py:320`, `clients/python/client/core.py:355` |
| REQ-ERR-001 | `clients/python/client/core.py:365` |
| REQ-ERR-002 | `clients/python/client/core.py:366` |
| REQ-ERR-004 | `clients/python/client/core.py:370` |
| REQ-ERR-005 | `clients/python/client/core.py:34`, `clients/python/client/core.py:379` |
| REQ-ERR-006 | `clients/python/client/core.py:385` |
| REQ-ERR-007 | `clients/python/client/core.py:367` |
| REQ-ERRCODE-001 | `clients/python/client/core.py:85` |
| REQ-ERRCODE-002 | `clients/python/client/core.py:369` |
| REQ-ERRCODE-003 | `clients/python/client/core.py:375` |
| REQ-EVENT-001 | `clients/python/client/core.py:84` |
| REQ-EVENT-002 | `clients/python/client/core.py:55`, `clients/python/client/core.py:392` |
| REQ-EVENT-003 | `clients/python/client/core.py:397` |
| REQ-EVENT-004 | `clients/python/client/core.py:24` |
| REQ-EVENT-005 | `clients/python/client/core.py:161` |
| REQ-EVENT-006 | `clients/python/client/core.py:360` |
| REQ-EVENT-007 | `clients/python/client/core.py:343` |
| REQ-EVENT-008 | `clients/python/client/core.py:368` |
| REQ-EVENT-009 | `clients/python/client/core.py:368` |
| REQ-FLUSH-001 | `clients/python/client/core.py:289` |
| REQ-FLUSH-002 | `clients/python/client/core.py:318` |
| REQ-FLUSH-003 | `clients/python/client/core.py:319` |
| REQ-FLUSH-004 | `clients/python/client/core.py:163` |
| REQ-FLUSH-006 | `clients/python/client/core.py:314` |
| REQ-FRAME-001 | `clients/python/client/core.py:279` |
| REQ-FRAME-002 | `clients/python/client/core.py:280` |
| REQ-FRAME-003 | `clients/python/client/core.py:300` |
| REQ-FRAME-004 | `clients/python/client/core.py:301` |
| REQ-FRAME-005 | `clients/python/client/core.py:280` |
| REQ-FRAME-006 | `clients/python/client/core.py:280` |
| REQ-FRAME-007 | `clients/python/client/core.py:280` |
| REQ-IDENTITY-001 | `clients/python/client/core.py:110` |
| REQ-IDENTITY-002 | `clients/python/client/persistence.py:101`, `clients/python/client/persistence.py:134` |
| REQ-IDENTITY-003 | `clients/python/client/core.py:120` |
| REQ-IDENTITY-004 | `clients/python/client/core.py:397` |
| REQ-IDENTITY-005 | `clients/python/client/core.py:115` |
| REQ-INBOUND-001 | `clients/python/client/core.py:347` |
| REQ-INBOUND-002 | `clients/python/client/core.py:328` |
| REQ-INBOUND-003 | `clients/python/client/core.py:339` |
| REQ-INBOUND-004 | `clients/python/client/core.py:335` |
| REQ-INBOUND-005 | `clients/python/client/core.py:268` |
| REQ-INBOUND-006 | `clients/python/client/persistence.py:81` |
| REQ-INBOUND-007 | `clients/python/client/core.py:329` |
| REQ-INBOUND-008 | `clients/python/client/persistence.py:143` |
| REQ-MSGID-001 | `clients/python/client/core.py:154` |
| REQ-MSGID-002 | `clients/python/client/core.py:154` |
| REQ-MSGID-003 | `clients/python/client/core.py:310` |
| REQ-MSGID-004 | `clients/python/client/core.py:154` |
| REQ-MSGID-005 | `clients/python/client/core.py:155` |
| REQ-NAME-001 | `clients/python/client/persistence.py:12`, `clients/python/client/persistence.py:30`, `clients/python/client/persistence.py:101` |
| REQ-NAME-002 | `clients/python/client/persistence.py:12` |
| REQ-NAME-003 | `clients/python/client/persistence.py:12` |
| REQ-OUTBOX-001 | `clients/python/client/persistence.py:119` |
| REQ-OUTBOX-002 | `clients/python/client/core.py:159` |
| REQ-OUTBOX-003 | `clients/python/client/core.py:154` |
| REQ-OUTBOX-004 | `clients/python/client/core.py:321` |
| REQ-OUTBOX-005 | `clients/python/client/core.py:357` |
| REQ-OUTBOX-006 | `clients/python/client/core.py:354` |
| REQ-OUTBOX-008 | `clients/python/client/core.py:316` |
| REQ-OUTBOX-009 | `clients/python/client/core.py:379` |
| REQ-OUTBOX-010 | `clients/python/client/core.py:385` |
| REQ-OUTBOX-012 | `clients/python/client/core.py:144` |
| REQ-OUTBOX-013 | `clients/python/client/persistence.py:139` |
| REQ-PERSIST-001 | `clients/python/client/persistence.py:3`, `clients/python/client/persistence.py:75` |
| REQ-PERSIST-002 | `clients/python/client/persistence.py:48` |
| REQ-PERSIST-003 | `clients/python/client/persistence.py:61` |
| REQ-PERSIST-004 | `clients/python/client/__main__.py:45`, `clients/python/client/persistence.py:22` |
| REQ-PERSIST-005 | `clients/python/client/persistence.py:85` |
| REQ-PERSIST-006 | `clients/python/client/persistence.py:77` |
| REQ-PERSIST-007 | `clients/python/client/persistence.py:79` |
| REQ-PERSIST-008 | `clients/python/client/core.py:393`, `clients/python/client/persistence.py:91` |
| REQ-RECONNECT-001 | `clients/python/client/core.py:58`, `clients/python/client/core.py:208` |
| REQ-RECONNECT-002 | `clients/python/client/core.py:31`, `clients/python/client/core.py:227` |
| REQ-RECONNECT-003 | `clients/python/client/core.py:260` |
| REQ-RECONNECT-005 | `clients/python/client/core.py:194` |
| REQ-RECONNECT-006 | `clients/python/client/core.py:243` |
| REQ-RECONNECT-007 | `clients/python/client/core.py:267` |
| REQ-RECONNECT-008 | `clients/python/client/core.py:235` |
| REQ-RECONNECT-009 | `clients/python/client/core.py:72`, `clients/python/client/core.py:250` |
| REQ-SESSION-002 | `clients/python/client/core.py:40` |
| REQ-SNF-005 | `clients/python/client/core.py:347` |
| REQ-STATE-001 | `clients/python/client/core.py:23`, `clients/python/client/core.py:227` |
| REQ-STATE-002 | `clients/python/client/core.py:69` |
| REQ-STATE-003 | `clients/python/client/core.py:70` |
| REQ-STATE-004 | `clients/python/client/core.py:67` |
| REQ-STATE-005 | `clients/python/client/core.py:68` |
| REQ-STATE-006 | `clients/python/client/core.py:140` |
| REQ-STATE-007 | `clients/python/client/core.py:163` |
| REQ-STATE-008 | `clients/python/client/core.py:420` |
| REQ-STDIO-001 | `clients/python/client/core.py:86` |
| REQ-STDIO-002 | `clients/python/client/__main__.py:18`, `clients/python/client/core.py:44` |
| REQ-STDIO-003 | `clients/python/client/core.py:45` |
| REQ-STDIO-005 | `clients/python/client/__main__.py:22`, `clients/python/client/core.py:251` |
| REQ-STDIO-006 | `clients/python/client/core.py:47` |
| REQ-STDIO-007 | `clients/python/client/core.py:417` |
| REQ-STDIO-008 | `clients/python/client/core.py:420` |
| REQ-STDIO-009 | `clients/python/client/core.py:406` |
| REQ-SYNC-001 | `clients/python/client/core.py:264` |
| REQ-SYNC-002 | `clients/python/client/core.py:264` |
| REQ-SYNC-008 | `clients/python/client/core.py:289` |
| REQ-TESTHOOK-001 | `clients/python/client/core.py:172` |
| REQ-TESTHOOK-002 | `clients/python/client/core.py:175` |
| REQ-TESTHOOK-004 | `clients/python/client/core.py:176` |
| REQ-TESTHOOK-005 | `clients/python/client/core.py:188` |
| REQ-TESTHOOK-006 | `clients/python/client/core.py:173` |
| REQ-TESTHOOK-007 | `clients/python/client/core.py:174` |
| REQ-TEXT-001 | `clients/python/client/persistence.py:39` |
| REQ-TEXT-002 | `clients/python/client/persistence.py:35` |
| REQ-TEXT-003 | `clients/python/client/persistence.py:36` |
| REQ-TEXT-004 | `clients/python/client/persistence.py:37` |
| REQ-TEXT-005 | `clients/python/client/persistence.py:41` |
| REQ-TIME-004 | `clients/python/client/core.py:344` |
| REQ-WIRE-002 | `clients/python/client/core.py:304` |
| REQ-WIRE-003 | `clients/python/client/core.py:271` |
| REQ-WIRE-005 | `clients/python/client/core.py:277` |
| REQ-WIRE-006 | `clients/python/client/core.py:233` |
| REQ-WIRE-007 | `clients/python/client/core.py:233` |

### Deliberately not implemented

These are obligations of the server or of the conformance runner, not of a client,
so a client cannot and must not implement them:

| area | IDs | why |
| --- | --- | --- |
| `REQ-C2S` | REQ-C2S-005 | server-side rejection rules for client frames |
| `REQ-COMPARE` | REQ-COMPARE-001, REQ-COMPARE-005, REQ-COMPARE-006, REQ-COMPARE-007, REQ-COMPARE-008 | rules binding the conformance runner, not the client |
| `REQ-DEDUP` | REQ-DEDUP-001, REQ-DEDUP-004, REQ-DEDUP-005, REQ-DEDUP-006 | server-side deduplication |
| `REQ-ERR` | REQ-ERR-003 | the server error-code table; the client relays codes verbatim per REQ-ERRCODE-002 |
| `REQ-NAME` | REQ-NAME-005 | server-side rejection of an invalid recipient; the client validates locally per REQ-OUTBOX-012 |
| `REQ-S2C` | REQ-S2C-001, REQ-S2C-002, REQ-S2C-003, REQ-S2C-004, REQ-S2C-005, REQ-S2C-006 | frames the server emits; the client only consumes them |
| `REQ-SESSION` | REQ-SESSION-001, REQ-SESSION-003, REQ-SESSION-004, REQ-SESSION-007 | server-side session replacement; the client half is REQ-RECONNECT-006, cited |
| `REQ-SNF` | REQ-SNF-001, REQ-SNF-002, REQ-SNF-003, REQ-SNF-006, REQ-SNF-007, REQ-SNF-008, REQ-SNF-009, REQ-SNF-010 | server-side store and forward |
| `REQ-SYNC` | REQ-SYNC-003, REQ-SYNC-004, REQ-SYNC-005, REQ-SYNC-006, REQ-SYNC-007, REQ-SYNC-010, REQ-SYNC-011, REQ-SYNC-012 | the server half of the handshake; the client half (001, 002, 008) is cited |
| `REQ-TIME` | REQ-TIME-001, REQ-TIME-002, REQ-TIME-003 | server assigns and owns server_ts; the client never surfaces it (REQ-TIME-004 is cited) |
| `REQ-WIRE` | REQ-WIRE-001 | transport endpoint is the server's; the client is handed the URL via REQ-CLI-001 |

## Iterations

**0 repair iterations.** The build and the conformance gate both passed on the
first attempt, so no generated code was changed after the initial write. A later
pass added requirement-ID citations for rules that were already implemented but
not yet traceable; conformance was re-run afterwards and still passed.

## Results

```
build:       python -m pip install -e .      (cwd clients/python)  -> exit 0
conformance: python scripts/conformance.py python                  -> exit 0

PASS  alice-bob-offline      [alice=python, bob=python]
PASS  duplicate-resend       [alice=python, bob=python]
PASS  first-launch-identity  [alice=python]
PASS  restart-persistence    [alice=python, bob=python]
4/4 passed
```

## Ambiguities

None. No requirement needed a guess, and no decision was deferred with a TODO.

Two points were unobvious but unambiguously settled by the spec, and are worth
recording because a different reading would have failed conformance:

- **REQ-TEXT-001** counts length in Unicode code points, not bytes and not UTF-16
  units. In Python `len()` is already code points, so no conversion is correct —
  `len(text.encode())` would wrongly reject valid multi-byte text.
- **REQ-STATE-003 with REQ-RECONNECT-002/009** means a failed connect is a
  self-transition inside `CONNECTING` and emits nothing. Treating a retry as
  `CONNECTING -> OFFLINE -> CONNECTING` would emit two events per second while the
  server is down and break the bounded-stdout guarantee.
