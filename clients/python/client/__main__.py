# GENERATED from spec/ by the generator - do not edit by hand
#
# CLI entry point (spec/core/cli-contract.md section 1).

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from .core import Client, emit
from .persistence import CorruptState


def main(argv: list[str] | None = None) -> int:
    # REQ-STDIO-002/006: UTF-8, LF line endings, set explicitly rather than
    # inherited from the host locale.
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.stderr.reconfigure(encoding="utf-8")
    # REQ-STDIO-005: all human-readable logging goes to stderr, never stdout.
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="level=%(levelname)s logger=%(name)s %(message)s",
    )

    # REQ-CLI-002: only the run command varies by platform; these flags and every
    # behaviour are identical across platforms.
    # REQ-CLI-008: the two flags and stdin are the entire input surface -- no
    # environment variables, no external config files, no interactive prompts.
    parser = argparse.ArgumentParser(prog="python -m client", add_help=True)
    # REQ-CLI-001: both flags are required. REQ-CLI-003: any order; argparse also
    # accepts the --flag=value form. REQ-CLI-004: argparse reports a usage error on
    # stderr and exits 2, having written nothing to stdout -- in particular no ready.
    parser.add_argument("--server", required=True)
    parser.add_argument("--data-dir", required=True)
    args = parser.parse_args(argv)

    try:
        # REQ-CLI-007: an unreachable server must not stop startup.
        client = Client(args.server, Path(args.data_dir))
    except CorruptState as exc:
        # REQ-PERSIST-004: emit the error and exit 2, without deleting, truncating or
        # resetting the file -- losing queued messages silently is worse.
        emit({"type": "error", "code": "corrupt_state", "message": exc.detail})
        return 2
    except OSError as exc:
        # REQ-CLI-005: an unusable --data-dir is a usage error (REQ-CLI-004).
        print(f"cannot use --data-dir: {exc}", file=sys.stderr)
        return 2

    try:
        # REQ-CLI-006: 0 on quit or stdin EOF.
        return asyncio.run(client.run())
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
