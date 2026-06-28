"""Tests for the create / join onboarding flow (grill-driven):
create a new org, join an existing one and actually pull its brain."""
import sys, pathlib, subprocess
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from motherflame import core, cli


def _isolate(tmp_path, monkeypatch):
    """Point core's config/brain at a temp dir so tests don't touch real state."""
    monkeypatch.setattr(core, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(core, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(core, "BRAIN_FILE", tmp_path / "brain.json")


def test_create_sets_org_and_key(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    core.cmd_create("Acme")
    cfg = core.load_config()
    assert cfg["org_name"] == "Acme"
    assert cfg["flame_key"].startswith("mf_acme_")
    assert cfg["members"] == 1


def test_create_with_remote(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    core.cmd_create("Acme", remote="/tmp/x.git")
    assert core.load_config()["sync_remote"] == "/tmp/x.git"


def test_join_sets_key_and_org(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    core.cmd_join("mf_acme_deadbeef")           # no remote → warns, sets key
    cfg = core.load_config()
    assert cfg["flame_key"] == "mf_acme_deadbeef"
    assert cfg["org_name"] == "Acme"


def test_join_without_key_is_safe(tmp_path, monkeypatch, capsys):
    _isolate(tmp_path, monkeypatch)
    core.cmd_join(None)                          # must not crash
    assert "Need a Flame Key" in capsys.readouterr().out


def test_join_end_to_end_pulls_brain(tmp_path, monkeypatch):
    """The bug grill found: join must PULL the team's brain, not leave it empty."""
    import os
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    key = "mf_acme_feedface"

    # User A: create, add a fact, push
    a_dir = tmp_path / "A"; a_dir.mkdir()
    _isolate(a_dir, monkeypatch)
    core.cmd_create("Acme", remote=str(remote))
    # overwrite the random key so B can join with a known one
    cfg = core.load_config(); cfg["flame_key"] = cfg["api_key"] = key; core.save_config(cfg)
    from motherflame import conflicts
    brain = core.load_brain()
    conflicts.add_claim(brain, "Product", "pricing", "$48k", source="chat", confidence=1.0)
    conflicts.rebuild_canonical(brain); core.save_brain(brain)
    core.cmd_push()

    # User B: fresh, join with A's key + same remote
    b_dir = tmp_path / "B"; b_dir.mkdir()
    _isolate(b_dir, monkeypatch)
    core.cmd_join(key, remote=str(remote))
    b_brain = core.load_brain()
    assert any(i["key"] == "pricing" and "$48k" in i["value"] for i in b_brain["items"]), \
        "join did not pull the team's brain"


def test_cli_dispatch_has_create_join():
    import inspect
    src = inspect.getsource(cli.main)
    assert 'cmd == "create"' in src
    assert 'cmd == "join"' in src


def test_pop_flag():
    val, rest = cli._pop_flag(["acme", "--remote", "git@x"], "--remote")
    assert val == "git@x" and rest == ["acme"]
    val, rest = cli._pop_flag(["acme"], "--remote")
    assert val is None and rest == ["acme"]
