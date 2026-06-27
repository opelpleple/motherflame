"""
Motherflame Connectors — pluggable sources of org context.

The brain is only as good as its coverage. Local files are one source; real org
knowledge also lives in Slack, Notion, Google Drive, Jira, email, wikis. Rather
than hard-code each, Motherflame defines a small connector contract: anything
that can yield (title, text, source_id) documents can feed the harvester.

This module ships the CONTRACT + a registry + a reference local-files connector.
Concrete remote connectors (Slack, Notion, …) live outside core — an org writes
or installs the ones it needs and registers them. That keeps core dependency-free
and lets coverage grow without bloating the CLI.

A connector is intentionally tiny:

    class MyConnector(BaseConnector):
        name = "my_source"
        def fetch(self): ...  # yield Document(...) items

    register(MyConnector)

The harvester treats every Document's text exactly like a local file's contents
(same extraction, redaction, claims, review queue) — so trust/temporality/PII
guarantees apply uniformly across sources.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class Document:
    """One unit of context from a connector, normalized for the harvester."""
    title: str
    text: str
    source_id: str                     # stable id, e.g. "slack:C123:ts" or a path
    category_hint: str = ""            # optional: nudge which brain category
    metadata: dict = field(default_factory=dict)   # author, url, timestamp, …


class BaseConnector:
    """Contract every connector implements. Subclass, set `name`, implement
    `fetch()` to yield Documents. Optionally override `available()` to declare
    whether the connector is configured/reachable right now."""

    name: str = "base"

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def available(self) -> bool:
        """Return True if this connector can run (creds present, reachable).
        Default True; remote connectors should check tokens/network here."""
        return True

    def fetch(self) -> Iterable[Document]:
        """Yield Document objects. Must be overridden."""
        raise NotImplementedError(f"{self.name}.fetch() not implemented")


# ── Registry ───────────────────────────────────────────────────────────────

_REGISTRY: dict[str, type[BaseConnector]] = {}


def register(connector_cls: type[BaseConnector]) -> type[BaseConnector]:
    """Register a connector class by its `name`. Usable as a decorator."""
    if not getattr(connector_cls, "name", None):
        raise ValueError("connector must define a non-empty `name`")
    _REGISTRY[connector_cls.name] = connector_cls
    return connector_cls


def available_connectors() -> list[str]:
    return sorted(_REGISTRY)


def get_connector(name: str, config: dict | None = None) -> BaseConnector:
    if name not in _REGISTRY:
        raise KeyError(f"No connector named '{name}'. Registered: {available_connectors()}")
    return _REGISTRY[name](config)


def harvest_documents(name: str, config: dict | None = None) -> list[Document]:
    """Convenience: instantiate a connector and collect its Documents.
    Returns [] (not an error) if the connector isn't available."""
    conn = get_connector(name, config)
    if not conn.available():
        return []
    return list(conn.fetch())


# ── Reference connector: local files ───────────────────────────────────────
# Proves the contract and mirrors today's behavior. Real remote connectors
# (Slack/Notion/Drive) follow this exact shape but live outside core.

@register
class LocalFilesConnector(BaseConnector):
    name = "local_files"

    def available(self) -> bool:
        from pathlib import Path
        folder = self.config.get("folder", ".")
        return Path(folder).expanduser().exists()

    def fetch(self) -> Iterable[Document]:
        from pathlib import Path
        folder = Path(self.config.get("folder", ".")).expanduser()
        globs = self.config.get("globs", ["*.md", "*.txt"])
        for pattern in globs:
            for path in folder.rglob(pattern):
                if not path.is_file():
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                yield Document(title=path.name, text=text, source_id=str(path))
