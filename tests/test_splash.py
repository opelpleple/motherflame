"""Tests for the splash screen renderer."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from motherflame import splash


def _strip(s):
    return splash._strip_ansi(s)


def test_splash_renders_cold_state():
    out = _strip(splash.render_splash({}, {}))
    assert "MOTHERFLAME" not in out          # figlet is ascii-art, not the literal word
    assert "Your Org Brain" in out
    assert "not connected" in out            # AI + brain unlit
    assert "motherflame setup" in out        # next-step hint


def test_splash_renders_full_state():
    cfg = {"provider": "openai", "model": "gpt-4o-mini", "agent_api_key": "sk-x",
           "flame_key": "mf_acme_1", "org_name": "Acme", "sync_remote": "/tmp/r.git",
           "members": 3}
    brain = {"org_name": "Acme", "items": [{"key": "pricing", "value": "$48k"}]}
    out = _strip(splash.render_splash(cfg, brain))
    assert "Acme" in out
    assert "openai/gpt-4o-mini" in out
    assert "1 fact" in out and "1 facts" not in out   # singular grammar
    assert "synced" in out
    assert "motherflame chat" in out                   # ready hint
    assert "mf_acme_1" in out                           # flame key shown


def test_splash_box_lines_aligned():
    """Every box line should end with the right border at the same column."""
    cfg = {"provider": "openai", "agent_api_key": "sk-x", "model": "m",
           "flame_key": "mf_x_1", "org_name": "X"}
    brain = {"items": [{"key": "a", "value": "b"}]}
    raw = splash.render_splash(cfg, brain)
    box_lines = [l for l in raw.split("\n") if "│" in l]
    widths = {len(_strip(l)) for l in box_lines}
    assert len(widths) == 1, f"box lines misaligned: {widths}"


def test_splash_pending_count():
    cfg = {"flame_key": "mf_x_1", "org_name": "X"}
    brain = {"items": [{"key": "a", "value": "b"}], "pending": [{"key": "c"}]}
    out = _strip(splash.render_splash(cfg, brain))
    assert "1 pending" in out
