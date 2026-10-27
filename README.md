# Spec-Driven Messaging Client Generator

A **code generator** (driven by Claude Code) that regenerates two messaging clients — a
Kotlin JVM CLI and a Python CLI — from a written specification. A small hand-written
Python server hosts them, and a hand-written conformance runner proves them
interchangeable.

**The generator and its harness are the deliverable.** The clients are disposable
output: delete `clients/` and one command rebuilds them from `spec/`.

## Folder map

| Path | What it is | Generated? |
| --- | --- | --- |
| `spec/core/` | The single source of truth: 181 numbered requirements (`REQ-<AREA>-NNN`) | no |
| `spec/platforms/` | Per-platform idioms, libraries, build — **no behaviour** | no |
| `spec/scenarios/` | Executable acceptance scenarios (YAML), platform- and role-neutral | no |
| `spec/extensions/` | Optional modules, switched on in `enabled.txt` | no |
| `platforms/*.yaml` | Per-platform manifests: out_dir, spec inputs, build/run cmds, clean globs, per-OS env | no |
| `server/` | Reference server for the v1 protocol, in-memory, pytest over raw frames | no |
| `conformance/` | Language-agnostic runner: drives clients over stdin/stdout JSONL | no |
| `scripts/` | `conformance.py` (+ `.sh`/`.cmd` wrappers) | no |
| `.claude/commands/`, `.claude/agents/` | The generation harness: `/generate <platform>` and its subagent | no |
| `clients/<platform>/` | **Generated client code** — the regeneration boundary | **yes** |
| `clients/kotlin/gradlew*`, `gradle/wrapper/` | Toolchain bootstrap, hand-provided (see `clients/kotlin/TOOLCHAIN.md`) | no |

## Running it

Install the dev dependencies for the hand-written halves:

```bash
python -m pip install -r requirements-dev.txt
```

Server + harness unit tests (71 tests, raw-frame protocol tests and runner self-tests):

```bash
python -m pytest server/tests conformance/tests -q
```

The conformance gate for one platform:

```bash
python scripts/conformance.py python
```

Every scenario in every client combination, including mixed pairs:

```bash
python scripts/conformance.py --matrix
```

Self-test the harness with no real client involved:

```bash
python scripts/conformance.py mock
```

`scripts/conformance.sh` and `scripts/conformance.cmd` are thin wrappers around
`scripts/conformance.py`. Useful flags: `--alice X --bob Y`, `--scenario <name>`,
`--list`, `--build`.

## Regenerating a client

From Claude Code, in this repo:

```
/generate python
```

That reads `platforms/<platform>.yaml`, `spec/core/*`, the enabled
`spec/extensions/*` and `spec/platforms/<platform>.md` — **and nothing else** — deletes
the manifest's `clean_globs`, writes the client from scratch, builds it, runs the
conformance gate, repairs generated code only (max 3 iterations), and writes
`clients/<platform>/GENERATION_REPORT.md` with spec checksums, requirement-ID
traceability, iteration count and results. Adding a platform or an extension needs no
harness change.

## STATUS

| Client | Gate (`conformance.py <platform>`) | Notes |
| --- | --- | --- |
| **python** | ✅ 4/4 | green on the first generation attempt, 0 repair iterations |
| **kotlin** | ✅ 4/4 | 1 iteration, and it was a harness fix, not a code fix |

Cross-client matrix: **14/14 runs pass** — every scenario in every combination, including
Kotlin↔Python in both directions.

The previously recorded Kotlin flake (~1 run in 4 failing right after `kill` → `start`)
is **fixed**. The cause was the harness, not the client: `kill` terminated Gradle's
`client.bat` wrapper but not the `java.exe` it spawns, leaving an orphaned JVM holding
the data-dir and its server session. `ClientProcess.kill()` now kills the whole process
tree (`taskkill /T /F /PID` on Windows; POSIX unchanged). Kotlin scenarios also got
markedly faster — `duplicate-resend` 16.6s → 7.1s — since each run no longer contends
with an orphan.

Server: 34 raw-frame protocol tests pass. Harness: 37 self-tests pass.

## Authorship

| Area | Authorship |
| --- | --- |
| `spec/`, `server/`, `conformance/`, `.claude/` harness, `scripts/`, manifests | **Co-drafted with Claude Code, reviewed and directed by me.** |
| `clients/kotlin/`, `clients/python/` | **Generated — this is the regeneration boundary.** Not hand-edited; every file carries a `GENERATED from spec/` header and cites the requirement IDs it implements. |

See [DESIGN.md](DESIGN.md) for the approach and [FUTURE.md](FUTURE.md) for what is
deliberately left out.
