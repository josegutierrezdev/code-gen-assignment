# CLAUDE.md — rules for working in this repository

This repository is a **spec-driven code generator**. The clients under `clients/` are
build output, not source. Read these rules before generating anything.

## 1. The spec is the single source of truth

- All behavior is defined by the files under `spec/`.
- Answer every behavior question from `spec/` — **never** by reading, imitating, or
  inferring from existing client code under `clients/`. Existing generated code carries
  no authority; it may be stale, wrong, or absent.
- If the spec and a generated client disagree, the spec is right and the client is a bug.

## 2. Write only inside `clients/<platform>/`

During a generation run:

- Write **only** inside `clients/<platform>/` for the platform being generated.
- Never create, edit, or delete anything in `spec/`, `server/`, or `conformance/`.
  Those are hand-written and out of scope for generation.
- Never touch another platform's directory.
- One exception lives inside a client directory: files a platform marks as
  **toolchain bootstrap** (such as the Gradle wrapper, see
  `clients/kotlin/TOOLCHAIN.md`). They are hand-provided, carry no generated
  header, are excluded from that platform's `clean_globs`, and MUST NOT be
  created, modified, or deleted by a generation run.

If the spec is **ambiguous, contradictory, or wrong**: stop. Do not guess, do not pick a
"reasonable" default, do not write a TODO and continue. Report:

1. the requirement ID(s) involved,
2. the exact conflicting or missing sentences, quoted,
3. the concrete decision you cannot make.

A stopped run with a precise question is a success. A run that guessed is a failure.

## 3. Generated file header

Every generated source file MUST begin with a header comment whose first line is exactly:

```
GENERATED from spec/ by the generator - do not edit by hand
```

in that file's comment syntax (`// ` for Kotlin, `# ` for Python, etc.).

## 4. Cite requirement IDs

Generated code MUST cite the requirement IDs it implements, in comments adjacent to the
implementing code:

```python
# REQ-OUTBOX-002: append to the outbox before any network attempt
```

```kotlin
// REQ-OUTBOX-002: append to the outbox before any network attempt
```

Every requirement assigned to a platform must be traceable to at least one citation in
that platform's generated code.

## 5. Definition of done

A client is **not done** until:

```bash
python scripts/conformance.py <platform>
```

passes. Not "compiles", not "looks right", not "tests mostly pass". Until the
conformance runner exits 0, the generation run is incomplete — keep iterating
(generate -> build -> run conformance -> read failures -> fix) or stop and report per §2.
