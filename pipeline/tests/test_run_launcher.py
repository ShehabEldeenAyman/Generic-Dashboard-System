"""Tests for run.py, the one-command launcher."""

import json
import os
import time

import pytest

import run


class Completed:
    def __init__(self, returncode=0):
        self.returncode = returncode


def test_missing_python_packages_stop_the_launcher_with_instructions(monkeypatch):
    monkeypatch.setattr(run.importlib.util, "find_spec", lambda name: None if name == "pyshacl" else object())
    with pytest.raises(SystemExit) as stopped:
        run.check_backend_dependencies()
    assert "pyshacl" in str(stopped.value)
    assert "pip install -r requirements.txt" in str(stopped.value)


def test_missing_npm_stops_the_launcher(monkeypatch):
    monkeypatch.setattr(run.shutil, "which", lambda name: None)
    with pytest.raises(SystemExit, match="npm was not found"):
        run.npm()


def test_frontend_rebuilds_only_when_sources_are_newer(tmp_path, monkeypatch):
    frontend = tmp_path / "frontend"
    (frontend / "src").mkdir(parents=True)
    (frontend / "dist").mkdir()
    source = frontend / "src" / "App.jsx"
    source.write_text("old", encoding="utf-8")
    monkeypatch.setattr(run, "FRONTEND", frontend)
    monkeypatch.setattr(run, "DIST_INDEX", frontend / "dist" / "index.html")

    assert run.frontend_is_stale()  # never built

    run.DIST_INDEX.write_text("<html>", encoding="utf-8")
    past = time.time() - 60
    os.utime(source, (past, past))
    assert not run.frontend_is_stale()

    source.write_text("new", encoding="utf-8")
    assert run.frontend_is_stale()


def test_build_is_skipped_when_up_to_date_and_forced_with_rebuild(monkeypatch):
    commands = []
    monkeypatch.setattr(run, "frontend_is_stale", lambda: False)
    monkeypatch.setattr(run, "ensure_frontend_dependencies", lambda: None)
    monkeypatch.setattr(run, "npm", lambda: "npm")
    monkeypatch.setattr(run.subprocess, "run", lambda command, **kwargs: commands.append(command) or Completed())

    run.build_frontend(force=False)
    assert commands == []
    run.build_frontend(force=True)
    assert commands == [["npm", "run", "build"]]


@pytest.fixture
def reasoning_package(tmp_path, monkeypatch):
    folder = tmp_path / "reasoning"
    folder.mkdir()
    (folder / "package.json").write_text(json.dumps({"dependencies": {"eyereasoner": "21.1.28"}}), encoding="utf-8")
    (folder / "package-lock.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(run, "REASONING", folder)
    monkeypatch.delenv("EYE_COMMAND", raising=False)
    calls = []
    monkeypatch.setattr(run.subprocess, "run", lambda command, **kwargs: calls.append((command, kwargs.get("cwd"))) or Completed())
    return folder, calls


def install(folder, version):
    package = folder / "node_modules" / "eyereasoner"
    package.mkdir(parents=True, exist_ok=True)
    (package / "package.json").write_text(json.dumps({"version": version}), encoding="utf-8")


def test_reasoner_is_not_installed_when_native_eye_is_available(reasoning_package, monkeypatch):
    _folder, calls = reasoning_package
    monkeypatch.setattr(run.shutil, "which", lambda name: "/usr/local/bin/eye" if name == "eye" else "/usr/bin/npm")
    run.ensure_reasoner()
    monkeypatch.setattr(run.shutil, "which", lambda name: "/usr/bin/npm")
    monkeypatch.setenv("EYE_COMMAND", "/opt/eye/bin/eye")
    run.ensure_reasoner()
    assert calls == []


def test_reasoner_is_installed_when_missing_or_outdated(reasoning_package, monkeypatch):
    folder, calls = reasoning_package
    monkeypatch.setattr(run.shutil, "which", lambda name: None if name == "eye" else "/usr/bin/npm")

    run.ensure_reasoner()  # missing
    install(folder, "21.1.27")
    run.ensure_reasoner()  # outdated
    install(folder, "21.1.28")
    run.ensure_reasoner()  # up to date

    assert calls == [
        (["/usr/bin/npm", "ci", "--no-audit", "--no-fund"], folder),
        (["/usr/bin/npm", "ci", "--no-audit", "--no-fund"], folder),
    ]


def test_reasoner_install_explains_a_missing_npm(reasoning_package, monkeypatch, capsys):
    _folder, calls = reasoning_package
    monkeypatch.setattr(run.shutil, "which", lambda name: None)
    run.ensure_reasoner()
    assert calls == []
    assert "EYE reasoning is unavailable" in capsys.readouterr().out


def test_uvicorn_command_options():
    command = run.uvicorn_command("0.0.0.0", 9000, reload=True)
    assert command[1:] == ["-m", "uvicorn", "pipeline.playground_server:app", "--host", "0.0.0.0", "--port", "9000", "--reload"]
    assert "--reload" not in run.uvicorn_command("127.0.0.1", 8000, reload=False)


def test_main_builds_then_serves(monkeypatch):
    steps = []
    monkeypatch.setattr(run, "check_backend_dependencies", lambda: steps.append("check"))
    monkeypatch.setattr(run, "ensure_reasoner", lambda: steps.append("reasoner"))
    monkeypatch.setattr(run, "build_frontend", lambda force: steps.append(f"build force={force}"))
    monkeypatch.setattr(run.subprocess, "run", lambda command, cwd: steps.append(command[-4:]) or Completed(0))
    monkeypatch.setattr(run.sys, "argv", ["run.py", "--rebuild", "--port", "9100"])

    assert run.main() == 0
    assert steps == ["check", "reasoner", "build force=True", ["--host", "127.0.0.1", "--port", "9100"]]


def test_dev_mode_runs_backend_and_vite_and_points_the_proxy_at_the_backend(monkeypatch):
    started = []
    monkeypatch.setattr(run, "check_backend_dependencies", lambda: None)
    monkeypatch.setattr(run, "ensure_reasoner", lambda: None)
    monkeypatch.setattr(run, "ensure_frontend_dependencies", lambda: None)
    monkeypatch.setattr(run, "npm", lambda: "npm")
    monkeypatch.setattr(run, "run_together", lambda commands: started.extend(commands) or 0)
    monkeypatch.setattr(run.sys, "argv", ["run.py", "--dev", "--host", "0.0.0.0", "--port", "8123"])
    monkeypatch.setenv("PIPELINE_API_URL", "restored after the test")

    assert run.main() == 0
    assert started[0][0][-1] == "--reload"
    assert started[1] == (["npm", "run", "dev"], run.FRONTEND)
    assert os.environ["PIPELINE_API_URL"] == "http://127.0.0.1:8123"
