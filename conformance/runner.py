"""HAND-WRITTEN, NOT generated. See conformance/README.md.

The language-agnostic conformance runner: starts the server, launches clients from
their platform manifests, drives them over stdin, and matches their stdout events
against spec/scenarios/*.yaml.
"""

from __future__ import annotations

import argparse
import itertools
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from . import manifest as manifest_mod
from . import scenario as scenario_mod
from .clientproc import ClientProcess, Event
from .manifest import REPO_ROOT, Manifest
from .scenario import Scenario, Step
from .serverctl import ServerProcess

RUNS_DIR = REPO_ROOT / ".data" / "conformance"


class StepFailure(Exception):
    def __init__(self, step: Step, reason: str) -> None:
        super().__init__(reason)
        self.step = step
        self.reason = reason


# -- matching --------------------------------------------------------------------


def substitute(value: object, bindings: dict[str, str]) -> object:
    """Replace "$name" with a captured value (REQ-COMPARE-008)."""
    if isinstance(value, str) and value.startswith("$"):
        key = value[1:]
        if key not in bindings:
            raise KeyError(f"${key} is not bound yet")
        return bindings[key]
    return value


def matches(event: Event, match: dict, bindings: dict[str, str]) -> bool:
    """REQ-COMPARE-001: compare type plus the listed fields only, exactly.

    REQ-COMPARE-002: fields the expectation does not name are ignored.
    REQ-COMPARE-004: comparison is case-sensitive.
    """
    if event.raw is not None:
        return False
    for key, expected in match.items():
        if event.get(key) != substitute(expected, bindings):
            return False
    return True


def render(match: dict, bindings: dict[str, str]) -> str:
    out = {}
    for key, value in match.items():
        try:
            resolved = substitute(value, bindings)
        except KeyError:
            resolved = f"{value} (unbound)"
        out[key] = resolved
    return str(out)


# -- one run ---------------------------------------------------------------------


@dataclass
class Result:
    scenario: str
    assignment: dict[str, str]
    ok: bool
    detail: str = ""
    duration_s: float = 0.0

    @property
    def label(self) -> str:
        roles = ", ".join(f"{role}={plat}" for role, plat in self.assignment.items())
        return f"{self.scenario} [{roles}]"


class ScenarioRun:
    def __init__(self, scenario: Scenario, assignment: dict[str, str],
                 manifests: dict[str, Manifest], run_dir: Path) -> None:
        self.scenario = scenario
        self.assignment = assignment
        self.manifests = manifests
        self.run_dir = run_dir
        self.bindings: dict[str, str] = {}
        self.clients: dict[str, ClientProcess] = {}

    def execute(self) -> Result:
        started = time.monotonic()
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)
        self.run_dir.mkdir(parents=True)
        server = ServerProcess(self.run_dir)
        try:
            server.start()
            for actor in self.scenario.actors:
                platform = self.assignment[actor]
                self.clients[actor] = ClientProcess(
                    role=actor,
                    manifest=self.manifests[platform],
                    # REQ-PERSIST-006: a fresh, private data-dir per client.
                    data_dir=self.run_dir / f"data-{actor}",
                    server_url=server.url,
                    log_dir=self.run_dir,
                )
                self.clients[actor].start()
            for step in self.scenario.steps:
                self._run_step(step)
        except StepFailure as failure:
            return Result(
                self.scenario.name, self.assignment, False,
                self._report(failure), time.monotonic() - started,
            )
        except Exception as exc:  # harness fault, not a client failure
            return Result(
                self.scenario.name, self.assignment, False,
                f"runner error: {type(exc).__name__}: {exc}\n  run dir: {self.run_dir}",
                time.monotonic() - started,
            )
        finally:
            for client in self.clients.values():
                client.close()
            server.stop()
        return Result(self.scenario.name, self.assignment, True,
                      duration_s=time.monotonic() - started)

    def _run_step(self, step: Step) -> None:
        client = self.clients[step.actor]
        action = step.action

        if action == "command":
            client.send(str(step.value))
            return

        if action == "expect":
            match = dict(step.value)  # type: ignore[arg-type]
            event = client.next_event(step.timeout_ms)
            if event is None:
                if client.stream_ended:
                    reason = (
                        f"stdout ended before {render(match, self.bindings)} arrived; "
                        f"the client is no longer running"
                    )
                else:
                    reason = (
                        f"timed out after {step.timeout_ms}ms waiting for "
                        f"{render(match, self.bindings)}"
                    )
                raise StepFailure(step, reason)
            if not matches(event, match, self.bindings):
                raise StepFailure(
                    step,
                    f"expected {render(match, self.bindings)}\n     but got {event}",
                )
            for var, field_name in step.capture.items():
                if field_name not in event:
                    raise StepFailure(
                        step, f"cannot capture ${var}: event has no field {field_name!r}"
                    )
                self.bindings[var] = event[field_name]
            return

        if action == "expect_none":
            match = dict(step.value)  # type: ignore[arg-type]
            arrived = client.events_during(step.window_ms)
            offenders = [e for e in arrived if matches(e, match, self.bindings)]
            if offenders:
                raise StepFailure(
                    step,
                    f"expected NO event matching {render(match, self.bindings)} "
                    f"within {step.window_ms}ms, but got {offenders[0]}",
                )
            return

        if action == "kill":
            client.kill()
            return

        if action == "start":
            client.start()
            return

        if action == "snapshot":
            client.snapshot(str(step.value))
            return

        if action == "restore":
            client.restore(str(step.value))
            return

        raise StepFailure(step, f"unsupported action {action!r}")

    def _report(self, failure: StepFailure) -> str:
        step = failure.step
        lines = [
            f"step {step.index}: {step.describe()}",
            f"  {failure.reason}",
        ]
        if self.bindings:
            lines.append(f"  bindings: {self.bindings}")
        for actor, client in self.clients.items():
            platform = self.assignment[actor]
            code = client.exit_code()
            if code is None and client.stream_ended:
                code = client.wait_exit(2.0)
            status = "running" if code is None else f"exited {code}"
            lines.append(f"  last 20 events from {actor} ({platform}, {status}):")
            tail = client.tail(20)
            lines.extend(tail if tail else ["     (no events)"])
            if code is not None and code != 0:
                lines.append(
                    f"  {actor} is not running -- is the {platform} client generated "
                    f"and built? last stderr:"
                )
                lines.extend(client.stderr_tail(10) or ["     | (stderr empty)"])
        lines.append(f"  logs and data dirs: {self.run_dir}")
        return "\n".join(lines)


# -- orchestration ---------------------------------------------------------------


def assignments(scenario: Scenario, platforms: list[str], matrix: bool,
                roles: dict[str, str]) -> list[dict[str, str]]:
    """Role-to-platform assignments for one scenario.

    Scenarios are role-neutral, so either client can play either part. --matrix
    walks every combination; duplicates are dropped for single-actor scenarios.
    """
    if not matrix:
        return [{actor: roles[actor] for actor in scenario.actors}]
    seen: list[dict[str, str]] = []
    for combo in itertools.product(platforms, repeat=len(scenario.actors)):
        candidate = dict(zip(scenario.actors, combo))
        if candidate not in seen:
            seen.append(candidate)
    return seen


def build(mf: Manifest) -> None:
    import os
    import subprocess

    print(f"building {mf.name}: {' '.join(mf.build_argv)} (cwd {mf.out_dir})")
    if mf.env:
        print(f"  with env {mf.env}")
    done = subprocess.run(
        mf.build_argv,
        cwd=str(mf.cwd),
        env={**os.environ, **mf.env} if mf.env else None,
    )
    if done.returncode != 0:
        raise SystemExit(f"build failed for {mf.name} (exit {done.returncode})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="conformance",
        description="Run spec/scenarios/*.yaml against generated clients.",
    )
    parser.add_argument("platform", nargs="?",
                        help="platform for every role (shorthand for --alice X --bob X)")
    parser.add_argument("--alice", help="platform playing alice")
    parser.add_argument("--bob", help="platform playing bob")
    parser.add_argument("--matrix", action="store_true",
                        help="run every scenario in every platform combination")
    parser.add_argument("--platforms", default=None,
                        help="comma-separated platform list for --matrix (default: all)")
    parser.add_argument("--scenario", action="append", default=None,
                        help="run only this scenario (repeatable)")
    parser.add_argument("--build", action="store_true",
                        help="run each platform's build_cmd first")
    parser.add_argument("--list", action="store_true", help="list scenarios and exit")
    args = parser.parse_args(argv)

    scenarios = scenario_mod.load_all(args.scenario)
    if args.list:
        for s in scenarios:
            print(f"{s.name}: {s.title}")
            print(f"  actors: {', '.join(s.actors)}  steps: {len(s.steps)}")
            print(f"  requirements: {', '.join(s.requirements) or '(none listed)'}")
        return 0

    if args.matrix:
        platforms = (args.platforms.split(",") if args.platforms
                     else manifest_mod.available())
        roles: dict[str, str] = {}
    else:
        alice = args.alice or args.platform
        bob = args.bob or args.platform or alice
        if not alice:
            parser.error("give a platform, or --alice/--bob, or --matrix")
        platforms = sorted({alice, bob})
        roles = {"alice": alice, "bob": bob}
        # Any actor a scenario names beyond alice/bob defaults to alice's platform.
        for s in scenarios:
            for actor in s.actors:
                roles.setdefault(actor, alice)

    manifests = {name: manifest_mod.load(name) for name in platforms}
    if args.build:
        for mf in manifests.values():
            build(mf)

    results: list[Result] = []
    for s in scenarios:
        for assignment in assignments(s, platforms, args.matrix, roles):
            tag = "-".join(f"{r}_{p}" for r, p in assignment.items())
            run = ScenarioRun(s, assignment, manifests, RUNS_DIR / f"{s.name}-{tag}")
            result = run.execute()
            results.append(result)
            mark = "PASS" if result.ok else "FAIL"
            print(f"{mark}  {result.label}  ({result.duration_s:.1f}s)", flush=True)
            if not result.ok:
                print(result.detail, flush=True)

    failed = [r for r in results if not r.ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    if failed:
        print("failed:")
        for r in failed:
            print(f"  - {r.label}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
