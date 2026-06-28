"""Tests for the team-synced layer: remote health check, team dashboard,
invite flow, and doctor's deep team check."""
import sys, pathlib, subprocess
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from motherflame import core, sync, cli


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(core, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(core, "BRAIN_FILE", tmp_path / "brain.json")


# ── remote health check ──────────────────────────────────────────────────────

def test_check_remote_empty_string():
    r = sync.check_remote("")
    assert r["ok"] is False and r["status"] == "invalid"


def test_check_remote_reachable_bare_repo(tmp_path):
    remote = tmp_path / "r.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    r = sync.check_remote(str(remote))
    assert r["ok"] is True
    assert r["status"] in ("empty", "reachable")     # bare repo, no commits → empty


def test_check_remote_not_found(tmp_path):
    r = sync.check_remote(str(tmp_path / "does-not-exist.git"))
    assert r["ok"] is False
    # git's wording for a missing local repo varies; any failure status is fine
    assert r["status"] in ("not_found", "no_network", "auth_failed", "invalid")


# ── team dashboard ───────────────────────────────────────────────────────────

def test_team_no_brain(tmp_path, monkeypatch, capsys):
    _isolate(tmp_path, monkeypatch)
    core.cmd_team()
    out = capsys.readouterr().out
    assert "No Org Brain yet" in out
    assert "motherflame create" in out


def test_team_dashboard_shows_invite(tmp_path, monkeypatch, capsys):
    _isolate(tmp_path, monkeypatch)
    remote = tmp_path / "r.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    core.cmd_create("Acme", remote=str(remote))
    capsys.readouterr()                              # clear create output
    core.cmd_team()
    out = capsys.readouterr().out
    assert "Team Brain" in out
    assert "Invite a teammate" in out
    assert "motherflame join" in out
    assert "reachable" in out or "empty" in out      # live health badge


def test_team_solo_no_remote(tmp_path, monkeypatch, capsys):
    _isolate(tmp_path, monkeypatch)
    core.cmd_create("Solo")                          # no remote
    capsys.readouterr()
    core.cmd_team()
    out = capsys.readouterr().out
    assert "solo mode" in out


# ── invite flow in create ────────────────────────────────────────────────────

def test_create_with_remote_shows_invite(tmp_path, monkeypatch, capsys):
    _isolate(tmp_path, monkeypatch)
    remote = tmp_path / "r.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    core.cmd_create("Acme", remote=str(remote))
    out = capsys.readouterr().out
    assert "Invite your team" in out
    assert "motherflame join" in out


# ── doctor deep team check ───────────────────────────────────────────────────

def test_doctor_solo_can_be_fully_lit(tmp_path, monkeypatch, capsys):
    """Solo (no remote) is a valid complete state — team-sync counts as ok."""
    _isolate(tmp_path, monkeypatch)
    cfg = core.load_config()
    cfg.update(provider="openai", model="gpt-4o-mini", agent_api_key="sk-x",
               flame_key="mf_x_1", org_name="X")
    core.save_config(cfg)
    from motherflame import conflicts
    brain = core.load_brain()
    conflicts.add_claim(brain, "P", "pricing", "$48k", source="chat", confidence=1.0)
    conflicts.rebuild_canonical(brain); core.save_brain(brain)
    core.cmd_doctor()
    assert "Fully lit" in capsys.readouterr().out


def test_team_wired_in_cli():
    import inspect
    assert 'cmd == "team"' in inspect.getsource(cli.main)
