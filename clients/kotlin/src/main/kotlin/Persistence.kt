// GENERATED from spec/ by the generator - do not edit by hand
//
// On-disk state: identity, outbox, seen set (REQ-PERSIST-001).

package client

import java.nio.ByteBuffer
import java.nio.channels.FileChannel
import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardCopyOption
import java.nio.file.StandardOpenOption
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

class CorruptState(val detail: String) : Exception(detail)

// REQ-NAME-001: 1-32 chars from [a-zA-Z0-9_-]. REQ-NAME-002, REQ-NAME-003:
// case-sensitive, never trimmed, case-folded or Unicode-normalised, so the pattern
// is anchored and total.
private val NAME_RE = Regex("^[A-Za-z0-9_-]{1,32}$")

fun validName(value: String?): Boolean = value != null && NAME_RE.matches(value)

// REQ-TEXT-001: length is counted in Unicode CODE POINTS, not bytes and not UTF-16
// code units -- String.length would be wrong for non-BMP characters such as emoji.
// REQ-TEXT-002: out-of-range length is invalid.
// REQ-TEXT-003: text is opaque -- measured here, never rewritten.
// REQ-TEXT-004: any JSON-legal code point is allowed, including newlines and tabs.
// REQ-TEXT-005: unpaired surrogates are invalid.
fun validText(value: String?): Boolean {
    if (value == null) return false
    val points = value.codePointCount(0, value.length)
    if (points < 1 || points > 4000) return false
    var i = 0
    while (i < value.length) {
        val ch = value[i]
        if (Character.isHighSurrogate(ch)) {
            if (i + 1 >= value.length || !Character.isLowSurrogate(value[i + 1])) return false
            i += 2
            continue
        }
        if (Character.isLowSurrogate(ch)) return false
        i++
    }
    return true
}

data class Entry(val id: String, val to: String, val text: String)

/**
 * The three state files and nothing else (REQ-PERSIST-001).
 *
 * REQ-PERSIST-006: everything is rooted at the given data-dir, so clients with
 * different data-dirs share nothing and can run concurrently.
 * REQ-PERSIST-007: sharing one data-dir between processes is unsupported, and this
 * class does not try to detect it.
 * REQ-INBOUND-006: the seen set is never evicted from.
 */
class Store(private val dir: Path) {
    private val json = Json { ignoreUnknownKeys = true }
    private val identityPath: Path = dir.resolve("identity.json")
    private val outboxPath: Path = dir.resolve("outbox.json")
    private val seenPath: Path = dir.resolve("seen.json")

    var name: String? = null
        private set
    val outbox: MutableList<Entry> = mutableListOf()
    val seen: MutableSet<String> = linkedSetOf()

    init {
        // REQ-PERSIST-005: create the data dir, including missing parents.
        Files.createDirectories(dir)
        // REQ-PERSIST-008: all state is loaded before `ready` is emitted.
        load()
    }

    private fun read(path: Path): JsonObject? {
        // REQ-PERSIST-003: UTF-8 JSON objects carrying "v": 1. A missing file is
        // empty state, not an error.
        if (!Files.exists(path)) return null
        val raw = try {
            Files.readString(path, StandardCharsets.UTF_8)
        } catch (e: Exception) {
            throw CorruptState("${path.fileName}: ${e.message}")
        }
        val obj = try {
            json.parseToJsonElement(raw).jsonObject
        } catch (e: Exception) {
            throw CorruptState("${path.fileName}: not valid JSON")
        }
        if (obj["v"]?.jsonPrimitive?.int != 1) throw CorruptState("${path.fileName}: not v1")
        return obj
    }

    private fun load() {
        read(identityPath)?.let { obj ->
            val stored = obj["name"]?.jsonPrimitive?.content
            // REQ-IDENTITY-002: a stored name failing REQ-NAME-001 is corrupt state.
            if (!validName(stored)) throw CorruptState("identity.json: name is not valid")
            name = stored
        }
        read(outboxPath)?.let { obj ->
            val entries = try {
                obj["entries"]!!.jsonArray
            } catch (e: Exception) {
                throw CorruptState("outbox.json: entries is not a list")
            }
            // REQ-OUTBOX-001: array order is queue order, preserved across restarts.
            for (element in entries) {
                val e = try {
                    element.jsonObject
                } catch (ex: Exception) {
                    throw CorruptState("outbox.json: malformed entry")
                }
                val id = e["id"]?.jsonPrimitive?.content
                val to = e["to"]?.jsonPrimitive?.content
                val text = e["text"]?.jsonPrimitive?.content
                if (id == null || !validName(to) || !validText(text)) {
                    throw CorruptState("outbox.json: malformed entry")
                }
                outbox.add(Entry(id, to!!, text!!))
            }
        }
        read(seenPath)?.let { obj ->
            val ids = try {
                obj["seen"]!!.jsonArray
            } catch (e: Exception) {
                throw CorruptState("seen.json: seen is not a list")
            }
            for (element in ids) seen.add(element.jsonPrimitive.content)
        }
    }

    private fun writeAtomic(target: Path, body: JsonObject) {
        // REQ-PERSIST-002: serialise in full to a temp file IN THE SAME DIRECTORY,
        // flush it to durable storage, then rename over the target. Never modify in
        // place, never truncate-then-write, never append. ATOMIC_MOVE with
        // REPLACE_EXISTING is required: File.renameTo fails over an existing file on
        // Windows, and ATOMIC_MOVE is not guaranteed across filesystems.
        val tmp = Files.createTempFile(dir, "state", ".tmp")
        val bytes = json.encodeToString(JsonObject.serializer(), body)
            .toByteArray(StandardCharsets.UTF_8)
        FileChannel.open(tmp, StandardOpenOption.WRITE).use { channel ->
            channel.write(ByteBuffer.wrap(bytes))
            channel.force(true)
        }
        Files.move(
            tmp, target,
            StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING,
        )
    }

    // REQ-IDENTITY-002: persisted before `logged_in` and before any network attempt.
    fun saveIdentity(newName: String) {
        name = newName
        writeAtomic(identityPath, buildJsonObject { put("v", 1); put("name", newName) })
    }

    // REQ-OUTBOX-013
    fun saveOutbox() {
        writeAtomic(outboxPath, buildJsonObject {
            put("v", 1)
            put("entries", buildJsonArray {
                for (e in outbox) add(buildJsonObject {
                    put("id", e.id); put("to", e.to); put("text", e.text)
                })
            })
        })
    }

    // REQ-INBOUND-008: array order is not significant.
    fun saveSeen() {
        writeAtomic(seenPath, buildJsonObject {
            put("v", 1)
            put("seen", buildJsonArray { for (id in seen) add(kotlinx.serialization.json.JsonPrimitive(id)) })
        })
    }
}
