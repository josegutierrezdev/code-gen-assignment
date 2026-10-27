"""HAND-WRITTEN, NOT generated. See conformance/README.md.

Loads platform manifests from platforms/<name>.yaml and resolves the posix/windows
command variants for the current OS.
"""

from __future__ import annotations

import os
import shlex
import sys
from fnmatch import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PLATFORMS_DIR = REPO_ROOT / "platforms"

# The manifests say `python3` (posix) / `python` (windows). On a machine where that
# name is missing or shadowed -- a bare Windows install, or any virtualenv -- the
# literal name is wrong, so the interpreter running the runner is used instead.
_INTERPRETER_NAMES = {"python", "python3", "py", "python.exe", "python3.exe"}

# The mock client is a fixture of the runner, not a generator target, so it is not a
# file in platforms/. It is still addressable as a platform name for self-testing.
_MOCK = {
    "name": "mock",
    "out_dir": "conformance",
    "spec_files": [],
    "build_cmd": {"posix": "python3 -c \"import mock_client\"",
                  "windows": "python -c \"import mock_client\""},
    "run_cmd": {"posix": "python3 -m mock_client", "windows": "python -m mock_client"},
    "clean_globs": ["conformance/**/__pycache__"],
}

REQUIRED_FIELDS = ("name", "out_dir", "spec_files", "build_cmd", "run_cmd", "clean_globs")
OPTIONAL_FIELDS = ("env",)

# Placeholder available in env values, so a manifest stays machine independent.
REPO_ROOT_PLACEHOLDER = "${repo_root}"


class ManifestError(RuntimeError):
    pass


@dataclass(frozen=True)
class Manifest:
    name: str
    out_dir: Path
    spec_files: tuple[str, ...]
    build_argv: tuple[str, ...]
    run_argv: tuple[str, ...]
    clean_globs: tuple[str, ...]
    # Extra environment for build_cmd and run_cmd, already resolved for this OS.
    # Merged onto the inherited environment rather than replacing it.
    env: dict[str, str] = field(default_factory=dict)

    @property
    def cwd(self) -> Path:
        """build_cmd and run_cmd both execute with cwd = out_dir."""
        return REPO_ROOT / self.out_dir


def _variant_key() -> str:
    return "windows" if os.name == "nt" else "posix"


def _split(command: str) -> tuple[str, ...]:
    # posix=False keeps Windows backslash paths intact; the quotes it leaves behind
    # are stripped by hand.
    parts = shlex.split(command, posix=os.name != "nt")
    parts = [p.strip('"') for p in parts]
    if parts and parts[0].lower() in _INTERPRETER_NAMES:
        parts[0] = sys.executable
    return tuple(parts)


def _resolve(raw: dict, field: str) -> tuple[str, ...]:
    value = raw[field]
    if not isinstance(value, dict) or {"posix", "windows"} - set(value):
        raise ManifestError(
            f"{raw.get('name')}: {field} must have both a posix: and a windows: variant"
        )
    return _split(value[_variant_key()])


def _resolve_env(raw: dict, source: str) -> dict[str, str]:
    """The optional env: block, as {posix: {...}, windows: {...}}.

    Values may use ${repo_root}, which keeps a manifest portable instead of
    baking in one machine's absolute paths.
    """
    value = raw.get("env")
    if value is None:
        return {}
    if not isinstance(value, dict) or {"posix", "windows"} - set(value):
        raise ManifestError(
            f"{source}: env must have both a posix: and a windows: variant"
        )
    chosen = value[_variant_key()] or {}
    if not isinstance(chosen, dict):
        raise ManifestError(f"{source}: env.{_variant_key()} must be a mapping")
    resolved = {}
    for key, raw_value in chosen.items():
        if not isinstance(key, str) or not isinstance(raw_value, str):
            raise ManifestError(f"{source}: env entries must be string to string")
        resolved[key] = raw_value.replace(REPO_ROOT_PLACEHOLDER, str(REPO_ROOT))
    return resolved


def _absolutise(argv: tuple[str, ...], cwd: Path) -> tuple[str, ...]:
    """Make a relative launcher absolute against the command's own cwd.

    On Windows CreateProcess resolves a relative argv[0] against the PARENT
    process's working directory, not the `cwd` passed to Popen, so a manifest
    command like `build/install/client/bin/client` fails with ENOENT even though
    it exists inside out_dir. Resolving it here keeps manifests relative and
    readable while still launching correctly on both platforms.
    """
    if not argv:
        return argv
    candidate = cwd / argv[0]
    if not Path(argv[0]).is_absolute() and candidate.exists():
        return (str(candidate), *argv[1:])
    return argv


def _build(raw: dict, source: str) -> Manifest:
    missing = [f for f in REQUIRED_FIELDS if f not in raw]
    if missing:
        raise ManifestError(f"{source}: manifest is missing {', '.join(missing)}")
    unknown = set(raw) - set(REQUIRED_FIELDS) - set(OPTIONAL_FIELDS)
    if unknown:
        raise ManifestError(f"{source}: manifest has unknown fields {sorted(unknown)}")
    cwd = REPO_ROOT / Path(raw["out_dir"])
    return Manifest(
        name=raw["name"],
        out_dir=Path(raw["out_dir"]),
        spec_files=tuple(raw["spec_files"] or ()),
        build_argv=_absolutise(_resolve(raw, "build_cmd"), cwd),
        run_argv=_absolutise(_resolve(raw, "run_cmd"), cwd),
        clean_globs=tuple(raw["clean_globs"] or ()),
        env=_resolve_env(raw, source),
    )


def load(name: str) -> Manifest:
    if name == "mock":
        return _build(dict(_MOCK), "<built-in mock>")
    path = PLATFORMS_DIR / f"{name}.yaml"
    if not path.exists():
        raise ManifestError(
            f"no manifest for platform {name!r}: {path} does not exist "
            f"(known: {', '.join(available())})"
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw.get("name") != name:
        raise ManifestError(f"{path}: name field is {raw.get('name')!r}, expected {name!r}")
    return _build(raw, str(path))


def clean_glob_matches(pattern: str, path: str) -> bool:
    """Would deleting ``pattern`` remove ``path``?

    Patterns are repo-root-relative globs. A pattern naming a directory removes
    its whole subtree. Shared by the conformance tests and by
    scripts/clean_generated.py so the two can never disagree about what a clean
    deletes -- in particular about the hand-provided Gradle wrapper.
    """
    pattern = pattern.replace("\\", "/").rstrip("/")
    path = path.replace("\\", "/")
    if fnmatch(path, pattern):
        return True
    # a directory pattern takes its subtree with it
    return fnmatch(path, pattern + "/*") or fnmatch(path, pattern + "/**")


def available() -> list[str]:
    """Real generator target platforms, from platforms/*.yaml. Excludes mock."""
    return sorted(p.stem for p in PLATFORMS_DIR.glob("*.yaml"))
