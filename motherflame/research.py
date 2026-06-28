"""
Motherflame Web Research — bootstrap an Org Brain from a company website.

Onboarding by typing facts is shallow and tedious ("pricing: subscription").
Far better: point Motherflame at your website, let the LLM read the key pages and
propose concrete facts, then have a human confirm them. This module does the
fetching + page discovery; the LLM extraction prompt and the confirm UI live in
agent.py / core.py.

Pure stdlib (urllib + regex) — no third-party scraper, no external service.
"""
import re
import urllib.request
import urllib.parse
from html.parser import HTMLParser

_UA = "Mozilla/5.0 (compatible; MotherflameBot/1.0; +https://github.com/opelpleple/motherflame)"

# Pages worth reading on a typical company site, by URL hint.
_PAGE_HINTS = (
    "about", "company", "team", "pricing", "price", "plans", "product",
    "products", "features", "solution", "services", "how-it-works", "mission",
    "customers", "who-we-serve", "use-cases", "faq",
)


def fetch_url(url: str, timeout: int = 15, max_bytes: int = 600_000) -> str:
    """Fetch a URL and return plain text (HTML stripped). Raises on failure."""
    from motherflame.core import _extract_text_from_html
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(max_bytes).decode("utf-8", errors="ignore")
    return _extract_text_from_html(raw)


def _fetch_raw_html(url: str, timeout: int = 15, max_bytes: int = 600_000) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(max_bytes).decode("utf-8", errors="ignore")


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for k, v in attrs:
                if k == "href" and v:
                    self.hrefs.append(v)


def discover_pages(home_url: str, limit: int = 6, timeout: int = 15) -> list:
    """From a homepage, find a handful of high-signal same-domain pages
    (about / pricing / product / team …). Returns an ordered, de-duped list of
    absolute URLs including the homepage itself."""
    if not home_url.startswith(("http://", "https://")):
        home_url = "https://" + home_url
    try:
        html = _fetch_raw_html(home_url, timeout=timeout)
    except Exception:
        return [home_url]

    base = urllib.parse.urlparse(home_url)
    host = base.netloc
    p = _LinkParser()
    try:
        p.feed(html)
    except Exception:
        pass

    scored = {}
    for href in p.hrefs:
        absu = urllib.parse.urljoin(home_url, href.split("#")[0])
        u = urllib.parse.urlparse(absu)
        if u.scheme not in ("http", "https"):
            continue
        if u.netloc != host:                       # same domain only
            continue
        path = u.path.lower().rstrip("/")
        if not path or path == base.path.rstrip("/"):
            continue
        # score by how many page hints the path matches
        score = sum(1 for h in _PAGE_HINTS if h in path)
        if score == 0:
            continue
        clean = f"{u.scheme}://{u.netloc}{u.path}"
        scored[clean] = max(scored.get(clean, 0), score)

    ranked = [home_url] + [u for u, _ in
                           sorted(scored.items(), key=lambda kv: -kv[1])]
    # de-dupe preserving order
    seen, out = set(), []
    for u in ranked:
        key = u.rstrip("/")
        if key not in seen:
            seen.add(key)
            out.append(u)
    return out[:limit]


def gather(home_url: str, max_pages: int = 5, timeout: int = 15) -> dict:
    """Fetch the homepage + discovered pages. Returns
    {url: text} for every page that fetched successfully."""
    pages = discover_pages(home_url, limit=max_pages, timeout=timeout)
    out = {}
    for u in pages:
        try:
            text = fetch_url(u, timeout=timeout)
            if text and len(text.strip()) > 80:
                out[u] = text
        except Exception:
            continue
    return out
