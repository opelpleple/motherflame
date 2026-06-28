"""Tests for the agent's team-sync setup tools (setup_team_sync, create_team_repo)."""
import sys, pathlib, subprocess
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from motherflame import runtime, core


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(core, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(core, "BRAIN_FILE", tmp_path / "brain.json")


def test_setup_team_sync_sets_remote(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    remote = tmp_path / "r.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    core.cmd_create("Acme")            # gives a flame key
    out = runtime._tool_setup_team_sync({}, str(remote))
    assert "Team sync set" in out
    assert core.load_config()["sync_remote"] == str(remote)


def test_setup_team_sync_empty_url(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    out = runtime._tool_setup_team_sync({}, "")
    assert "need a git remote" in out.lower()
    # nothing saved
    assert not core.load_config().get("sync_remote")


def test_setup_team_sync_unreachable_warns(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    out = runtime._tool_setup_team_sync({}, str(tmp_path / "nope.git"))
    assert "not reachable" in out.lower()
    # still saves the intent so the user can fix access then push
    assert core.load_config()["sync_remote"] == str(tmp_path / "nope.git")


def test_create_team_repo_no_gh(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    # simulate gh not installed
    monkeypatch.setattr("shutil.which", lambda x: None)
    out = runtime._tool_create_team_repo({})
    assert "gh" in out.lower() and "install" in out.lower()


def test_tools_registered():
    names = {t["name"] for t in runtime.TOOLS}
    assert "setup_team_sync" in names
    assert "create_team_repo" in names


def test_dispatch_routes_team_tools(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    # empty git_url → guidance, no crash, not mutating
    out, mutated = runtime._dispatch_tool("setup_team_sync", {"git_url": ""}, {})
    assert mutated is False
    assert "git remote" in out.lower()
