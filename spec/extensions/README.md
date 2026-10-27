# spec/extensions/

Optional capabilities that are **not** part of the core conformance surface.

A client that implements no extensions is still fully conformant. Core requirement IDs
never change when an extension is added, and an extension may not alter core behavior —
only add to it.

## Adding an extension

1. **Write the module.** Create `spec/extensions/<name>.md` — for example
   `attachments.md`, `reactions.md`, `groups.md`. It is a normative spec in the same
   style as `spec/core/`: RFC 2119 language, one stable ID per statement, and
   platform-neutral throughout.

2. **Use its own ID area.** IDs are `REQ-EXT-<NAME>-NNN`, e.g. `REQ-EXT-GROUPS-001`.
   Never extend a core area. An extension MAY reference core IDs; it MUST NOT contradict
   one. New wire frame types are safe by construction: core receivers ignore unknown
   `type` values (REQ-FRAME-003) and unknown fields (REQ-FRAME-004), so an extension is
   invisible to a client that does not implement it.

3. **Index it.** Add the module and its ID range to the table at the bottom of this file.

4. **Enable it.** Add one line — the module's bare name, no path, no extension — to
   `spec/extensions/enabled.txt`:

   ```
   attachments
   reactions
   ```

   Blank lines and `#` comments are ignored. A module that exists but is not listed is a
   draft: the generator does not read it.

5. **Regenerate.** The generator reads `enabled.txt` and appends each enabled module's
   file to the spec input set for **every** platform, after that platform's own spec
   file. No manifest edit is needed: `spec_files` in `platforms/*.yaml` lists only the
   core and platform specs, and enabled extensions are added automatically.

6. **Add scenarios.** Extension behavior is proven the same way core behavior is — a
   `spec/scenarios/*.yaml` naming the new requirement IDs. Scenarios for an extension
   MUST be skipped by the runner when the extension is not enabled, so core-only runs
   stay green.

## Rules

- Extensions are **additive**. If a capability requires changing a core requirement, it
  is a core change and a protocol version bump, not an extension.
- Each extension is independent: no module may depend on another being enabled.
- An extension MUST define its own events or frames in full, including whether an event
  is compared by the conformance runner (REQ-COMPARE-001).
- `enabled.txt` is the single switch. There is no per-platform enablement in `v1`: an
  enabled extension applies to every platform, so the clients stay interchangeable.

## Modules

| Module | ID area | Status |
| --- | --- | --- |
| *(none yet)* | — | — |
