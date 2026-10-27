"""HAND-WRITTEN, NOT generated. See conformance/README.md.

Starts the hand-written reference server on a free port, one fresh instance per
scenario run. The server is in-memory, so a fresh process is the only way to get a
clean dedup record and empty held queues between scenarios.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

from .manifest import REPO_ROOT


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class ServerProcess:
    def __init__(self, log_dir: Path) -> None:
        self.port = free_port()
        self.url = f"ws://127.0.0.1:{self.port}/ws"
        self._log = open(log_dir / "server.stderr.log", "ab")
        self._proc: subprocess.Popen | None = None

    def start(self, timeout_s: float = 20.0) -> None:
        self._proc = subprocess.Popen(
            [sys.executable, "-m", "server", "--port", str(self.port)],
            cwd=str(REPO_ROOT),
            stdin=subprocess.DEVNULL,
            stdout=self._log,
            stderr=self._log,
        )
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                raise RuntimeError(
                    f"server exited with {self._proc.returncode} during startup; "
                    f"see {self._log.name}"
                )
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.5):
                    return
            except OSError:
                time.sleep(0.05)
        raise RuntimeError(f"server did not open port {self.port} within {timeout_s}s")

    def stop(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=5)
        self._log.close()

    def __enter__(self) -> "ServerProcess":
        self.start()
        return self

    def __exit__(self, *_exc) -> None:
        self.stop()
