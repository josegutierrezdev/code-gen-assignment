# clients/kotlin — toolchain bootstrap (HAND-PROVIDED, NOT GENERATED)

`clients/kotlin/` is **generated only**, with exactly one exception: the Gradle wrapper.

| Path | Origin |
| --- | --- |
| `gradlew` | hand-provided |
| `gradlew.bat` | hand-provided |
| `gradle/wrapper/gradle-wrapper.jar` | hand-provided |
| `gradle/wrapper/gradle-wrapper.properties` | hand-provided |
| `TOOLCHAIN.md` | hand-provided (this file) |
| everything else | generated — see the header on each file |

These carry **no** `GENERATED from spec/` header, and a generation run must neither
create, modify, nor delete them. They are deliberately absent from `clean_globs` in
`platforms/kotlin.yaml`, so every clean and regeneration leaves them in place; a test in
`conformance/tests/test_runner.py` enforces that.

## Why it is not generated

The wrapper jar is a binary artifact. It can only be produced by a real Gradle
installation running the `wrapper` task — a model cannot write it, and nothing in
`spec/` describes it. It is toolchain bootstrap, not an implementation of any
requirement.

## How it was produced

```
gradle wrapper --gradle-version 8.14.3 --distribution-type bin
```

run with Gradle 8.14.3 against JDK 21 (Temurin 21.0.8). Gradle's `wrapper` task needs an
existing build in the directory, so a one-line placeholder `settings.gradle.kts` was
created for the run and removed afterwards — the real one is generated.

To regenerate it after a Gradle upgrade, run the same command with the new version and
update this file.

## Environment

`platforms/kotlin.yaml` sets `TEMP`, `TMP`, and `GRADLE_USER_HOME` under `env.windows`,
so `gradlew` works with no manual setup. `TEMP` is load-bearing: a Gradle build runs in a
daemon JVM, and JDK 16+ backs its NIO pipes with an AF_UNIX socket **file** in the temp
directory. When that directory is unwritable or its volume is full, Gradle fails with

```
java.io.IOException: Unable to establish loopback connection
Caused by: java.net.SocketException: Invalid argument: connect
```

which reads like a network fault but is not one. See the comments in the manifest.
