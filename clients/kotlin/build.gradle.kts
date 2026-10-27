// GENERATED from spec/ by the generator - do not edit by hand
plugins {
    kotlin("jvm") version "2.0.21"
    kotlin("plugin.serialization") version "2.0.21"
    application
}

repositories { mavenCentral() }

dependencies {
    // spec/platforms/kotlin.md: kotlinx.serialization for JSON; the transport is
    // java.net.http.WebSocket from the JDK. No third-party WebSocket or JSON library.
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.3")
}

// spec/platforms/kotlin.md: JDK 21 toolchain, so the build is not host-JDK dependent.
kotlin { jvmToolchain(21) }

application {
    mainClass.set("client.MainKt")
    // platforms/kotlin.yaml run_cmd expects build/install/client/bin/client
    applicationName = "client"
}
