# Platform Spec: Kotlin / JVM CLI

**Scope: idioms, libraries, and build only. This file defines no behavior.**

Every behavioral question — what an event contains, when it is emitted, what happens on
reconnect — is answered by `spec/core/`. If this file ever appears to contradict
`spec/core/`, the core spec wins and this file is the bug. If a behavior is missing from
`spec/core/`, stop and report the ambiguity (CLAUDE.md §2); do not settle it here.

Target directory: `clients/kotlin/` (generated only).

## Toolchain

| Item | Requirement |
| --- | --- |
| Language | Kotlin (JVM), latest stable |
| JDK | **21** — set `jvmToolchain(21)` so the build is not host-JDK dependent |
| Build | Gradle **8.14.3** via the committed wrapper (`gradlew`, `gradlew.bat`, `gradle/wrapper/`) |
| Packaging | `application` plugin, run via `installDist` |

The wrapper is hand-provided toolchain bootstrap, not generated output: do not create,
modify, or delete `gradlew`, `gradlew.bat`, or `gradle/wrapper/` (see
`clients/kotlin/TOOLCHAIN.md`). Generate `settings.gradle.kts` and `build.gradle.kts`
around it.

## Dependencies

Allowed:

- `java.net.http.WebSocket` (JDK built-in) for the transport.
- `kotlinx.serialization` (`kotlinx-serialization-json`) for JSON.
- `kotlinx.coroutines` — optional, fine to use for the connection and retry logic.

Forbidden:

- Any chat, messaging, or realtime SDK. The protocol is implemented directly from
  `spec/core/protocol.md`.
- Any third-party WebSocket client (OkHttp, Ktor client, Java-WebSocket, …).
- Any JSON library other than `kotlinx.serialization`.
- Any dependency not needed to satisfy the core spec.

## Layout

```
clients/kotlin/
  settings.gradle.kts
  build.gradle.kts
  gradlew  gradlew.bat  gradle/wrapper/…
  src/main/kotlin/…          # package name is the generator's choice
```

The `application` block MUST set the distribution name so the launcher lands at
`build/install/client/bin/client` (and `client.bat` on Windows), matching
`platforms/kotlin.yaml`.

## JSON mapping

- Model frames as `@Serializable` classes, discriminated on `type`.
- Configure the `Json` instance with `ignoreUnknownKeys = true` and
  `encodeDefaults = true`. Unknown-key tolerance is how REQ-FRAME-004 is satisfied on
  this platform; an unrecognised `type` must not throw (REQ-FRAME-003), so decode the
  envelope before the payload.
- `explicitNulls = false`, so an absent optional field is omitted rather than serialised
  as `null`.
- Emit events with `Json.encodeToString`, one line per event, never pretty-printed.

## Concurrency model

- **stdin on a dedicated reader thread.** `java.net.http.WebSocket` is callback-driven
  and `System.in` has no non-blocking read, so a blocking `BufferedReader` loop on its
  own thread is the required shape. Hand each line to the single owner of client state.
- Serialise all state mutation through one owner — a coroutine actor with a `Channel`, or
  a single-threaded executor. The single logical timeline of REQ-STATE-008 and
  REQ-STDIO-008 is not optional: two threads writing events concurrently will interleave
  lines and fail conformance.
- Write stdout from that one owner, flushing per line (`println` + `System.out.flush()`,
  or a `PrintWriter(…, autoFlush = true)`).
- Text frames may be delivered in fragments: accumulate `onText` data until
  `last == true` before parsing (REQ-WIRE-002).

## Atomic writes

Use `java.nio.file.Files` for the temp-file-plus-rename idiom of REQ-PERSIST-002:

```kotlin
val tmp = Files.createTempFile(dir, "state", ".tmp")
Files.newOutputStream(tmp).use { out ->
    out.write(bytes)
    (out as? FileOutputStream)?.fd?.sync()      // or FileChannel.force(true)
}
Files.move(tmp, target, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
```

`ATOMIC_MOVE` with `REPLACE_EXISTING` is required: a plain `File.renameTo` fails over an
existing file on Windows. Create the temp file **in the target directory**, because
`ATOMIC_MOVE` is not guaranteed across filesystems.

## UTF-8 and text length

- Set `Charsets.UTF_8` explicitly on every stream; do not inherit the platform default.
- Kotlin `String.length` counts **UTF-16 code units**, which is not what REQ-TEXT-001
  specifies. Count code points: `text.codePointCount(0, text.length)`.

## Build and run

```
./gradlew installDist                      # posix
gradlew.bat installDist                    # windows
build/install/client/bin/client --server ws://127.0.0.1:8765/ws --data-dir .data/alice
```

Both commands run with `clients/kotlin/` as the working directory
(`platforms/kotlin.yaml`).
