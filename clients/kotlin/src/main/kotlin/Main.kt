// GENERATED from spec/ by the generator - do not edit by hand
//
// State machine, outbox, inbound handling, reconnection and the observable event
// stream (spec/core/client-behavior.md, spec/core/cli-contract.md), over the wire
// protocol of spec/core/protocol.md.

package client

import java.net.URI
import java.net.http.HttpClient
import java.net.http.WebSocket
import java.nio.file.Path
import java.util.UUID
import java.util.concurrent.CompletionStage
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledExecutorService
import java.util.concurrent.TimeUnit
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

// REQ-STATE-001: exactly these five names, used verbatim in events
// (REQ-EVENT-004, REQ-COMPARE-004).
const val NO_IDENTITY = "NO_IDENTITY"
const val OFFLINE = "OFFLINE"
const val CONNECTING = "CONNECTING"
const val SYNCING = "SYNCING"
const val ONLINE = "ONLINE"

// REQ-RECONNECT-002: fixed 1 second interval -- no backoff, no jitter, no cap.
const val RETRY_MS = 1000L

// REQ-ERR-005: an error carrying ref_id with one of these codes is a permanent
// rejection; the message can never succeed as sent.
val PERMANENT_CODES = setOf("bad_name", "bad_text", "bad_frame")

private val JSON = Json { ignoreUnknownKeys = true; explicitNulls = false }

// REQ-STDIO-002: stdout carries only JSON Lines events, one object per line.
// REQ-STDIO-003: flushed immediately -- the conformance runner reads stdout
// synchronously and blocks on expected events.
// REQ-STDIO-006: single line; newlines inside strings are escaped by the encoder.
fun emit(event: JsonObject) {
    println(JSON.encodeToString(JsonObject.serializer(), event))
    System.out.flush()
}

// REQ-STDIO-005: all human-readable logging goes to stderr, never stdout.
fun logErr(message: String) = System.err.println("level=INFO logger=client $message")

class Client(private val url: String, dataDir: Path) {
    private val store = Store(dataDir)

    // REQ-STATE-008 / REQ-STDIO-008: one owner thread for all state and all stdout,
    // so the event stream is a deterministic serialisation of commands and frames.
    // java.net.http.WebSocket is callback driven and System.in has no non-blocking
    // read, so the stdin reader is a separate thread that posts here.
    private val exec: ScheduledExecutorService = Executors.newSingleThreadScheduledExecutor { r ->
        Thread(r, "client-state").apply { isDaemon = true }
    }
    private val http: HttpClient = HttpClient.newHttpClient()
    val done = CountDownLatch(1)

    // REQ-EVENT-002: ready reports NO_IDENTITY on a fresh data-dir, OFFLINE when an
    // identity was loaded (T1 / T2).
    private var state: String = if (store.name != null) OFFLINE else NO_IDENTITY

    // REQ-RECONNECT-001: the auto-reconnect armed flag.
    private var armed = false
    private var ws: WebSocket? = null
    private var generation = 0

    fun post(action: () -> Unit) = exec.execute {
        try {
            action()
        } catch (e: Exception) {
            logErr("internal error: ${e}")
        }
    }

    // REQ-STATE-004: the single gate for every transition in the T1-T18 table.
    // REQ-STATE-005: NO_IDENTITY is a start state only -- nothing sets it again.
    // REQ-STATE-002: emit state{from,to} on every real transition.
    // REQ-STATE-003: never for a self-transition, so retrying a connection is silent
    // on stdout and the stream stays bounded while the server is unreachable
    // (REQ-RECONNECT-009).
    private fun setState(next: String) {
        if (next == state) return
        emit(buildJsonObject { put("type", "state"); put("from", state); put("to", next) })
        state = next
    }

    private fun error(code: String, message: String, refId: String? = null) {
        emit(buildJsonObject {
            put("type", "error"); put("code", code); put("message", message)
            if (refId != null) put("ref_id", refId)
        })
    }

    fun start() {
        // REQ-EVENT-002: ready is the first line on stdout, exactly once, after the
        // persisted state is loaded (REQ-PERSIST-008) and before reading stdin.
        emit(buildJsonObject { put("type", "ready"); put("state", state) })
        store.name?.let {
            // T2: an identity loaded from disk re-emits logged_in and auto-connects
            // without a login (REQ-IDENTITY-004, REQ-EVENT-003).
            emit(buildJsonObject { put("type", "logged_in"); put("name", it) })
            arm()
        }
    }

    // -- commands -------------------------------------------------------------

    // REQ-CMD-001: the whole grammar -- login, send, offline, online, quit.
    // REQ-CMD-007: no stdin content may crash, hang or exit the client; the worst
    // outcome is an error event.
    // REQ-EVENT-001: these handlers emit only the seven defined event types.
    // REQ-ERRCODE-001: and only the defined client error codes.
    fun command(rawLine: String) {
        // REQ-STDIO-001: one command per line; a trailing CR is stripped, nothing else.
        val line = rawLine.removeSuffix("\r")
        // REQ-CMD-004: a blank or all-spaces line is ignored entirely.
        if (line.isBlank()) return
        val tokens = line.trim().split(Regex(" +"))
        // REQ-CMD-002: command words are lowercase and case-sensitive.
        when (tokens[0]) {
            "login" -> login(tokens)
            "send" -> send(line)
            "offline" -> offline(tokens)
            "online" -> online(tokens)
            "quit" -> quit(tokens)
            // REQ-CMD-005: unknown command word; never exit.
            else -> error("unknown_command", "unknown command '${tokens[0]}'")
        }
    }

    private fun login(tokens: List<String>) {
        // REQ-IDENTITY-001: an identity is required before connecting or sending.
        // REQ-CMD-006: login takes exactly one argument.
        if (tokens.size != 2) return error("bad_args", "usage: login <name>")
        // REQ-IDENTITY-005: identity is immutable, even for the same name.
        if (store.name != null) return error("already_logged_in", "identity is already set")
        // REQ-IDENTITY-003: validated locally, before persistence, never on the network.
        if (!validName(tokens[1])) return error("bad_name", "name must match [a-zA-Z0-9_-]{1,32}")
        store.saveIdentity(tokens[1])
        emit(buildJsonObject { put("type", "logged_in"); put("name", tokens[1]) })
        arm() // T4
    }

    private fun send(line: String) {
        // REQ-CMD-003: <to> is the token after the command word, and <text...> is the
        // entire remainder of the line after the single space following <to>, taken
        // verbatim -- no trimming, splitting, re-quoting or escape interpretation.
        val rest = line.trimStart(' ').removePrefix("send").trimStart(' ')
        val cut = rest.indexOf(' ')
        if (cut < 0) return error("bad_args", "usage: send <to> <text...>")
        val to = rest.substring(0, cut)
        val text = rest.substring(cut + 1)
        // REQ-STATE-006: a send with no identity is rejected and never queued.
        if (store.name == null) return error("not_logged_in", "login first")
        // REQ-OUTBOX-012: validate locally before queueing; no entry, no id consumed,
        // no `queued`, and therefore no ref_id on the error.
        if (!validName(to)) return error("bad_name", "recipient is not a valid name")
        if (!validText(text)) return error("bad_text", "text must be 1-4000 code points")
        // REQ-OUTBOX-003 steps 2-5. REQ-MSGID-001, REQ-MSGID-002, REQ-MSGID-004,
        // REQ-MSGID-005: a unique, opaque, lowercase canonical UUIDv4, generated here,
        // at the moment the user issues the send.
        val entry = Entry(UUID.randomUUID().toString(), to, text)
        store.outbox.add(entry)
        // REQ-OUTBOX-002: durably written BEFORE any network attempt.
        store.saveOutbox()
        // REQ-EVENT-005: queued{id,to,text}, after the write, before transmission.
        emit(buildJsonObject {
            put("type", "queued"); put("id", entry.id); put("to", entry.to); put("text", entry.text)
        })
        // REQ-FLUSH-004: while ONLINE, transmit immediately; REQ-STATE-007 /
        // REQ-FLUSH-005: otherwise queued only, and that is not an error.
        if (state == ONLINE) transmit(entry)
    }

    private fun offline(tokens: List<String>) {
        if (tokens.size != 1) return error("bad_args", "usage: offline")
        // REQ-TESTHOOK-001: offline/online simulate network loss deterministically.
        // REQ-TESTHOOK-002: close the connection immediately and disarm reconnect.
        // REQ-TESTHOOK-004: a no-op that still disarms when already OFFLINE (T8),
        // which setState makes silent.
        // REQ-TESTHOOK-006: neither hook touches persistent state.
        // REQ-TESTHOOK-007: there are no other hidden hooks or debug modes.
        armed = false
        dropConnection()
        setState(OFFLINE)
    }

    private fun online(tokens: List<String>) {
        if (tokens.size != 1) return error("bad_args", "usage: online")
        armed = true
        // REQ-TESTHOOK-005: while CONNECTING/SYNCING/ONLINE this only arms the flag --
        // no state event, and the existing attempt is not disturbed.
        if (state == CONNECTING || state == SYNCING || state == ONLINE) return
        if (store.name == null) return
        // T7 + REQ-RECONNECT-005: attempt immediately, without waiting out the interval.
        arm()
    }

    private fun quit(tokens: List<String>) {
        if (tokens.size != 1) return error("bad_args", "usage: quit")
        // REQ-CMD-008: exit 0 without waiting for acks, without flushing, without
        // dropping outbox entries -- all state is already durable. No state event.
        armed = false
        dropConnection()
        done.countDown()
    }

    // -- network --------------------------------------------------------------

    private fun arm() {
        armed = true
        // REQ-STATE-001 / REQ-RECONNECT-002: CONNECTING covers the whole attempt
        // period, including the gaps between retries, so a failed attempt never
        // leaves the state (T6, T10) and emits nothing.
        setState(CONNECTING)
        attempt()
    }

    private fun dropConnection() {
        generation++
        val current = ws
        ws = null
        current?.sendClose(WebSocket.NORMAL_CLOSURE, "bye")
        current?.abort()
    }

    private fun attempt() {
        if (!armed) return
        generation++
        val gen = generation
        // REQ-WIRE-006, REQ-WIRE-007: no subprotocol, extension or compression
        // requirement, and no application-level heartbeat.
        // REQ-RECONNECT-008: reconnecting never clears the outbox, the seen set or
        // the identity -- they live in the Store, untouched here.
        http.newWebSocketBuilder()
            .buildAsync(URI.create(url), Listener(gen))
            .whenComplete { socket, failure ->
                post {
                    if (gen != generation) return@post
                    if (failure != null) {
                        // REQ-RECONNECT-009: a connect failure emits no error event
                        // and no state event; detail goes to stderr.
                        logErr("connection attempt failed: ${failure.message}")
                        scheduleRetry()
                    } else {
                        ws = socket
                        // REQ-SYNC-001, REQ-SYNC-002: hello is the first frame, and no
                        // send or delivered goes out before welcome.
                        // REQ-C2S-001: hello{name}.
                        frame(socket, buildJsonObject {
                            put("v", 1); put("type", "hello"); put("name", store.name)
                        })
                    }
                }
            }
    }

    private fun scheduleRetry() {
        if (!armed) return
        // REQ-RECONNECT-003: measured from the end of the previous attempt.
        exec.schedule({ post { if (armed) attempt() } }, RETRY_MS, TimeUnit.MILLISECONDS)
    }

    private fun onDisconnected(gen: Int) {
        if (gen != generation) return
        ws = null
        if (!armed) return
        // T13 / T15: a disconnect from SYNCING or ONLINE is the one state event for
        // the loss; the retry loop that follows is silent.
        setState(CONNECTING)
        scheduleRetry()
    }

    // REQ-WIRE-002: exactly one JSON object per text frame.
    // REQ-C2S-004: hello, send and delivered are the only frames a client sends.
    private fun frame(socket: WebSocket, payload: JsonObject) {
        socket.sendText(JSON.encodeToString(JsonObject.serializer(), payload), true)
    }

    private fun transmit(entry: Entry) {
        val socket = ws ?: return
        // REQ-C2S-002, REQ-MSGID-003: always the entry's original id.
        frame(socket, buildJsonObject {
            put("v", 1); put("type", "send")
            put("id", entry.id); put("to", entry.to); put("text", entry.text)
        })
    }

    private fun flush() {
        // REQ-FLUSH-002: every entry, in FIFO order, with its original id.
        // REQ-FLUSH-003: entries already sent but unacked are re-sent with the same
        // id, which server-side dedup makes safe (REQ-DEDUP-002).
        // REQ-FLUSH-006: never reorder -- a send issued during a flush was appended at
        // the tail, so it goes out after these.
        // REQ-OUTBOX-008: entries restored from disk are live here and emit no queued.
        for (entry in store.outbox.toList()) transmit(entry)
    }

    private fun onFrame(gen: Int, raw: String) {
        if (gen != generation) return
        val obj = try {
            JSON.parseToJsonElement(raw).jsonObject
        } catch (e: Exception) {
            // REQ-WIRE-005: a malformed frame is ignored; the connection stays open.
            return
        }
        // REQ-FRAME-002, REQ-FRAME-005, REQ-FRAME-006, REQ-FRAME-007: a frame with a
        // bad v or a missing field is ignored by a client; key order and whitespace
        // are never relied on, and no undefined field is ever emitted.
        if (obj["v"]?.jsonPrimitive?.int != 1) return
        val socket = ws ?: return
        when (obj["type"]?.jsonPrimitive?.content) {
            "welcome" -> setState(SYNCING) // T9
            "sync_done" -> {
                // T12 + REQ-SYNC-008 / REQ-FLUSH-001: only now may the outbox flush.
                setState(ONLINE)
                flush()
            }
            "msg" -> onMsg(socket, obj)
            "ack" -> onAck(obj)
            "error" -> {
                if (obj["code"]?.jsonPrimitive?.content == "replaced") {
                    // T17 + REQ-RECONNECT-006 / REQ-SESSION-006: disarm and go OFFLINE;
                    // reconnecting would make two clients evict each other forever.
                    error("replaced", obj["message"]?.jsonPrimitive?.content ?: "")
                    armed = false
                    dropConnection()
                    setState(OFFLINE)
                } else {
                    onError(obj)
                }
            }
            // REQ-FRAME-003: any other type is ignored silently -- no error, no close,
            // no state change. REQ-FRAME-004: unknown fields are never read.
        }
    }

    private fun onMsg(socket: WebSocket, obj: JsonObject) {
        // REQ-INBOUND-002: deduplicated by id, persisted so it survives restarts.
        // REQ-INBOUND-007: `to` is informational -- never filter on it.
        // REQ-C2S-003: delivered{id} confirms durable acceptance.
        val id = obj["id"]?.jsonPrimitive?.content ?: return
        val confirm = buildJsonObject { put("v", 1); put("type", "delivered"); put("id", id) }
        if (store.seen.contains(id)) {
            // REQ-INBOUND-004: a duplicate is still confirmed, so the server can drop
            // its copy, but it must not be displayed again.
            frame(socket, confirm)
            return
        }
        // REQ-INBOUND-003: persist the id, THEN display, THEN confirm. Persisting
        // before confirming stops a crash in between from redisplaying the message.
        store.seen.add(id)
        store.saveSeen()
        // REQ-EVENT-007: id, from and text only -- `to` and `server_ts` are never
        // surfaced (REQ-TIME-004, REQ-COMPARE-003).
        emit(buildJsonObject {
            put("type", "received"); put("id", id)
            put("from", obj["from"]?.jsonPrimitive?.content)
            put("text", obj["text"]?.jsonPrimitive?.content)
        })
        // REQ-INBOUND-001: reply delivered (REQ-SNF-005 needs it to release the copy).
        frame(socket, confirm)
    }

    private fun onAck(obj: JsonObject) {
        val id = obj["id"]?.jsonPrimitive?.content ?: return
        // REQ-OUTBOX-006: an ack for an id not in the outbox is ignored -- no `sent`,
        // no error. This covers duplicate acks arising from REQ-DEDUP-002.
        if (!store.outbox.removeIf { it.id == id }) return
        // REQ-OUTBOX-005: remove, persist, THEN emit sent -- at most once per id.
        store.saveOutbox()
        // REQ-EVENT-006: sent{id} means the server took responsibility, not that the
        // recipient has seen it.
        emit(buildJsonObject { put("type", "sent"); put("id", id) })
    }

    private fun onError(obj: JsonObject) {
        // REQ-ERR-001: code is the contract, message is not parsed.
        // REQ-ERR-002: ref_id may be absent and must be tolerated.
        // REQ-ERR-007: an error does not close the connection or exit.
        // REQ-ERRCODE-002: the server's code is relayed verbatim, including codes
        // unknown to this client (REQ-ERR-004); never translated or remapped.
        // REQ-EVENT-008, REQ-EVENT-009: error{code,message,ref_id?} and no more.
        val code = obj["code"]?.jsonPrimitive?.content ?: return
        val ref = obj["ref_id"]?.jsonPrimitive?.content
        if (ref != null && code in PERMANENT_CODES) {
            // REQ-ERR-005 / REQ-OUTBOX-009: a permanent rejection can never succeed,
            // so drop the entry rather than retry it forever. No `sent`.
            if (store.outbox.removeIf { it.id == ref }) store.saveOutbox()
        }
        // REQ-ERR-006 / REQ-OUTBOX-010: any other code is retryable, so the entry
        // stays in the outbox.
        // REQ-ERRCODE-003: ref_id is surfaced whenever the error concerns a specific
        // message id, so a dropped entry is visible and attributable.
        error(code, obj["message"]?.jsonPrimitive?.content ?: "", ref)
    }

    fun shutdown() {
        post { armed = false; dropConnection() }
        exec.shutdown()
    }

    private inner class Listener(private val gen: Int) : WebSocket.Listener {
        private val buffer = StringBuilder()

        override fun onOpen(webSocket: WebSocket) {
            webSocket.request(1)
        }

        override fun onText(
            webSocket: WebSocket,
            data: CharSequence,
            last: Boolean,
        ): CompletionStage<*>? {
            // REQ-WIRE-002: a text frame may arrive in fragments; accumulate until
            // last before parsing, because one frame is exactly one JSON object.
            buffer.append(data)
            if (last) {
                val raw = buffer.toString()
                buffer.setLength(0)
                post { onFrame(gen, raw) }
            }
            webSocket.request(1)
            return null
        }

        // REQ-WIRE-003: a binary frame is ignored.
        override fun onBinary(
            webSocket: WebSocket,
            data: java.nio.ByteBuffer,
            last: Boolean,
        ): CompletionStage<*>? {
            webSocket.request(1)
            return null
        }

        override fun onClose(
            webSocket: WebSocket,
            statusCode: Int,
            reason: String,
        ): CompletionStage<*>? {
            post { onDisconnected(gen) }
            return null
        }

        override fun onError(webSocket: WebSocket, err: Throwable) {
            logErr("connection error: ${err.message}")
            post { onDisconnected(gen) }
        }
    }
}

fun main(args: Array<String>) {
    // REQ-CLI-002: only the run command varies by platform; these flags and every
    // behaviour are identical across platforms.
    // REQ-CLI-008: the two flags and stdin are the entire input surface -- no
    // environment variables, no external config files, no interactive prompts.
    var server: String? = null
    var dataDir: String? = null
    var i = 0
    while (i < args.size) {
        val arg = args[i]
        val eq = arg.indexOf('=')
        val (flag, inline) = if (arg.startsWith("--") && eq > 0) {
            arg.substring(0, eq) to arg.substring(eq + 1)
        } else {
            arg to null
        }
        // REQ-CLI-003: any flag order; both --flag value and --flag=value.
        val value = inline ?: args.getOrNull(++i)
        when (flag) {
            "--server" -> server = value
            "--data-dir" -> dataDir = value
            else -> {
                // REQ-CLI-004: a usage error writes to stderr and exits 2, having
                // written NOTHING to stdout -- in particular no ready event.
                System.err.println("unrecognised argument: $arg")
                kotlin.system.exitProcess(2)
            }
        }
        i++
    }
    if (server == null || dataDir == null) {
        System.err.println("usage: client --server <ws-url> --data-dir <path>")
        kotlin.system.exitProcess(2)
    }

    val client = try {
        // REQ-CLI-007: an unreachable server must not stop startup.
        Client(server, Path.of(dataDir))
    } catch (e: CorruptState) {
        // REQ-PERSIST-004: emit the error and exit 2, without deleting, truncating or
        // resetting the file -- losing queued messages silently is worse.
        emit(buildJsonObject {
            put("type", "error"); put("code", "corrupt_state"); put("message", e.detail)
        })
        kotlin.system.exitProcess(2)
    } catch (e: Exception) {
        // REQ-CLI-005: an unusable --data-dir is a usage error (REQ-CLI-004).
        System.err.println("cannot use --data-dir: ${e.message}")
        kotlin.system.exitProcess(2)
    }

    client.post { client.start() }

    // A dedicated blocking reader thread: System.in has no non-blocking read, and
    // REQ-STDIO-009 requires stdin to be read in every state.
    val reader = Thread({
        val input = System.`in`.bufferedReader(Charsets.UTF_8)
        while (true) {
            val line = input.readLine() ?: break
            // REQ-STDIO-008: commands are processed strictly in the order read, one at
            // a time, on the single owner thread.
            client.post { client.command(line) }
        }
        // REQ-STDIO-007: EOF on stdin is exactly the quit command (T18).
        client.post { client.command("quit") }
    }, "stdin")
    reader.isDaemon = true
    reader.start()

    client.done.await()
    client.shutdown()
    // REQ-CLI-006: 0 on quit or stdin EOF.
    kotlin.system.exitProcess(0)
}
