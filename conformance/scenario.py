"""HAND-WRITTEN, NOT generated. See conformance/README.md.

Loads and validates spec/scenarios/*.yaml. The schema is documented in
spec/scenarios/README.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .manifest import REPO_ROOT

SCENARIOS_DIR = REPO_ROOT / "spec" / "scenarios"

ACTIONS = ("command", "expect", "expect_none", "kill", "start", "snapshot", "restore")
DEFAULT_TIMEOUT_MS = 5000
DEFAULT_WINDOW_MS = 1000


class ScenarioError(RuntimeError):
    pass


@dataclass(frozen=True)
class Step:
    index: int
    actor: str
    action: str
    value: object
    timeout_ms: int = DEFAULT_TIMEOUT_MS
    window_ms: int = DEFAULT_WINDOW_MS
    capture: dict[str, str] = field(default_factory=dict)

    def describe(self) -> str:
        if self.action == "command":
            return f"{self.actor}: command {self.value!r}"
        if self.action in ("expect", "expect_none"):
            return f"{self.actor}: {self.action} {self.value}"
        return f"{self.actor}: {self.action} {self.value if self.value is not True else ''}".strip()


@dataclass(frozen=True)
class Scenario:
    name: str
    title: str
    path: Path
    actors: tuple[str, ...]
    requirements: tuple[str, ...]
    steps: tuple[Step, ...]


def _parse_step(raw: object, index: int, actors: tuple[str, ...], source: str) -> Step:
    if not isinstance(raw, dict):
        raise ScenarioError(f"{source}: step {index} is not a mapping")
    if "actor" not in raw:
        raise ScenarioError(f"{source}: step {index} has no actor")
    actor = raw["actor"]
    if actor not in actors:
        raise ScenarioError(
            f"{source}: step {index} names actor {actor!r}, which is not in actors: {list(actors)}"
        )
    present = [a for a in ACTIONS if a in raw]
    if len(present) != 1:
        raise ScenarioError(
            f"{source}: step {index} must have exactly one action key "
            f"({', '.join(ACTIONS)}), found {present or 'none'}"
        )
    action = present[0]
    value = raw[action]
    if action in ("expect", "expect_none"):
        if not isinstance(value, dict) or "type" not in value:
            raise ScenarioError(
                f"{source}: step {index} {action} must be a mapping containing type"
            )
    capture = raw.get("capture") or {}
    if capture and action != "expect":
        raise ScenarioError(f"{source}: step {index} capture is only valid on expect")
    if not isinstance(capture, dict):
        raise ScenarioError(f"{source}: step {index} capture must be a mapping")
    unknown = set(raw) - {"actor", "timeout_ms", "window_ms", "capture", "note", action}
    if unknown:
        raise ScenarioError(f"{source}: step {index} has unknown keys {sorted(unknown)}")
    return Step(
        index=index,
        actor=actor,
        action=action,
        value=value,
        timeout_ms=int(raw.get("timeout_ms", DEFAULT_TIMEOUT_MS)),
        window_ms=int(raw.get("window_ms", DEFAULT_WINDOW_MS)),
        capture=dict(capture),
    )


def _check_process_state(steps: tuple[Step, ...], actors: tuple[str, ...],
                         source: str) -> None:
    """A data-dir may only be copied or replaced while its client is stopped.

    Copying a live client's data-dir races its own atomic writes (REQ-PERSIST-002)
    and can capture a half-written set of files, so snapshot and restore must both
    sit between a kill and the next start. Enforced here rather than reviewed by
    eye, so no future scenario can reintroduce the race.
    """
    running = dict.fromkeys(actors, True)  # the runner launches every actor up front
    for step in steps:
        if step.action == "kill":
            if not running[step.actor]:
                raise ScenarioError(
                    f"{source}: step {step.index} kills {step.actor}, which is "
                    f"already stopped"
                )
            running[step.actor] = False
        elif step.action == "start":
            if running[step.actor]:
                raise ScenarioError(
                    f"{source}: step {step.index} starts {step.actor}, which is "
                    f"already running"
                )
            running[step.actor] = True
        elif step.action in ("snapshot", "restore"):
            if running[step.actor]:
                raise ScenarioError(
                    f"{source}: step {step.index} takes a {step.action} of "
                    f"{step.actor} while its process is running; use "
                    f"kill -> {step.action} -> start"
                )
        elif running[step.actor] is False and step.action in ("command", "expect"):
            # expect_none is legitimate on a stopped client; the others are not.
            raise ScenarioError(
                f"{source}: step {step.index} is a {step.action} for {step.actor}, "
                f"whose process is stopped"
            )


def load(path: Path) -> Scenario:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    source = path.name
    if not isinstance(raw, dict):
        raise ScenarioError(f"{source}: top level is not a mapping")
    for required in ("name", "actors", "steps"):
        if required not in raw:
            raise ScenarioError(f"{source}: missing {required}")
    if raw["name"] != path.stem:
        raise ScenarioError(f"{source}: name is {raw['name']!r}, expected {path.stem!r}")
    actors = tuple(raw["actors"])
    if not actors:
        raise ScenarioError(f"{source}: actors is empty")
    steps = tuple(
        _parse_step(s, i, actors, source) for i, s in enumerate(raw["steps"] or ())
    )
    if not steps:
        raise ScenarioError(f"{source}: steps is empty")
    _check_process_state(steps, actors, source)
    return Scenario(
        name=raw["name"],
        title=raw.get("title", ""),
        path=path,
        actors=actors,
        requirements=tuple(raw.get("requirements") or ()),
        steps=steps,
    )


def load_all(only: list[str] | None = None) -> list[Scenario]:
    paths = sorted(SCENARIOS_DIR.glob("*.yaml"))
    if only:
        wanted = set(only)
        paths = [p for p in paths if p.stem in wanted]
        missing = wanted - {p.stem for p in paths}
        if missing:
            raise ScenarioError(f"no such scenario: {', '.join(sorted(missing))}")
    if not paths:
        raise ScenarioError(f"no scenarios found in {SCENARIOS_DIR}")
    return [load(p) for p in paths]
