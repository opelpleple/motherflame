"""Tests for the doctor onboarding dashboard."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from motherflame import core, cli


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(core, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(core, "BRAIN_FILE", tmp_path / "brain.json")


def test_doctor_cold_start(tmp_path, monkeypatch, capsys):
    _isolate(tmp_path, monkeypatch)
    core.cmd_doctor()
    out = capsys.readouterr().out
    assert "Motherflame Doctor" in out
    assert "Cold start" in out
    assert "motherflame setup" in out          # hint shown
    assert "20%" in out                          # only encryption lit (1/5)


def test_doctor_fully_lit(tmp_path, monkeypatch, capsys):
    _isolate(tmp_path, monkeypatch)
    # configure everything
    cfg = core.load_config()
    cfg.update(provider="openai", model="gpt-4o-mini", agent_api_key="sk-x",
               flame_key="mf_acme_1", org_name="Acme", sync_remote="/tmp/r.git")
    core.save_config(cfg)
    from motherflame import conflicts
    brain = core.load_brain()
    conflicts.add_claim(brain, "P", "pricing", "$48k", source="chat", confidence=1.0)
    conflicts.rebuild_canonical(brain)
    core.save_brain(brain)

    core.cmd_doctor()
    out = capsys.readouterr().out
    assert "100%" in out
    assert "Fully lit" in out


def test_doctor_partial_shows_next(tmp_path, monkeypatch, capsys):
    _isolate(tmp_path, monkeypatch)
    cfg = core.load_config()
    cfg.update(provider="openai", agent_api_key="sk-x", flame_key="mf_x_1", org_name="X")
    core.save_config(cfg)
    core.cmd_doctor()
    out = capsys.readouterr().out
    assert "Almost there" in out
    assert "motherflame start" in out            # next unlit hint


def test_doctor_surfaces_pending_and_contested(tmp_path, monkeypatch, capsys):
    _isolate(tmp_path, monkeypatch)
    cfg = core.load_config()
    cfg.update(provider="openai", agent_api_key="sk-x", flame_key="mf_x_1", org_name="X")
    core.save_config(cfg)
    from motherflame import conflicts
    brain = core.load_brain()
    conflicts.ensure_layers(brain)
    conflicts.stage_or_add(brain, "P", "pricing", "$48k", source="doc.md", review=True)
    core.save_brain(brain)
    core.cmd_doctor()
    out = capsys.readouterr().out
    assert "awaiting review" in out


def test_doctor_wired_in_cli():
    import inspect
    assert 'cmd == "doctor"' in inspect.getsource(cli.main)
