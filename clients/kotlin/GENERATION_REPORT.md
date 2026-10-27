<!-- GENERATED from spec/ by the generator - do not edit by hand -->

# Generation Report — platform `kotlin`

Generated 2026-10-27 by `/generate kotlin`.

## Inputs

| sha256 | file |
| --- | --- |
| `6f8c80b27b8d0512` | `spec/core/README.md` |
| `6020cfbb143129fe` | `spec/core/protocol.md` |
| `cecf8a35af189102` | `spec/core/client-behavior.md` |
| `4a86a39092ecb7ba` | `spec/core/cli-contract.md` |
| `1ebb55a4b81c40d2` | `spec/platforms/kotlin.md` |
| `386cf158e9a0787a` | `platforms/kotlin.yaml` (manifest) |
| `04cc314c653a19b3` | `spec/extensions/enabled.txt` |

Enabled extensions: **none**.

Nothing under `clients/` was read for behaviour (CLAUDE.md §1). The Gradle wrapper
was left untouched as toolchain bootstrap (`clients/kotlin/TOOLCHAIN.md`).

## Output

| file | role |
| --- | --- |
| `settings.gradle.kts`, `build.gradle.kts` | Gradle build, JDK 21 toolchain, installDist |
| `src/main/kotlin/Persistence.kt` | validation and the three atomic state files |
| `src/main/kotlin/Main.kt` | state machine, outbox, inbound dedup, reconnect, wire, CLI |

## Requirement coverage

**133 of 181** active core requirements cited; the remaining
48 are server-side or conformance-runner obligations, not client ones.

| REQ ID | implemented at |
| --- | --- |
| REQ-C2S-001 | `clients/kotlin/src/main/kotlin/Main.kt:260` |
| REQ-C2S-002 | `clients/kotlin/src/main/kotlin/Main.kt:293` |
| REQ-C2S-003 | `clients/kotlin/src/main/kotlin/Main.kt:352` |
| REQ-C2S-004 | `clients/kotlin/src/main/kotlin/Main.kt:286` |
| REQ-CLI-002 | `clients/kotlin/src/main/kotlin/Main.kt:465` |
| REQ-CLI-003 | `clients/kotlin/src/main/kotlin/Main.kt:480` |
| REQ-CLI-004 | `clients/kotlin/src/main/kotlin/Main.kt:486`, `clients/kotlin/src/main/kotlin/Main.kt:510` |
| REQ-CLI-005 | `clients/kotlin/src/main/kotlin/Main.kt:510` |
| REQ-CLI-006 | `clients/kotlin/src/main/kotlin/Main.kt:535` |
| REQ-CLI-007 | `clients/kotlin/src/main/kotlin/Main.kt:500` |
| REQ-CLI-008 | `clients/kotlin/src/main/kotlin/Main.kt:467` |
| REQ-CMD-001 | `clients/kotlin/src/main/kotlin/Main.kt:119` |
| REQ-CMD-002 | `clients/kotlin/src/main/kotlin/Main.kt:130` |
| REQ-CMD-003 | `clients/kotlin/src/main/kotlin/Main.kt:156` |
| REQ-CMD-004 | `clients/kotlin/src/main/kotlin/Main.kt:127` |
| REQ-CMD-005 | `clients/kotlin/src/main/kotlin/Main.kt:137` |
| REQ-CMD-006 | `clients/kotlin/src/main/kotlin/Main.kt:144` |
| REQ-CMD-007 | `clients/kotlin/src/main/kotlin/Main.kt:120` |
| REQ-CMD-008 | `clients/kotlin/src/main/kotlin/Main.kt:212` |
| REQ-COMPARE-003 | `clients/kotlin/src/main/kotlin/Main.kt:366` |
| REQ-COMPARE-004 | `clients/kotlin/src/main/kotlin/Main.kt:28` |
| REQ-DEDUP-002 | `clients/kotlin/src/main/kotlin/Main.kt:303`, `clients/kotlin/src/main/kotlin/Main.kt:379` |
| REQ-ERR-001 | `clients/kotlin/src/main/kotlin/Main.kt:389` |
| REQ-ERR-002 | `clients/kotlin/src/main/kotlin/Main.kt:390` |
| REQ-ERR-004 | `clients/kotlin/src/main/kotlin/Main.kt:393` |
| REQ-ERR-005 | `clients/kotlin/src/main/kotlin/Main.kt:38`, `clients/kotlin/src/main/kotlin/Main.kt:398` |
| REQ-ERR-006 | `clients/kotlin/src/main/kotlin/Main.kt:402` |
| REQ-ERR-007 | `clients/kotlin/src/main/kotlin/Main.kt:391` |
| REQ-ERRCODE-001 | `clients/kotlin/src/main/kotlin/Main.kt:123` |
| REQ-ERRCODE-002 | `clients/kotlin/src/main/kotlin/Main.kt:392` |
| REQ-ERRCODE-003 | `clients/kotlin/src/main/kotlin/Main.kt:404` |
| REQ-EVENT-001 | `clients/kotlin/src/main/kotlin/Main.kt:122` |
| REQ-EVENT-002 | `clients/kotlin/src/main/kotlin/Main.kt:69`, `clients/kotlin/src/main/kotlin/Main.kt:106` |
| REQ-EVENT-003 | `clients/kotlin/src/main/kotlin/Main.kt:111` |
| REQ-EVENT-004 | `clients/kotlin/src/main/kotlin/Main.kt:28` |
| REQ-EVENT-005 | `clients/kotlin/src/main/kotlin/Main.kt:177` |
| REQ-EVENT-006 | `clients/kotlin/src/main/kotlin/Main.kt:383` |
| REQ-EVENT-007 | `clients/kotlin/src/main/kotlin/Main.kt:365` |
| REQ-EVENT-008 | `clients/kotlin/src/main/kotlin/Main.kt:394` |
| REQ-EVENT-009 | `clients/kotlin/src/main/kotlin/Main.kt:394` |
| REQ-FLUSH-001 | `clients/kotlin/src/main/kotlin/Main.kt:326` |
| REQ-FLUSH-002 | `clients/kotlin/src/main/kotlin/Main.kt:301` |
| REQ-FLUSH-003 | `clients/kotlin/src/main/kotlin/Main.kt:302` |
| REQ-FLUSH-004 | `clients/kotlin/src/main/kotlin/Main.kt:181` |
| REQ-FLUSH-006 | `clients/kotlin/src/main/kotlin/Main.kt:304` |
| REQ-FRAME-002 | `clients/kotlin/src/main/kotlin/Main.kt:318` |
| REQ-FRAME-003 | `clients/kotlin/src/main/kotlin/Main.kt:344` |
| REQ-FRAME-004 | `clients/kotlin/src/main/kotlin/Main.kt:345` |
| REQ-FRAME-005 | `clients/kotlin/src/main/kotlin/Main.kt:318` |
| REQ-FRAME-006 | `clients/kotlin/src/main/kotlin/Main.kt:318` |
| REQ-FRAME-007 | `clients/kotlin/src/main/kotlin/Main.kt:318` |
| REQ-IDENTITY-001 | `clients/kotlin/src/main/kotlin/Main.kt:143` |
| REQ-IDENTITY-002 | `clients/kotlin/src/main/kotlin/Persistence.kt:107`, `clients/kotlin/src/main/kotlin/Persistence.kt:162` |
| REQ-IDENTITY-003 | `clients/kotlin/src/main/kotlin/Main.kt:148` |
| REQ-IDENTITY-004 | `clients/kotlin/src/main/kotlin/Main.kt:111` |
| REQ-IDENTITY-005 | `clients/kotlin/src/main/kotlin/Main.kt:146` |
| REQ-INBOUND-001 | `clients/kotlin/src/main/kotlin/Main.kt:372` |
| REQ-INBOUND-002 | `clients/kotlin/src/main/kotlin/Main.kt:350` |
| REQ-INBOUND-003 | `clients/kotlin/src/main/kotlin/Main.kt:361` |
| REQ-INBOUND-004 | `clients/kotlin/src/main/kotlin/Main.kt:356` |
| REQ-INBOUND-006 | `clients/kotlin/src/main/kotlin/Persistence.kt:66` |
| REQ-INBOUND-007 | `clients/kotlin/src/main/kotlin/Main.kt:351` |
| REQ-INBOUND-008 | `clients/kotlin/src/main/kotlin/Persistence.kt:180` |
| REQ-MSGID-001 | `clients/kotlin/src/main/kotlin/Main.kt:170` |
| REQ-MSGID-002 | `clients/kotlin/src/main/kotlin/Main.kt:170` |
| REQ-MSGID-003 | `clients/kotlin/src/main/kotlin/Main.kt:293` |
| REQ-MSGID-004 | `clients/kotlin/src/main/kotlin/Main.kt:170` |
| REQ-MSGID-005 | `clients/kotlin/src/main/kotlin/Main.kt:171` |
| REQ-NAME-001 | `clients/kotlin/src/main/kotlin/Persistence.kt:26`, `clients/kotlin/src/main/kotlin/Persistence.kt:107` |
| REQ-NAME-002 | `clients/kotlin/src/main/kotlin/Persistence.kt:26` |
| REQ-NAME-003 | `clients/kotlin/src/main/kotlin/Persistence.kt:26` |
| REQ-OUTBOX-001 | `clients/kotlin/src/main/kotlin/Persistence.kt:117` |
| REQ-OUTBOX-002 | `clients/kotlin/src/main/kotlin/Main.kt:175` |
| REQ-OUTBOX-003 | `clients/kotlin/src/main/kotlin/Main.kt:170` |
| REQ-OUTBOX-005 | `clients/kotlin/src/main/kotlin/Main.kt:381` |
| REQ-OUTBOX-006 | `clients/kotlin/src/main/kotlin/Main.kt:378` |
| REQ-OUTBOX-008 | `clients/kotlin/src/main/kotlin/Main.kt:306` |
| REQ-OUTBOX-009 | `clients/kotlin/src/main/kotlin/Main.kt:398` |
| REQ-OUTBOX-010 | `clients/kotlin/src/main/kotlin/Main.kt:402` |
| REQ-OUTBOX-012 | `clients/kotlin/src/main/kotlin/Main.kt:166` |
| REQ-OUTBOX-013 | `clients/kotlin/src/main/kotlin/Persistence.kt:168` |
| REQ-PERSIST-001 | `clients/kotlin/src/main/kotlin/Persistence.kt:3`, `clients/kotlin/src/main/kotlin/Persistence.kt:60` |
| REQ-PERSIST-002 | `clients/kotlin/src/main/kotlin/Persistence.kt:144` |
| REQ-PERSIST-003 | `clients/kotlin/src/main/kotlin/Persistence.kt:87` |
| REQ-PERSIST-004 | `clients/kotlin/src/main/kotlin/Main.kt:503` |
| REQ-PERSIST-005 | `clients/kotlin/src/main/kotlin/Persistence.kt:80` |
| REQ-PERSIST-006 | `clients/kotlin/src/main/kotlin/Persistence.kt:62` |
| REQ-PERSIST-007 | `clients/kotlin/src/main/kotlin/Persistence.kt:64` |
| REQ-PERSIST-008 | `clients/kotlin/src/main/kotlin/Main.kt:107`, `clients/kotlin/src/main/kotlin/Persistence.kt:82` |
| REQ-RECONNECT-001 | `clients/kotlin/src/main/kotlin/Main.kt:73` |
| REQ-RECONNECT-002 | `clients/kotlin/src/main/kotlin/Main.kt:35`, `clients/kotlin/src/main/kotlin/Main.kt:223` |
| REQ-RECONNECT-003 | `clients/kotlin/src/main/kotlin/Main.kt:271` |
| REQ-RECONNECT-005 | `clients/kotlin/src/main/kotlin/Main.kt:206` |
| REQ-RECONNECT-006 | `clients/kotlin/src/main/kotlin/Main.kt:334` |
| REQ-RECONNECT-008 | `clients/kotlin/src/main/kotlin/Main.kt:244` |
| REQ-RECONNECT-009 | `clients/kotlin/src/main/kotlin/Main.kt:91`, `clients/kotlin/src/main/kotlin/Main.kt:252` |
| REQ-SNF-005 | `clients/kotlin/src/main/kotlin/Main.kt:372` |
| REQ-STATE-001 | `clients/kotlin/src/main/kotlin/Main.kt:27`, `clients/kotlin/src/main/kotlin/Main.kt:223` |
| REQ-STATE-002 | `clients/kotlin/src/main/kotlin/Main.kt:88` |
| REQ-STATE-003 | `clients/kotlin/src/main/kotlin/Main.kt:89` |
| REQ-STATE-004 | `clients/kotlin/src/main/kotlin/Main.kt:86` |
| REQ-STATE-005 | `clients/kotlin/src/main/kotlin/Main.kt:87` |
| REQ-STATE-006 | `clients/kotlin/src/main/kotlin/Main.kt:164` |
| REQ-STATE-007 | `clients/kotlin/src/main/kotlin/Main.kt:181` |
| REQ-STATE-008 | `clients/kotlin/src/main/kotlin/Main.kt:59` |
| REQ-STDIO-001 | `clients/kotlin/src/main/kotlin/Main.kt:125` |
| REQ-STDIO-002 | `clients/kotlin/src/main/kotlin/Main.kt:44` |
| REQ-STDIO-003 | `clients/kotlin/src/main/kotlin/Main.kt:45` |
| REQ-STDIO-005 | `clients/kotlin/src/main/kotlin/Main.kt:53` |
| REQ-STDIO-006 | `clients/kotlin/src/main/kotlin/Main.kt:47` |
| REQ-STDIO-007 | `clients/kotlin/src/main/kotlin/Main.kt:527` |
| REQ-STDIO-008 | `clients/kotlin/src/main/kotlin/Main.kt:59`, `clients/kotlin/src/main/kotlin/Main.kt:523` |
| REQ-STDIO-009 | `clients/kotlin/src/main/kotlin/Main.kt:518` |
| REQ-SYNC-001 | `clients/kotlin/src/main/kotlin/Main.kt:258` |
| REQ-SYNC-002 | `clients/kotlin/src/main/kotlin/Main.kt:258` |
| REQ-SYNC-008 | `clients/kotlin/src/main/kotlin/Main.kt:326` |
| REQ-TESTHOOK-001 | `clients/kotlin/src/main/kotlin/Main.kt:188` |
| REQ-TESTHOOK-002 | `clients/kotlin/src/main/kotlin/Main.kt:189` |
| REQ-TESTHOOK-004 | `clients/kotlin/src/main/kotlin/Main.kt:190` |
| REQ-TESTHOOK-005 | `clients/kotlin/src/main/kotlin/Main.kt:202` |
| REQ-TESTHOOK-006 | `clients/kotlin/src/main/kotlin/Main.kt:192` |
| REQ-TESTHOOK-007 | `clients/kotlin/src/main/kotlin/Main.kt:193` |
| REQ-TEXT-001 | `clients/kotlin/src/main/kotlin/Persistence.kt:33` |
| REQ-TEXT-002 | `clients/kotlin/src/main/kotlin/Persistence.kt:35` |
| REQ-TEXT-003 | `clients/kotlin/src/main/kotlin/Persistence.kt:36` |
| REQ-TEXT-004 | `clients/kotlin/src/main/kotlin/Persistence.kt:37` |
| REQ-TEXT-005 | `clients/kotlin/src/main/kotlin/Persistence.kt:38` |
| REQ-TIME-004 | `clients/kotlin/src/main/kotlin/Main.kt:366` |
| REQ-WIRE-002 | `clients/kotlin/src/main/kotlin/Main.kt:285`, `clients/kotlin/src/main/kotlin/Main.kt:426` |
| REQ-WIRE-003 | `clients/kotlin/src/main/kotlin/Main.kt:438` |
| REQ-WIRE-005 | `clients/kotlin/src/main/kotlin/Main.kt:315` |
| REQ-WIRE-006 | `clients/kotlin/src/main/kotlin/Main.kt:242` |
| REQ-WIRE-007 | `clients/kotlin/src/main/kotlin/Main.kt:242` |

### Not client obligations

REQ-C2S-005 REQ-CLI-001 REQ-COMPARE-001 REQ-COMPARE-005 REQ-COMPARE-006 REQ-COMPARE-007 REQ-COMPARE-008 REQ-DEDUP-001 REQ-DEDUP-004 REQ-DEDUP-005 REQ-DEDUP-006 REQ-ERR-003 REQ-FRAME-001 REQ-INBOUND-005 REQ-NAME-005 REQ-OUTBOX-004 REQ-RECONNECT-007 REQ-S2C-001 REQ-S2C-002 REQ-S2C-003 REQ-S2C-004 REQ-S2C-005 REQ-S2C-006 REQ-SESSION-001 REQ-SESSION-002 REQ-SESSION-003 REQ-SESSION-004 REQ-SESSION-007 REQ-SNF-001 REQ-SNF-002 REQ-SNF-003 REQ-SNF-006 REQ-SNF-007 REQ-SNF-008 REQ-SNF-009 REQ-SNF-010 REQ-SYNC-003 REQ-SYNC-004 REQ-SYNC-005 REQ-SYNC-006 REQ-SYNC-007 REQ-SYNC-010 REQ-SYNC-011 REQ-SYNC-012 REQ-TIME-001 REQ-TIME-002 REQ-TIME-003 REQ-WIRE-001

## Iterations

**1 repair iteration**, and it was not a code fix:

1. First conformance run: 0/4, every scenario dying with
   `FileNotFoundError [WinError 2]` before any event. Cause was in the **harness**,
   not the generated client: on Windows `CreateProcess` resolves a relative
   `argv[0]` against the parent process's working directory, not the `cwd` passed
   to `Popen`, so the manifest's relative `run_cmd`
   (`build\install\clientin\client.bat`) could not be found. Fixed in
   `conformance/manifest.py` by absolutising a relative launcher against `out_dir`.
   No generated code changed. After that: 4/4.

## Results

```
build:       gradlew.bat --quiet --console=plain installDist   -> exit 0
conformance: python scripts/conformance.py kotlin              -> exit 0 (4/4), twice

PASS  alice-bob-offline      [alice=kotlin, bob=kotlin]
PASS  duplicate-resend       [alice=kotlin, bob=kotlin]
PASS  first-launch-identity  [alice=kotlin]
PASS  restart-persistence    [alice=kotlin, bob=kotlin]
```

Cross-client matrix (`--matrix`, 14 runs): every mixed pair passes — Kotlin↔Python
in both directions, for every scenario.

## Resolved defect: intermittent relaunch failure

**Fixed in the harness. No generated code changed.**

Originally, under load (the 14-run `--matrix` sweep, or repeated runs), Kotlin
intermittently failed the step immediately after `kill` -> `start`:

```
FAIL  first-launch-identity [alice=kotlin]
step 25: alice: expect {'type': 'ready', 'state': 'OFFLINE'}
  stdout ended before {'type': 'ready', 'state': 'OFFLINE'} arrived;
  the client is no longer running
```

Frequency was roughly 1 full run in 4, with `restart-persistence` failing the same way
less often; both passed reliably in isolation, and a matrix sweep showed 12/14 with
exactly these two.

Cause, as suspected and now confirmed: the manifest launches `client.bat`, a
Gradle-generated cmd.exe wrapper that spawns `java.exe` as a child.
`ClientProcess.kill()` terminated only the direct child, so the JVM survived the
simulated crash as an orphan, still holding the data-dir and its server session, and the
relaunched client exited before emitting `ready`.

Fix: `ClientProcess.kill()` now terminates the whole process tree —
`taskkill /T /F /PID <pid>` on Windows, unchanged `Popen.kill()` on POSIX. This is also
the more honest simulation of a crash for any wrapper-launched client, so it belongs in
the harness rather than in a platform workaround.

Result after the fix:

```
python scripts/conformance.py --matrix   ->  14/14 passed
```

Every scenario passes in every combination, Kotlin↔Python in both directions. A
secondary confirmation that the orphan was real: Kotlin scenarios sped up sharply once
each run stopped contending with a leftover JVM — `duplicate-resend` went from 16.6s to
7.1s, `restart-persistence` from 8.7s to 2.2s.
