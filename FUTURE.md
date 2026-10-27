# Future Work

Ordered by what I would do next, not by size.

## 1. Fix the Kotlin process-tree kill

The one known defect. `ClientProcess.kill()` terminates `client.bat` but not the
`java.exe` it spawns, so an orphaned JVM survives a simulated crash and intermittently
breaks the relaunch (~1 full run in 4; details in
`clients/kotlin/GENERATION_REPORT.md`). Kill the whole process tree — `taskkill /T /F`
on Windows, a process group elsewhere — which is also the more honest simulation of a
crash for any wrapper-launched client. Alternative: launch `java -cp` directly from the
manifest and skip the `.bat`.

## 2. The `spec-reviewer` subagent

Designed but not built. A second agent that audits generated code against **every**
requirement ID *without having written it*, emitting a pass/fail table per ID. The point
is independence: the generator is a poor judge of whether it implemented REQ-SNF-005,
having just convinced itself it did. The data is already there — generated code cites its
IDs, and `spec/core/README.md` indexes all 181 — so the reviewer can diff *claimed*
coverage against *actual* behaviour and flag citations that decorate code which does not
implement the rule. That closes the gap conformance leaves: conformance proves the
scenarios pass, not that every requirement is implemented.

## 3. Headless `scripts/generate.py`

`/generate <platform>` is interactive. A headless entrypoint would run it
non-interactively (`claude -p`, with the allowed-tools and permission mode pinned) for
`<platform>` or `all`, so regeneration is a CI step: regenerate from a tagged spec,
assert conformance, publish the report. With it, "the spec is the source of truth"
becomes enforceable on every spec commit rather than a convention. Needs
`scripts/clean_generated.py` (respecting `clean_globs`, so the Gradle wrapper survives)
and the thin `.sh`/`.cmd` wrappers alongside it.

## 4. An example spec extension

`spec/extensions/` defines the mechanism — a module with its own `REQ-EXT-<NAME>-NNN`
IDs, switched on in `enabled.txt`, picked up automatically by the generator — but ships
with no module, so the mechanism is untested. The cheapest convincing one is
**reactions**: a new `react{id,emoji}` frame and a `reaction{id,from,emoji}` event. It
exercises the forward-compatibility rules already in core (unknown frame types and
unknown fields are ignored, REQ-FRAME-003/004), so an extended client and an unextended
one stay interoperable — which is the claim worth testing. **Attachments** would be the
more interesting stress test, since it forces a decision about binary payloads over a
text-frame-only protocol. Each needs its own scenarios, skipped by the runner when the
module is disabled.

## 5. Smaller things

- **Flake pressure in CI**: run `--matrix` N times and fail on any single failure, so
  timing-dependent bugs like the Kotlin one surface before a human notices them.
- **Scenario coverage gaps**: nothing currently exercises `replaced` (newest connection
  wins) or a permanent rejection dropping an outbox entry end to end, though the server
  tests cover both sides of the wire.
- **A third platform** to test the "adding a platform needs no harness change" claim.
  TypeScript/Node would be the honest test: a profile plus a manifest, nothing else.
- **Spec-to-scenario traceability**: every requirement should name the scenario that
  proves it, and the index should fail CI when a requirement has no coverage.
- **Server durability**: it is in-memory by design, so restarting it forgets dedup
  records. A persistent store would let the conformance suite restart the *server*
  mid-scenario, which is currently untestable.
