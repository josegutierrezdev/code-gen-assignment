"""HAND-WRITTEN, NOT generated. See conformance/README.md.

One client under test: process lifecycle, stdin commands, and the stdout JSON Lines
event stream with a per-client stream position.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

from .manifest import Manifest


class Event(dict):
    """A parsed stdout event. ``raw`` is set when the line was not a JSON object,
    which is itself a REQ-STDIO-002 violation and fails any expectation."""

    def __init__(self, data: dict | None = None, raw: str | None = None) -> None:
        super().__init__(data or {})
        self.raw = raw

    def __str__(self) -> str:
        if self.raw is not None:
            return f"<non-JSON stdout line: {self.raw!r}>"
        return json.dumps(self, ensure_ascii=False, sort_keys=True)


class ClientProcess:
    def __init__(self, role: str, manifest: Manifest, data_dir: Path, server_url: str,
                 log_dir: Path) -> None:
        self.role = role
        self.manifest = manifest
        self.data_dir = data_dir
        self.server_url = server_url
        self.log_dir = log_dir
        self.events: list[Event] = []
        self.pos = 0
        self._cond = threading.Condition()
        self._proc: subprocess.Popen | None = None
        self._stdin: io.TextIOWrapper | None = None
        self._reader: threading.Thread | None = None
        self._stderr = open(log_dir / f"{role}.stderr.log", "ab")
        self._launches = 0
        self._snapshots: dict[str, Path] = {}
        self._eof = True

    # -- lifecycle --------------------------------------------------------------

    @property
    def argv(self) -> list[str]:
        # REQ-CLI-001: the runner supplies exactly these two flags.
        return [*self.manifest.run_argv, "--server", self.server_url,
                "--data-dir", str(self.data_dir)]

    def start(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            raise RuntimeError(f"{self.role}: already running")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._launches += 1
        self._eof = False
        self._stderr.write(f"\n=== launch {self._launches}: {self.argv} ===\n".encode())
        self._stderr.flush()
        self._proc = subprocess.Popen(
            self.argv,
            cwd=str(self.manifest.cwd),
            env={**os.environ, **self.manifest.env} if self.manifest.env else None,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._stderr,
            bufsize=0,
        )
        # Explicit wrappers: the line endings and encoding must not depend on the host.
        self._stdin = io.TextIOWrapper(
            self._proc.stdin, encoding="utf-8", newline="\n", write_through=True
        )
        stdout = io.TextIOWrapper(
            self._proc.stdout, encoding="utf-8", errors="replace", newline=""
        )
        self._reader = threading.Thread(
            target=self._read_stdout, args=(stdout,), daemon=True,
            name=f"stdout-{self.role}",
        )
        self._reader.start()

    def _read_stdout(self, stdout: io.TextIOWrapper) -> None:
        try:
            for line in stdout:
                line = line.rstrip("\r\n")
                if not line:
                    continue  # REQ-STDIO-004 forbids it; tolerate rather than crash
                try:
                    parsed = json.loads(line)
                except ValueError:
                    event = Event(raw=line)
                else:
                    event = (
                        Event(parsed) if isinstance(parsed, dict) else Event(raw=line)
                    )
                with self._cond:
                    self.events.append(event)
                    self._cond.notify_all()
        except (ValueError, OSError):
            pass
        finally:
            with self._cond:
                self._eof = True
                self._cond.notify_all()

    def send(self, command: str) -> None:
        if self._stdin is None or (self._proc and self._proc.poll() is not None):
            raise RuntimeError(f"{self.role}: not running, cannot send {command!r}")
        self._stdin.write(command + "\n")

    def kill(self) -> None:
        """Abrupt termination: no flush, no cleanup, data-dir left as it is.

        The whole process TREE must die, not just the direct child. A manifest may
        launch the client through a wrapper script -- Gradle's `client.bat` spawns
        java.exe as a child -- and killing only the wrapper leaves an orphan still
        holding the data-dir and its server session, which breaks the relaunch a
        scenario is trying to test. Killing the tree is also the more honest
        simulation of a crash.
        """
        if self._proc is None:
            return
        if self._proc.poll() is None:
            if os.name == "nt":
                # taskkill walks the tree; /F is required because the wrapper is a
                # console process that would otherwise be asked politely.
                subprocess.run(
                    ["taskkill", "/T", "/F", "/PID", str(self._proc.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:
                self._proc.kill()
        self._proc.wait(timeout=10)
        if self._reader is not None:
            self._reader.join(timeout=5)
        self._proc = None
        self._stdin = None

    @property
    def stream_ended(self) -> bool:
        """stdout has hit EOF: the client closed it or exited, so no further
        event can ever arrive."""
        return self._eof

    def exit_code(self) -> int | None:
        return None if self._proc is None else self._proc.poll()

    def wait_exit(self, timeout: float = 2.0) -> int | None:
        """Reap the process if it is on its way out, so a failure report can show
        the real exit code rather than 'running'."""
        if self._proc is None:
            return None
        try:
            return self._proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None

    def close(self) -> None:
        self.kill()
        self._stderr.close()

    # -- data-dir snapshots -----------------------------------------------------

    def snapshot(self, label: str) -> None:
        if self._proc is not None and self._proc.poll() is None:
            raise RuntimeError(f"{self.role}: kill before taking a snapshot")
        dest = self.log_dir / f"snapshot-{self.role}-{label}"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(self.data_dir, dest)
        self._snapshots[label] = dest

    def restore(self, label: str) -> None:
        if label not in self._snapshots:
            raise RuntimeError(f"{self.role}: no snapshot named {label!r}")
        if self._proc is not None and self._proc.poll() is None:
            raise RuntimeError(f"{self.role}: kill before restoring a snapshot")
        if self.data_dir.exists():
            shutil.rmtree(self.data_dir)
        shutil.copytree(self._snapshots[label], self.data_dir)

    # -- event stream -----------------------------------------------------------

    def next_event(self, timeout_ms: int) -> Event | None:
        """The next unconsumed event, advancing the stream position.

        Returns None on timeout, leaving the position untouched.
        """
        deadline = time.monotonic() + timeout_ms / 1000
        with self._cond:
            while self.pos >= len(self.events):
                # Nothing more can ever arrive once stdout has hit EOF, so fail
                # immediately instead of waiting out the timeout -- a client that
                # never started is the common case. EOF is the signal rather than
                # the exit code, because the pipe closes before the process is
                # reaped and poll() still reports None at that moment.
                if self._eof:
                    return None
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._cond.wait(remaining)
            event = self.events[self.pos]
            self.pos += 1
            return event

    def events_during(self, window_ms: int) -> list[Event]:
        """Events that arrive during the window, WITHOUT consuming them.

        expect_none must not disturb the transcript position, so anything that
        arrives here is still matched by later expect steps.
        """
        start_pos = self.pos
        deadline = time.monotonic() + window_ms / 1000
        with self._cond:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._cond.wait(remaining)
        return self.events[start_pos:]

    def stderr_tail(self, count: int = 10) -> list[str]:
        try:
            with open(self.log_dir / f"{self.role}.stderr.log", encoding="utf-8",
                      errors="replace") as handle:
                lines = [line.rstrip() for line in handle if line.strip()]
        except OSError:
            return []
        return [f"     | {line}" for line in lines[-count:]]

    def tail(self, count: int = 20) -> list[str]:
        marker = self.pos
        lines = []
        for i, event in enumerate(self.events[-count:], start=max(0, len(self.events) - count)):
            cursor = "->" if i == marker else "  "
            lines.append(f"  {cursor} [{i}] {event}")
        if marker >= len(self.events):
            lines.append(f"     -> [{marker}] (awaiting next event)")
        return lines
