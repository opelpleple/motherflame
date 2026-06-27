# Contributing to Motherflame

Thanks for considering a contribution. Motherflame is intentionally small,
readable, and **zero-dependency** (Python standard library only) — please keep it
that way unless there's a very strong reason.

## Dev setup

```bash
git clone https://github.com/opelpleple/motherflame
cd motherflame

# use a virtualenv (recommended)
python3 -m venv .venv
source .venv/bin/activate

pip install -e .
pip install pytest      # the only dev dependency
```

## Running tests

```bash
pytest tests/ -v
```

CI runs the same suite on Python 3.9, 3.11, and 3.12 (see
`.github/workflows/ci.yml`). PRs must keep the suite green.

## Project layout

| Module | Responsibility |
|---|---|
| `core.py` | Commands, harvest, display, the interactive REPL |
| `runtime.py` | Agentic tool-use loop + planning |
| `agent.py` | LLM calls, TTY pickers, providers |
| `conflicts.py` | Claims, resolution ladder, tombstones, canonicalization |
| `tokens.py` | Token budget manager (relevance ranking + fit) |
| `redact.py` | PII/secret redaction before LLM calls |
| `ledger.py` | Provenance + file fingerprints (freshness) |
| `sessions.py` | Persistent chat history |
| `sync.py` | Client-side encryption + local/git backends |
| `mcp_server.py` | JSON-RPC MCP server |
| `cli.py` | Entry point / command routing |

## Guidelines

- **No new runtime dependencies.** Standard library only.
- **Add a test** for any behavior change — `tests/` mirrors the modules.
- **Keep functions small and documented.** A new contributor should be able to
  read a module top-to-bottom and understand it.
- **Don't break backward compatibility** of `brain.json` without a migration
  (see `conflicts.migrate_items_to_claims` for the pattern).

## Reporting bugs

Open an issue with: what you ran, what you expected, what happened, and your
Python/OS version (`motherflame status` output helps).
