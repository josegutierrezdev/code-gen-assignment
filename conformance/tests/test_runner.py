"""HAND-WRITTEN, NOT generated. See conformance/README.md.

Tests of the runner itself, driven against the mock client fixture so the harness
can be trusted before any real client exists.
"""

from __future__ import annotations

import os
import sys

import pytest

from conformance import manifest as manifest_mod
from conformance import scenario as scenario_mod
from conformance.clientproc import Event
from conformance.runner import RUNS_DIR, ScenarioRun, assignments, matches, substitute
from conformance.scenario import Scenario, Step

MOCK = "mock"


# -- manifests -------------------------------------------------------------------


def test_real_platform_manifests_load_and_resolve():
    assert manifest_mod.available() == ["kotlin", "python"]
    for name in manifest_mod.available():
        mf = manifest_mod.load(name)
        assert mf.name == name
        assert mf.run_argv, "run_cmd must resolve to a non-empty argv"
        assert mf.spec_files, "spec_files must list the generator inputs"
        assert mf.cwd.is_dir(), f"{name}: out_dir {mf.out_dir} must exist"


def test_python_manifest_resolves_interpreter_to_this_one():
    """A bare `python`/`python3` is replaced by the running interpreter, so a
    virtualenv or a host without that name on PATH still works."""
    mf = manifest_mod.load("python")
    assert mf.run_argv[0] == sys.executable
    assert mf.run_argv[1:] == ("-m", "client")


def test_kotlin_manifest_picks_the_os_variant():
    mf = manifest_mod.load("kotlin")
    launcher = mf.run_argv[0]
    if os.name == "nt":
        assert launcher.endswith("client.bat")
    else:
        assert launcher.endswith("bin/client")


def test_unknown_platform_is_reported_clearly():
    with pytest.raises(manifest_mod.ManifestError) as exc:
        manifest_mod.load("haskell")
    assert "haskell" in str(exc.value) and "kotlin" in str(exc.value)


# -- scenario loading ------------------------------------------------------------


def test_every_scenario_parses_and_is_role_neutral():
    scenarios = scenario_mod.load_all()
    assert {s.name for s in scenarios} == {
        "alice-bob-offline",
        "duplicate-resend",
        "restart-persistence",
        "first-launch-identity",
    }
    for s in scenarios:
        assert s.requirements, f"{s.name}: should cite the requirement IDs it covers"
        for step in s.steps:
            assert step.actor in s.actors
            # A scenario must never name a platform, path, or port.
            rendered = str(step.value).lower()
            for leak in ("kotlin", "python", "gradle", "ws://", "localhost", "127.0.0.1"):
                assert leak not in rendered, f"{s.name} step {step.index} leaks {leak!r}"


def test_bad_scenario_is_rejected(tmp_path):
    path = tmp_path / "broken.yaml"
    path.write_text(
        "name: broken\nactors: [alice]\nsteps:\n  - {actor: alice, command: x, expect: {type: y}}\n",
        encoding="utf-8",
    )
    with pytest.raises(scenario_mod.ScenarioError) as exc:
        scenario_mod.load(path)
    assert "exactly one action" in str(exc.value)


def test_scenario_naming_a_missing_actor_is_rejected(tmp_path):
    path = tmp_path / "ghost.yaml"
    path.write_text(
        "name: ghost\nactors: [alice]\nsteps:\n  - {actor: bob, command: quit}\n",
        encoding="utf-8",
    )
    with pytest.raises(scenario_mod.ScenarioError) as exc:
        scenario_mod.load(path)
    assert "not in actors" in str(exc.value)


# -- matching --------------------------------------------------------------------


def test_match_compares_listed_fields_only():
    event = Event({"type": "queued", "id": "abc", "to": "bob", "text": "hi"})
    assert matches(event, {"type": "queued", "to": "bob"}, {})
    assert not matches(event, {"type": "queued", "to": "carol"}, {})
    # REQ-COMPARE-002: an unlisted field never fails a match
    assert matches(event, {"type": "queued"}, {})


def test_match_is_case_sensitive():
    """REQ-COMPARE-004."""
    event = Event({"type": "state", "from": "SYNCING", "to": "ONLINE"})
    assert matches(event, {"type": "state", "to": "ONLINE"}, {})
    assert not matches(event, {"type": "state", "to": "online"}, {})


def test_captured_ids_correlate_across_clients():
    """REQ-COMPARE-008."""
    bindings = {"m1": "7b1f9a3c"}
    assert substitute("$m1", bindings) == "7b1f9a3c"
    assert matches(Event({"type": "sent", "id": "7b1f9a3c"}), {"type": "sent", "id": "$m1"}, bindings)
    assert not matches(Event({"type": "sent", "id": "other"}), {"type": "sent", "id": "$m1"}, bindings)
    with pytest.raises(KeyError):
        substitute("$never_bound", bindings)


def test_non_json_stdout_line_never_matches():
    """REQ-STDIO-002: a stray log line on stdout must fail, not be skipped."""
    assert not matches(Event(raw="Listening on port 8765..."), {"type": "ready"}, {})


# -- assignments -----------------------------------------------------------------


def _scenario(name: str, actors: tuple[str, ...]) -> Scenario:
    return Scenario(name, "", scenario_mod.SCENARIOS_DIR / f"{name}.yaml", actors, (),
                    (Step(0, actors[0], "command", "quit"),))


def test_matrix_covers_every_combination():
    two = _scenario("two", ("alice", "bob"))
    combos = assignments(two, ["kotlin", "python"], matrix=True, roles={})
    assert combos == [
        {"alice": "kotlin", "bob": "kotlin"},
        {"alice": "kotlin", "bob": "python"},
        {"alice": "python", "bob": "kotlin"},
        {"alice": "python", "bob": "python"},
    ]


def test_matrix_dedupes_single_actor_scenarios():
    one = _scenario("one", ("alice",))
    combos = assignments(one, ["kotlin", "python"], matrix=True, roles={})
    assert combos == [{"alice": "kotlin"}, {"alice": "python"}]


def test_explicit_roles_are_honoured():
    two = _scenario("two", ("alice", "bob"))
    combos = assignments(two, ["kotlin", "python"], matrix=False,
                         roles={"alice": "kotlin", "bob": "python"})
    assert combos == [{"alice": "kotlin", "bob": "python"}]


# -- end to end against the mock client ------------------------------------------


@pytest.mark.parametrize("name", [
    "first-launch-identity",
    "restart-persistence",
    "duplicate-resend",
    "alice-bob-offline",
])
def test_scenario_passes_with_the_mock_client(name):
    """The harness proves itself: every scenario is satisfiable end to end."""
    scenario = scenario_mod.load(scenario_mod.SCENARIOS_DIR / f"{name}.yaml")
    assignment = {actor: MOCK for actor in scenario.actors}
    run = ScenarioRun(scenario, assignment, {MOCK: manifest_mod.load(MOCK)},
                      RUNS_DIR / f"selftest-{name}")
    result = run.execute()
    assert result.ok, result.detail


def test_failure_report_names_the_step_and_tails_the_events():
    """A failing expectation must print the step, what was expected, and the last
    events per client -- that report is the runner's whole diagnostic value."""
    bogus = Scenario(
        name="bogus",
        title="deliberately wrong expectation",
        path=scenario_mod.SCENARIOS_DIR / "bogus.yaml",
        actors=("alice",),
        requirements=(),
        steps=(
            Step(0, "alice", "expect", {"type": "ready", "state": "NO_IDENTITY"},
                 timeout_ms=10000),
            Step(1, "alice", "command", "login alice"),
            # wrong on purpose: logged_in carries name=alice, not name=zebra
            Step(2, "alice", "expect", {"type": "logged_in", "name": "zebra"},
                 timeout_ms=3000),
        ),
    )
    run = ScenarioRun(bogus, {"alice": MOCK}, {MOCK: manifest_mod.load(MOCK)},
                      RUNS_DIR / "selftest-bogus")
    result = run.execute()

    assert not result.ok
    detail = result.detail
    assert "step 2" in detail
    assert "logged_in" in detail and "zebra" in detail
    assert "but got" in detail
    assert "last 20 events from alice (mock" in detail
    assert '"state": "NO_IDENTITY"' in detail or "NO_IDENTITY" in detail
    assert str(run.run_dir) in detail  # points at the logs and data dirs


def test_timeout_failure_is_reported_as_a_timeout():
    waiting = Scenario(
        name="waiting",
        title="expects an event that never comes",
        path=scenario_mod.SCENARIOS_DIR / "waiting.yaml",
        actors=("alice",),
        requirements=(),
        steps=(
            Step(0, "alice", "expect", {"type": "ready"}, timeout_ms=10000),
            Step(1, "alice", "expect", {"type": "received"}, timeout_ms=700),
        ),
    )
    run = ScenarioRun(waiting, {"alice": MOCK}, {MOCK: manifest_mod.load(MOCK)},
                      RUNS_DIR / "selftest-waiting")
    result = run.execute()
    assert not result.ok
    assert "timed out after 700ms" in result.detail
    assert "step 1" in result.detail


def test_expect_none_catches_an_event_that_should_not_arrive():
    """expect_none must fail when a matching event does arrive, and must not
    consume the stream position when it passes."""
    scenario = Scenario(
        name="noisy",
        title="",
        path=scenario_mod.SCENARIOS_DIR / "noisy.yaml",
        actors=("alice",),
        requirements=(),
        steps=(
            Step(0, "alice", "expect", {"type": "ready"}, timeout_ms=10000),
            Step(1, "alice", "command", "login alice"),
            # logged_in WILL arrive, so forbidding it must fail
            Step(2, "alice", "expect_none", {"type": "logged_in"}, window_ms=1500),
        ),
    )
    run = ScenarioRun(scenario, {"alice": MOCK}, {MOCK: manifest_mod.load(MOCK)},
                      RUNS_DIR / "selftest-noisy")
    result = run.execute()
    assert not result.ok
    assert "expected NO event" in result.detail
    assert "logged_in" in result.detail


def test_dead_client_is_reported_as_stream_ended_not_a_timeout():
    """A client that died must be diagnosed as such, and fast -- not as a long
    timeout with no explanation."""
    import time

    scenario = Scenario(
        name="dead",
        title="",
        path=scenario_mod.SCENARIOS_DIR / "dead.yaml",
        actors=("alice",),
        requirements=(),
        steps=(
            Step(0, "alice", "expect", {"type": "ready"}, timeout_ms=10000),
            Step(1, "alice", "kill", True),
            Step(2, "alice", "expect", {"type": "ready"}, timeout_ms=30000),
        ),
    )
    run = ScenarioRun(scenario, {"alice": MOCK}, {MOCK: manifest_mod.load(MOCK)},
                      RUNS_DIR / "selftest-dead")
    started = time.monotonic()
    result = run.execute()
    elapsed = time.monotonic() - started

    assert not result.ok
    assert "stdout ended before" in result.detail
    assert "step 2" in result.detail
    # It must not have waited out the 30s timeout.
    assert elapsed < 20, f"took {elapsed:.1f}s; should fail as soon as stdout ends"


# -- toolchain boundary: clean_globs vs the hand-provided Gradle wrapper ----------

GRADLE_WRAPPER_FILES = [
    "clients/kotlin/gradlew",
    "clients/kotlin/gradlew.bat",
    "clients/kotlin/gradle/wrapper/gradle-wrapper.jar",
    "clients/kotlin/gradle/wrapper/gradle-wrapper.properties",
]


def test_clean_globs_never_delete_the_gradle_wrapper():
    """The wrapper is a hand-provided toolchain bootstrap: the generator cannot
    recreate it, so no clean may remove it."""
    mf = manifest_mod.load("kotlin")
    for path in GRADLE_WRAPPER_FILES:
        for pattern in mf.clean_globs:
            assert not manifest_mod.clean_glob_matches(pattern, path), (
                f"clean_glob {pattern!r} would delete {path!r}"
            )


def test_clean_globs_do_delete_generated_sources():
    """A clean has to be a real clean, or regeneration is not from scratch."""
    expected = {
        "kotlin": ["clients/kotlin/src/main/kotlin/Main.kt",
                   "clients/kotlin/build.gradle.kts",
                   "clients/kotlin/settings.gradle.kts"],
        "python": ["clients/python/client/__main__.py",
                   "clients/python/pyproject.toml"],
    }
    for platform, paths in expected.items():
        mf = manifest_mod.load(platform)
        for path in paths:
            assert any(manifest_mod.clean_glob_matches(p, path) for p in mf.clean_globs), (
                f"{platform}: no clean_glob covers generated file {path!r}"
            )


def test_gitkeep_survives_a_clean():
    for platform in ("kotlin", "python"):
        mf = manifest_mod.load(platform)
        keep = f"clients/{platform}/.gitkeep"
        assert not any(manifest_mod.clean_glob_matches(p, keep) for p in mf.clean_globs)


def test_python_build_installs_into_the_running_interpreter():
    mf = manifest_mod.load("python")
    assert mf.build_argv[0] == sys.executable
    assert mf.build_argv[1:] == ("-m", "pip", "install", "-e", ".")
    # cwd is out_dir, so "." is the generated package root
    assert mf.cwd == manifest_mod.REPO_ROOT / "clients" / "python"


# -- snapshot / restore may only touch a stopped client --------------------------


def test_scenarios_only_snapshot_or_restore_a_stopped_client():
    """Every shipped scenario satisfies kill -> snapshot|restore -> start."""
    for s in scenario_mod.load_all():
        running = dict.fromkeys(s.actors, True)
        for step in s.steps:
            if step.action == "kill":
                running[step.actor] = False
            elif step.action == "start":
                running[step.actor] = True
            elif step.action in ("snapshot", "restore"):
                assert not running[step.actor], (
                    f"{s.name} step {step.index}: {step.action} while "
                    f"{step.actor} is running"
                )


@pytest.mark.parametrize("action", ["snapshot", "restore"])
def test_scenario_is_rejected_when_it_copies_a_live_data_dir(tmp_path, action):
    path = tmp_path / "racy.yaml"
    path.write_text(
        "name: racy\nactors: [alice]\nsteps:\n"
        f"  - {{actor: alice, {action}: s1}}\n",
        encoding="utf-8",
    )
    with pytest.raises(scenario_mod.ScenarioError) as exc:
        scenario_mod.load(path)
    assert "while its process is running" in str(exc.value)
    assert f"kill -> {action} -> start" in str(exc.value)


def test_scenario_is_rejected_when_it_drives_a_stopped_client(tmp_path):
    path = tmp_path / "zombie.yaml"
    path.write_text(
        "name: zombie\nactors: [alice]\nsteps:\n"
        "  - {actor: alice, kill: true}\n"
        "  - {actor: alice, command: quit}\n",
        encoding="utf-8",
    )
    with pytest.raises(scenario_mod.ScenarioError) as exc:
        scenario_mod.load(path)
    assert "whose process is stopped" in str(exc.value)


def test_runner_refuses_to_snapshot_a_running_client(tmp_path):
    """Belt and braces: the static check is backed by a runtime guard."""
    from conformance.clientproc import ClientProcess

    client = ClientProcess("alice", manifest_mod.load(MOCK), tmp_path / "data",
                           "ws://127.0.0.1:1/ws", tmp_path)
    client.start()
    try:
        with pytest.raises(RuntimeError, match="kill before taking a snapshot"):
            client.snapshot("s1")
    finally:
        client.close()


# -- toolchain bootstrap: the Gradle wrapper must exist and survive -------------


def test_gradle_wrapper_is_present():
    """Hand-provided bootstrap: the generator cannot produce it, so it must be
    committed and present before any Kotlin generation run."""
    root = manifest_mod.REPO_ROOT
    for path in GRADLE_WRAPPER_FILES:
        assert (root / path).is_file(), f"missing toolchain bootstrap: {path}"
    jar = root / "clients/kotlin/gradle/wrapper/gradle-wrapper.jar"
    assert jar.stat().st_size > 10_000, "gradle-wrapper.jar looks truncated"
    assert (root / "clients/kotlin/TOOLCHAIN.md").is_file()


def test_wrapper_carries_no_generated_header():
    """It is hand-provided, so it must not claim to be generated."""
    root = manifest_mod.REPO_ROOT
    for name in ("gradlew", "gradlew.bat", "gradle/wrapper/gradle-wrapper.properties"):
        text = (root / "clients/kotlin" / name).read_text(
            encoding="utf-8", errors="replace"
        )
        assert "GENERATED from spec/" not in text


# -- manifest env ---------------------------------------------------------------


def test_kotlin_env_redirects_temp_off_the_system_drive():
    """TEMP is load-bearing on Windows: JDK 16+ puts the daemon's AF_UNIX socket
    file in it, so an unwritable or full temp volume breaks every Gradle build."""
    mf = manifest_mod.load("kotlin")
    if os.name != "nt":
        assert mf.env == {}
        return
    assert set(mf.env) == {"TEMP", "TMP", "GRADLE_USER_HOME"}
    for key, value in mf.env.items():
        assert manifest_mod.REPO_ROOT_PLACEHOLDER not in value, "placeholder unresolved"
        assert str(manifest_mod.REPO_ROOT) in value, f"{key} must live inside the repo"
    assert mf.env["TEMP"] == mf.env["TMP"]


def test_env_placeholder_is_resolved_not_hardcoded():
    """A manifest must not bake in one machine's absolute paths."""
    raw = (manifest_mod.PLATFORMS_DIR / "kotlin.yaml").read_text(encoding="utf-8")
    assert manifest_mod.REPO_ROOT_PLACEHOLDER in raw
    for drive in ("C:\\", "D:\\", "/home/", "/Users/"):
        assert drive not in raw, f"manifest hardcodes a host path: {drive}"


def test_env_requires_both_os_variants(tmp_path):
    bad = tmp_path / "broken.yaml"
    bad.write_text(
        "name: broken\nout_dir: .\nspec_files: []\n"
        "build_cmd: {posix: 'true', windows: 'true'}\n"
        "run_cmd: {posix: 'true', windows: 'true'}\n"
        "clean_globs: []\nenv: {windows: {A: b}}\n",
        encoding="utf-8",
    )
    import yaml as _yaml

    with pytest.raises(manifest_mod.ManifestError, match="posix:"):
        manifest_mod._build(_yaml.safe_load(bad.read_text(encoding="utf-8")), str(bad))


def test_unknown_manifest_field_is_rejected(tmp_path):
    import yaml as _yaml

    raw = _yaml.safe_load(
        (manifest_mod.PLATFORMS_DIR / "python.yaml").read_text(encoding="utf-8")
    )
    raw["typo_field"] = 1
    with pytest.raises(manifest_mod.ManifestError, match="unknown fields"):
        manifest_mod._build(raw, "test")
