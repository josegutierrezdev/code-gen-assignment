# conformance/ — HAND-WRITTEN, NOT GENERATED

**This directory is outside generator discipline.** It is written and maintained by hand.

- No file here carries the `GENERATED from spec/` header, and none ever should.
- A generation run MUST NOT create, edit, or delete anything here (CLAUDE.md §2).
- It is the gate in CLAUDE.md §5: a client is not done until the runner exits 0.

The runner is **language-agnostic**. It knows nothing about Kotlin or Python: it reads
`platforms/<name>.yaml` for the command to launch, then speaks only the CLI contract —
stdin commands in, JSON Lines events out (`spec/core/cli-contract.md`).

## Run

```bash
python scripts/conformance.py python            # both roles played by the python client
python scripts/conformance.py --alice kotlin --bob python
python scripts/conformance.py --matrix          # every scenario in every combination
python scripts/conformance.py mock              # self-test the harness itself
```

Useful flags: `--scenario <name>` (repeatable), `--list`, `--build` (run each platform's
`build_cmd` first), `--platforms a,b` (restrict `--matrix`).

`scripts/conformance.sh` and `scripts/conformance.cmd` are thin wrappers that only
forward to `scripts/conformance.py`; set `PYTHON` to pick an interpreter.

Exit status is `0` when every run passed, `1` otherwise.

## What a run does

1. Starts the hand-written server on a **free port**, one fresh process per scenario, so
   no dedup record or held message leaks between scenarios.
2. Launches one client per actor from `run_cmd` (the `posix:` or `windows:` variant for
   the current OS), each with a **fresh temp `--data-dir`** under
   `.data/conformance/<scenario>-<roles>/` (REQ-PERSIST-006).
3. Writes commands to stdin and parses stdout as JSON Lines, keeping a per-client
   stream position.
4. Matches each `expect` against the **next** event on that client's stream — a strict
   transcript, per REQ-COMPARE-005. Captured ids correlate across clients
   (REQ-COMPARE-008), so no UUID is ever hard-coded.

A leading `python` / `python3` / `py` in a manifest command is replaced with the
interpreter running the runner, so a virtualenv works without editing manifests.

## On failure

The report names the failing step, what was expected, what actually arrived, the last 20
events for every client (with a `->` cursor at the stream position), and the run
directory holding each client's stderr log and data dir. Expectations that end because
the client died are reported as such rather than as a timeout.

## Self-test

`mock` is a built-in platform backed by `conformance/mock_client/` — a deliberately
minimal fixture that exists only to prove the harness works before any real client does.
It is **not** a reference implementation and must never be read when generating a client
(CLAUDE.md §1).

```bash
python -m pytest conformance/tests -q
```

Those tests cover manifest resolution, scenario validation, matching and capture
semantics, `--matrix` expansion, every scenario end to end against the mock, and the
failure reports themselves.

## Layout

| File | Role |
| --- | --- |
| `manifest.py` | loads `platforms/*.yaml`, resolves posix/windows variants |
| `scenario.py` | loads and validates `spec/scenarios/*.yaml` |
| `clientproc.py` | one client: process, stdin, stdout event stream, snapshots |
| `serverctl.py` | a fresh server on a free port per scenario |
| `runner.py` | matching, step execution, orchestration, CLI |
| `mock_client/` | harness self-test fixture (not a client) |
| `tests/` | tests of the runner itself |
