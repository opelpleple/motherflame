"""Tests for web research onboarding (research.py + llm_research_extract)."""
import sys, pathlib, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from motherflame import research, agent, cli, core


def test_discover_pages_same_domain(monkeypatch):
    html = '''
      <a href="/about">About</a>
      <a href="/pricing">Pricing</a>
      <a href="https://other.com/spam">External</a>
      <a href="/blog/post">Blog</a>
      <a href="/product/x">Product</a>
    '''
    monkeypatch.setattr(research, "_fetch_raw_html", lambda *a, **k: html)
    pages = research.discover_pages("https://acme.com", limit=6)
    # homepage first, then same-domain hint pages; external dropped
    assert pages[0] == "https://acme.com"
    joined = " ".join(pages)
    assert "acme.com/about" in joined
    assert "acme.com/pricing" in joined
    assert "other.com" not in joined


def test_discover_pages_handles_fetch_failure(monkeypatch):
    def boom(*a, **k): raise OSError("no net")
    monkeypatch.setattr(research, "_fetch_raw_html", boom)
    pages = research.discover_pages("https://acme.com")
    assert pages == ["https://acme.com"]      # degrades to just the homepage


def test_gather_collects_text(monkeypatch):
    monkeypatch.setattr(research, "discover_pages",
                        lambda u, **k: ["https://acme.com", "https://acme.com/about"])
    monkeypatch.setattr(research, "fetch_url",
                        lambda u, **k: "Acme builds trust software for fintech. " * 5)
    out = research.gather("https://acme.com")
    assert len(out) == 2
    assert all(len(v) > 80 for v in out.values())


def test_research_extract_returns_concrete_facts(monkeypatch):
    payload = json.dumps({"items": [
        {"category": "Product", "key": "pricing_tiers",
         "value": "Listing plans $18k / $48k / $100k+ per year", "confidence": 0.8},
    ]})
    monkeypatch.setattr(agent, "call_llm", lambda cfg, system, user: payload)
    facts = agent.llm_research_extract({"provider": "openai", "agent_api_key": "x"},
                                       "some website text", "https://acme.com")
    assert len(facts) == 1
    assert facts[0]["key"] == "pricing_tiers"
    assert "$18k" in facts[0]["value"]
    assert facts[0]["via"] == "research"
    assert facts[0]["source"] == "https://acme.com"


def test_research_extract_bad_json_is_safe(monkeypatch):
    monkeypatch.setattr(agent, "call_llm", lambda *a, **k: "not json at all")
    assert agent.llm_research_extract({"provider": "openai", "agent_api_key": "x"},
                                      "text", "https://acme.com") == []


def test_research_wired_in_cli():
    import inspect
    assert 'cmd == "research"' in inspect.getsource(cli.main)
    assert callable(core.cmd_research)
