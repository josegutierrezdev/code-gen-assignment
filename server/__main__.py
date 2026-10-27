"""HAND-WRITTEN, NOT generated. See server/README.md.

CLI entry point:  python -m server --port 8765
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from .app import run


def _configure_logging(level: str) -> None:
    """Structured, one record per line, on stderr -- never stdout."""
    logging.basicConfig(
        stream=sys.stderr,
        level=getattr(logging, level.upper()),
        format="ts=%(asctime)s.%(msecs)03dZ level=%(levelname)s logger=%(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    logging.Formatter.converter = __import__("time").gmtime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--log-level", default="info", choices=["debug", "info", "warning", "error"]
    )
    args = parser.parse_args(argv)

    _configure_logging(args.log_level)
    try:
        asyncio.run(run(args.host, args.port))
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
