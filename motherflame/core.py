#!/usr/bin/env python3
"""Motherflame core — config, harvest, display, and command implementations."""

import json
import time
from datetime import datetime
from pathlib import Path

from motherflame import __version__

# ── Paths ──────────────────────────────────────────────────────────────────
CONFIG_DIR  = Path.home() / ".motherflame"
CONFIG_FILE = CONFIG_DIR / "config.json"
BRAIN_FILE  = CONFIG_DIR / "brain.json"

# ── ANSI styling ───────────────────────────────────────────────────────────
RESET        = "\033[0m"
BOLD         = "\033[1m"
DIM          = "\033[2m"
RED          = "\033[91m"
GREEN        = "\033[92m"
CYAN         = "\033[96m"
FLAME_ORANGE = "\033[38;5;208m"
FLAME_YELLOW = "\033[38;5;220m"
CLEAR_LINE   = "\r\033[K"

# ── Scan defaults ──────────────────────────────────────────────────────────
SCAN_PRESETS = {
    "md":   {"globs": ["*.md"],                       "label": "Markdown"},
    "html": {"globs": ["*.html", "*.htm"],            "label": "HTML"},
    "both": {"globs": ["*.md", "*.html", "*.htm"],    "label": "Markdown + HTML"},
    "txt":  {"globs": ["*.txt"],                      "label": "Plain text"},
    "pdf":  {"globs": ["*.pdf"],                      "label": "PDF"},
    "all":  {"globs": ["*.md", "*.html", "*.htm", "*.txt", "*.pdf"], "label": "All"},
}
DEFAULT_SCAN = "both"


# ──────────────────────────────────────────────
# Config helpers
# ──────────────────────────────────────────────

def _atomic_write_json(path, data):
    """Write JSON atomically: serialize to a temp file in the same dir, fsync,
    then os.replace() (atomic on POSIX). A crash mid-write can never corrupt the
    real file — you either get the old version or the new one, never a half-file.
    Also keeps a .bak of the previous good version."""
    import os, tempfile
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    # back up the last good file before replacing
    if path.exists():
        try:
            (path.with_suffix(path.suffix + ".bak")).write_text(
                path.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError:
            pass
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)   # atomic
    finally:
        if os.path.exists(tmp):
            try: os.unlink(tmp)
            except OSError: pass


def _load_json_safe(path, default):
    """Load JSON; if the file is corrupt, fall back to the .bak, else default."""
    path = Path(path)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            bak = path.with_suffix(path.suffix + ".bak")
            if bak.exists():
                try:
                    return json.loads(bak.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    pass
    return default() if callable(default) else default


# ── Cross-process locking (prevents lost updates) ──────────────────────────
# brain.json is a single file that callers load → mutate → save. If two
# processes do that concurrently (e.g. you're chatting while Claude Code writes
# via MCP), the second save clobbers the first — a lost update. A file lock
# serializes the read-modify-write window so updates compose instead of racing.

import contextlib

@contextlib.contextmanager
def brain_lock(timeout=10.0):
    """Advisory exclusive lock around a brain read-modify-write. Uses fcntl on
    POSIX; degrades to a best-effort lockfile elsewhere. Always yields."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = CONFIG_DIR / ".brain.lock"
    try:
        import fcntl, time as _t
        f = open(lock_path, "w")
        start = _t.time()
        while True:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if _t.time() - start > timeout:
                    break  # give up waiting; proceed (best-effort, no deadlock)
                _t.sleep(0.05)
        try:
            yield
        finally:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            finally:
                f.close()
    except ImportError:
        # No fcntl (e.g. Windows) — proceed without a hard lock.
        yield


def update_brain(mutator):
    """Locked read-modify-write: load the freshest brain, apply mutator(brain),
    save. Prevents lost updates when chat and MCP touch the brain concurrently.
    `mutator` may return a value, which is returned to the caller."""
    with brain_lock():
        brain = load_brain()
        result = mutator(brain)
        save_brain(brain)
        return result


def load_config():
    return _load_json_safe(CONFIG_FILE, dict)

def save_config(cfg):
    _atomic_write_json(CONFIG_FILE, cfg)

def load_brain():
    return _load_json_safe(
        BRAIN_FILE,
        lambda: {"org_name": "", "items": [], "gaps": [], "last_updated": ""})

def save_brain(brain):
    _atomic_write_json(BRAIN_FILE, brain)


# ──────────────────────────────────────────────
# Display helpers
# ──────────────────────────────────────────────

def _disp_width(s: str) -> int:
    """Visible width of a string, ignoring ANSI codes and counting wide chars (emoji/CJK) as 2."""
    import re, unicodedata
    s = re.sub(r"\033\[[0-9;]*m", "", s)  # strip ANSI
    w = 0
    for ch in s:
        if unicodedata.combining(ch):
            continue
        ea = unicodedata.east_asian_width(ch)
        if ea in ("W", "F"):
            w += 2
        elif ord(ch) >= 0x1F000:  # emoji block
            w += 2
        else:
            w += 1
    return w


def _truncate_visible(s: str, max_width: int) -> str:
    """Truncate string to max visible width, keeping ANSI codes intact and re-appending RESET."""
    import re, unicodedata
    out = []
    w = 0
    i = 0
    ansi_re = re.compile(r"\033\[[0-9;]*m")
    while i < len(s):
        m = ansi_re.match(s, i)
        if m:
            out.append(m.group())
            i = m.end()
            continue
        ch = s[i]
        if unicodedata.combining(ch):
            out.append(ch)
            i += 1
            continue
        ea = unicodedata.east_asian_width(ch)
        cw = 2 if (ea in ("W", "F") or ord(ch) >= 0x1F000) else 1
        if w + cw > max_width:
            break
        out.append(ch)
        w += cw
        i += 1
    return "".join(out) + RESET


def print_banner():
    print(f"\n{FLAME_ORANGE}{BOLD}  🔥 Motherflame{RESET}  {DIM}v{__version__}{RESET}")
    print(f"{DIM}  The Org Brain for teams that use AI{RESET}\n")


def print_status_box(cfg, brain):
    org       = brain.get("org_name") or cfg.get("org_name") or "—"
    items     = len(brain.get("items", []))
    gaps      = len(brain.get("gaps", []))
    members   = cfg.get("members", 1)
    connected = bool(cfg.get("api_key"))
    has_agent = bool(cfg.get("agent_api_key")) or cfg.get("provider") == "ollama"

    INNER = 38   # inner width between borders

    def row(label_colored: str):
        """Pad/truncate a colored content string to INNER visible width, wrap in borders."""
        w = _disp_width(label_colored)
        if w > INNER:
            label_colored = _truncate_visible(label_colored, INNER - 1) + "…"
            w = _disp_width(label_colored)
        pad = max(INNER - w, 0)
        return f"{BOLD}│{RESET} {label_colored}{' ' * pad} {BOLD}│{RESET}"

    top    = f"{BOLD}┌{'─' * (INNER + 2)}┐{RESET}"
    bottom = f"{BOLD}└{'─' * (INNER + 2)}┘{RESET}"
    blank  = row("")

    if connected:
        status = f"{GREEN}✅ Active{RESET}"
    else:
        status = f"{RED}❌ Not connected{RESET}"

    if has_agent:
        prov  = cfg.get("provider", "—")
        model = cfg.get("model", "—")
        agent = f"{GREEN}✓ {prov}/{model}{RESET}"
    else:
        agent = f"{DIM}not connected{RESET}"

    know = f"{GREEN}{items} items{RESET}"
    if gaps:
        know += f"{DIM} · {RESET}{RED}{gaps} gaps{RESET}"

    print(top)
    print(row(f"{FLAME_ORANGE}🔥 Motherflame{RESET}"))
    print(blank)
    print(row(f"Org Brain:  {CYAN}{BOLD}{org}{RESET}"))
    print(row(f"Knowledge:  {know}"))
    print(row(f"AI Agent:   {agent}"))
    print(row(f"Members:    {members} flame{'s' if members != 1 else ''}"))
    print(row(f"Status:     {status}"))
    print(blank)

    if not connected:
        hint = f"{DIM}Run: motherflame connect <key>{RESET}"
    elif not has_agent:
        hint = f"{FLAME_YELLOW}Run: motherflame setup{RESET}"
    elif items == 0:
        hint = f"{FLAME_YELLOW}Run: motherflame start{RESET}"
    else:
        hint = f"{DIM}motherflame query \"...\"{RESET}"
    print(row(hint))
    print(bottom)
    print()


def spinner(msg, seconds=1.5):
    frames = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    end = time.time() + seconds
    i = 0
    while time.time() < end:
        print(f"\r{FLAME_ORANGE}{frames[i % len(frames)]}{RESET} {msg}", end="", flush=True)
        time.sleep(0.08)
        i += 1
    print(f"{CLEAR_LINE}", end="")


def ask(prompt, default=""):
    """Prompt for input, returning `default` if the user just presses Enter."""
    suffix = f" {DIM}[{default}]{RESET}" if default else ""
    try:
        if prompt:
            val = input(f"  {prompt}{suffix}: ").strip()
        else:
            val = input(f"  {FLAME_YELLOW}›{RESET} ").strip()
    except (EOFError, KeyboardInterrupt):
        return default
    return val or default


def section(title):
    print(f"\n{BOLD}{FLAME_ORANGE}── {title} ──{RESET}\n")


# ──────────────────────────────────────────────
# Folder + scan-type pickers
# ──────────────────────────────────────────────

def _pick_folders(base=None):
    """List subdirectories of base, show file counts, let user multi-select via checkbox.
    Returns a list of absolute folder paths to harvest."""
    from motherflame.agent import checkbox_select

    base = Path(base).expanduser() if base else Path.home()

    if not base.exists() or not base.is_dir():
        print(f"  {RED}Folder not found: {base}{RESET}")
        return []

    # Gather candidate folders: the base itself + its immediate subdirs (skip hidden/system)
    SKIP = {"Library", "node_modules", ".git", "__pycache__", ".Trash", ".cache"}
    candidates = []

    candidates.append(base)
    try:
        for entry in sorted(base.iterdir()):
            if not entry.is_dir():
                continue
            if entry.name.startswith(".") or entry.name in SKIP:
                continue
            candidates.append(entry)
    except PermissionError:
        pass

    SCAN_EXTS = {".md", ".html", ".htm", ".txt", ".pdf"}
    def count_files(folder):
        try:
            return sum(1 for f in folder.rglob("*")
                       if f.is_file() and f.suffix.lower() in SCAN_EXTS)
        except (PermissionError, OSError):
            return 0

    labels = []
    valid  = []
    for folder in candidates:
        n = count_files(folder)
        if folder == base:
            name = f"{folder.name or folder}/ (this folder, top-level only)"
        else:
            name = f"{folder.name}/"
        labels.append(f"{name}  ({n} files)")
        valid.append(folder)

    if not valid:
        return []

    print(f"  {DIM}Browsing: {base}{RESET}")
    indices = checkbox_select("Select folders to harvest:", labels, defaults=[])

    return [str(valid[i]) for i in indices]


def _pick_scan_types():
    """Checkbox selector — select multiple file types at once. Returns (globs, label)."""
    from motherflame.agent import checkbox_select

    FILE_TYPES = [
        ("Markdown (.md)",          ["*.md"]),
        ("HTML (.html, .htm)",      ["*.html", "*.htm"]),
        ("Plain text (.txt)",       ["*.txt"]),
        ("PDF (.pdf)",              ["*.pdf"]),
    ]
    labels   = [ft[0] for ft in FILE_TYPES]
    defaults = [0, 1]   # md + html checked by default

    indices = checkbox_select("Select file types to scan:", labels, defaults=defaults)

    if not indices:
        indices = defaults   # nothing selected → use default

    globs = []
    chosen_labels = []
    for i in indices:
        globs.extend(FILE_TYPES[i][1])
        chosen_labels.append(FILE_TYPES[i][0])

    label = ", ".join(chosen_labels)
    print(f"  {DIM}→ {label}{RESET}\n")
    return globs, label


def _read_doc_text(file):
    """Read a file's text by type: PDF via _extract_pdf_text, HTML stripped,
    everything else as utf-8. Returns '' for unreadable/binary."""
    suf = file.suffix.lower()
    if suf == ".pdf":
        return _extract_pdf_text(file)
    raw = file.read_text(encoding="utf-8", errors="ignore")
    if suf in (".html", ".htm"):
        return _extract_text_from_html(raw)
    return raw


def _extract_pdf_text(path) -> str:
    """Extract text from a PDF. Tries the `pdftotext` CLI (poppler), then a
    pure-Python fallback. Returns '' if neither is available — never returns
    raw binary garbage (the old read_text bug)."""
    import shutil, subprocess
    # 1. pdftotext (best quality, common on Linux/mac via poppler)
    if shutil.which("pdftotext"):
        try:
            out = subprocess.run(["pdftotext", "-q", str(path), "-"],
                                 capture_output=True, text=True, timeout=30)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout
        except (subprocess.SubprocessError, OSError):
            pass
    # 2. optional pure-Python libs if the user happens to have them
    for mod, fn in (("pypdf", "PdfReader"), ("PyPDF2", "PdfReader")):
        try:
            m = __import__(mod)
            reader = getattr(m, fn)(str(path))
            return "\n".join((pg.extract_text() or "") for pg in reader.pages)
        except Exception:
            continue
    return ""   # can't read it → skip, don't emit garbage


def _extract_text_from_html(content: str) -> str:
    """Strip HTML tags → plain text for signal extraction."""
    import re
    content = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", content,
                     flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r"<[^>]+>", " ", content)
    for a, b in [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                 ("&quot;", '"'), ("&#39;", "'"), ("&nbsp;", " ")]:
        content = content.replace(a, b)
    content = re.sub(r"\s+", " ", content)
    return content


# ──────────────────────────────────────────────
# Harvest
# ──────────────────────────────────────────────

def _confirm_llm_harvest(cfg):
    """Privacy gate: harvesting with an LLM sends file *contents* to the provider.
    BYO-key does NOT make this private. Get explicit, informed consent the first
    time, and let the user fall back to local keyword extraction. Returns True to
    proceed with LLM extraction, False to use keyword-only."""
    provider = cfg.get("provider", "your AI provider")
    if cfg.get("llm_harvest_consent"):   # already agreed this machine
        print(f"  {DIM}Using AI extraction ({provider}/{cfg.get('model')}) · "
              f"PII redacted before upload{RESET}")
        return True
    print(f"\n  {BOLD}⚠️  Privacy notice{RESET}")
    print(f"  AI extraction sends the {BOLD}contents{RESET} of the files you harvest to "
          f"{BOLD}{provider}{RESET}.")
    print(f"  {DIM}• Bringing your own API key does NOT make this private — the text leaves your machine.{RESET}")
    print(f"  {DIM}• Emails / keys / cards / SSNs are masked first, but regex redaction is best-effort, NOT guaranteed.{RESET}")
    print(f"  {DIM}• Do NOT point AI harvest at folders with real customer PII or credentials.{RESET}")
    try:
        from motherflame.agent import arrow_select
        choice = arrow_select(
            "How do you want to harvest?",
            [f"Use AI extraction (send contents to {provider})",
             "Local keyword extraction only (nothing leaves my machine)",
             "Use AI, and don't ask again on this machine"],
            default=1)
    except Exception:
        return False
    if choice == 1:
        print(f"  {GREEN}✓ Keyword-only — no file contents leave your machine{RESET}")
        return False
    if choice == 2:
        cfg["llm_harvest_consent"] = True
        save_config(cfg)
    print(f"  {DIM}Proceeding with AI extraction · PII redacted before upload{RESET}")
    return True


def harvest_from_folder(folder, brain, globs=None, use_llm=False, cfg=None, changed_only=False):
    """Scan a folder for org signals and add them to the brain.
    If use_llm=True and cfg has an agent key, uses LLM extraction (high quality);
    otherwise falls back to keyword matching.
    If changed_only=True, skips files unchanged since the last harvest (freshness).
    Returns (brain, found_count)."""
    folder = Path(folder).expanduser()
    if globs is None:
        globs = ["*.md", "*.html", "*.htm"]

    files = []
    for g in globs:
        files.extend(folder.rglob(g))
    files = list(dict.fromkeys(files))  # dedupe (preserves order)

    from motherflame import ledger

    # Freshness filter — only re-process new/changed files
    if changed_only:
        before_n = len(files)
        files = ledger.changed_files(files)
        skipped = before_n - len(files)
        if skipped:
            print(f"\n  {DIM}Skipping {skipped} unchanged files (freshness){RESET}")

    if not files:
        ext_list = ", ".join(globs)
        if changed_only:
            print(f"  {DIM}No new or changed files in {folder}{RESET}")
        else:
            print(f"  {DIM}No files ({ext_list}) found in {folder}{RESET}")
        return brain, 0

    # Count by type for display
    md_count   = sum(1 for f in files if f.suffix == ".md")
    html_count = sum(1 for f in files if f.suffix in (".html", ".htm"))
    other      = len(files) - md_count - html_count
    parts = []
    if md_count:   parts.append(f"{md_count} .md")
    if html_count: parts.append(f"{html_count} .html")
    if other:      parts.append(f"{other} other")
    mode = "LLM" if use_llm else "keyword"
    print(f"\n  {DIM}Found {len(files)} files ({', '.join(parts)}) · {mode} extraction...{RESET}")

    existing_keys = {item["key"] for item in brain.get("items", [])}
    found_count = 0

    # ── LLM extraction path (high quality) ──
    if use_llm and cfg and (cfg.get("agent_api_key") or cfg.get("provider") == "ollama"):
        from motherflame.agent import llm_extract_signals
        from motherflame import conflicts, redact
        conflicts.ensure_layers(brain)
        owner = cfg.get("member_name", "")   # team-unique identity (empty if solo)
        redact_on = cfg.get("redact_pii", True)   # default ON — privacy by default
        redaction_total = {}
        failed_files = []
        # Process ALL files (no silent 30-file cap). Show progress so large
        # harvests are visibly working, not hung. A high ceiling guards against
        # runaway cost; warn instead of silently dropping the rest.
        MAX_FILES = int(cfg.get("max_harvest_files", 2000))
        total = len(files)
        if total > MAX_FILES:
            print(f"  {DIM}Note: {total} files found; processing first {MAX_FILES} "
                  f"(raise max_harvest_files to scan more){RESET}")
            files = files[:MAX_FILES]
        for i, file in enumerate(files, 1):
            if total > 20 and (i % 10 == 0 or i == total):
                print(f"\r  {DIM}Extracting… {i}/{len(files)} files, "
                      f"{found_count} facts{RESET}", end="", flush=True)
            try:
                content = _read_doc_text(file)
                if len(content.strip()) < 30:
                    continue
                # Strip PII/secrets before the content leaves the machine for the LLM
                content, _rc = redact.redact(content, enabled=redact_on)
                for lbl, n in _rc.items():
                    redaction_total[lbl] = redaction_total.get(lbl, 0) + n
                items = llm_extract_signals(cfg, content, str(file.name))
                for item in items:
                    key = item["key"]
                    # Record as a CLAIM (never clobbers — conflict manager resolves later)
                    conflicts.add_claim(brain, item["category"], key, item["value"],
                                        source=str(file.name), owner=owner,
                                        confidence=item.get("confidence", 0.85))
                    found_count += 1
                    ledger.record_fact_write(item["category"], key, item["value"],
                                             source=str(file.name), fact_id=key)
                ledger.record_file_seen(file)   # freshness fingerprint
            except Exception as e:
                failed_files.append((str(file.name), type(e).__name__))
                continue
        if total > 20:
            print()  # newline after progress line
        if redaction_total:
            print(f"  {DIM}🔒 Redacted before upload: {redact.summarize(redaction_total)}{RESET}")
        if failed_files:
            # Don't lose files silently — tell the user what didn't extract and why.
            print(f"  {FLAME_YELLOW}⚠️  {len(failed_files)} file(s) failed extraction "
                  f"(rate limit / parse / encoding):{RESET}")
            for fname, err in failed_files[:5]:
                print(f"     {DIM}• {fname} ({err}){RESET}")
            if len(failed_files) > 5:
                print(f"     {DIM}…and {len(failed_files) - 5} more. Re-run to retry.{RESET}")
        conflicts.rebuild_canonical(brain)   # recompute single source of truth
        ledger.record_scan(folder, len(files), globs, found_count)
        return brain, found_count

    # ── Keyword fallback path (no LLM / offline) ──
    signal_patterns = [
        ("Company", "company_name", ["# ", "company:", "organization:"]),
        ("Company", "what_we_do", ["we help", "we provide", "our mission"]),
        ("Product", "product_name", ["product:", "platform:", "tool:", "app:"]),
        ("Product", "pricing", ["pricing", "price", "tier", "$"]),
        ("Team", "team_size", ["team of", "people", "employees"]),
        ("Strategy", "goals", ["goal:", "objective:", "target:", "KPI:"]),
        ("Strategy", "market", ["market:", "customer:", "audience:"]),
    ]

    from motherflame import conflicts as _cf
    _cf.ensure_layers(brain)
    kw_owner = cfg.get("member_name", "") if cfg else ""
    kw_max = int(cfg.get("max_harvest_files", 2000)) if cfg else 2000
    import re as _re
    for file in files[:kw_max]:
        try:
            content = _read_doc_text(file)
            lines = content.split("\n")

            for line in lines:
                stripped = line.strip().lstrip("#").strip()
                # Noise control: a fact value is a short-ish line, not a paragraph
                # and not an empty/heading fragment.
                if not (8 <= len(stripped) <= 160):
                    continue
                line_lower = line.lower()
                for cat, key, keywords in signal_patterns:
                    if key in existing_keys:
                        continue
                    # whole-word match only (avoid 'team' matching 'teamwork')
                    if any(_re.search(r"\b" + _re.escape(kw.lower().strip()) + r"\b", line_lower)
                           for kw in keywords):
                        # keyword facts are low-confidence — they're guesses, flagged
                        # for review, and lose to any LLM/interview/owner claim
                        _cf.add_claim(brain, cat, key, stripped[:160],
                                      source=str(file.name), owner=kw_owner, confidence=0.4)
                        existing_keys.add(key)
                        found_count += 1
                        ledger.record_fact_write(cat, key, stripped[:160],
                                                 source=str(file.name), fact_id=key)
                        break
            ledger.record_file_seen(file)   # freshness fingerprint
        except Exception:
            continue

    # Record the scan event in the provenance ledger
    ledger.record_scan(folder, len(files), globs, found_count)
    _cf.rebuild_canonical(brain)   # resolve keyword claims into canonical

    return brain, found_count


INTERVIEW_QUESTIONS = [
    ("Company", "company_tagline", "What does your company do? (1 sentence)", None),
    ("Company", "target_customer", "Who are your main customers?", None),
    ("Company", "problem_solved", "What problem do you solve for them?", None),
    ("Product", "pricing_model", "How is your pricing structured? (e.g. $X/month, subscription)", None),
    ("Product", "main_product", "What is your main product/service called?", None),
    ("Team", "team_size", "How many people are on the team?", None),
    ("Team", "decision_maker", "Who decides on product? Who on finance?", None),
    ("Voice", "communication_style", "How do you talk to customers? (formal/casual/technical)", "casual"),
    ("Strategy", "current_focus", "What are you focused on right now?", None),
    ("Strategy", "avoid", "What do you NOT do / what's not your brand?", None),
]


# ──────────────────────────────────────────────
# Commands
# ──────────────────────────────────────────────

def _generate_flame_key(org_hint=""):
    """Generate a local Flame Key — no server needed. Solo/self-hosted users get
    a real key derived from a random token, so encryption works without signup."""
    import secrets
    slug = "".join(c for c in org_hint.lower() if c.isalnum()) or "org"
    return f"mf_{slug}_{secrets.token_hex(8)}"


def ensure_local_identity(cfg):
    """Make sure there's a Flame Key so the app is usable WITHOUT a server.
    If the user never ran `connect`, auto-provision a local key the first time.
    Returns cfg (saved if changed)."""
    if not cfg.get("flame_key"):
        org_hint = cfg.get("org_name", "") or cfg.get("member_name", "")
        cfg["flame_key"] = _generate_flame_key(org_hint)
        cfg["api_key"] = cfg["flame_key"]
        cfg.setdefault("org_name", "My Org")
        cfg["auto_provisioned"] = True
        save_config(cfg)
    return cfg


def cmd_connect(flame_key=None):
    """motherflame connect [key] — connect to an Org Brain via Flame Key.
    With no key, generates a local one (solo/self-hosted — no server required)."""
    cfg = load_config()
    if not flame_key:
        flame_key = _generate_flame_key(cfg.get("org_name", ""))
        print(f"{GREEN}✓ Generated a local Flame Key{RESET} {DIM}(no server needed){RESET}")
        print(f"  {BOLD}{flame_key}{RESET}")
        print(f"  {DIM}Share this key with teammates to sync the same Org Brain.{RESET}")
    cfg["api_key"]   = flame_key
    cfg["flame_key"] = flame_key
    # Derive a friendly org name from the key if none set (mf_acme_widgets → Widgets)
    if not cfg.get("org_name") or cfg.get("org_name") == "My Org":
        parts = flame_key.replace("mf_", "").split("_")
        guess = parts[0] if parts else flame_key
        cfg["org_name"] = guess.capitalize() if guess else "My Org"
    cfg.setdefault("members", 1)
    cfg["connected_at"] = datetime.now().isoformat()
    cfg.pop("auto_provisioned", None)
    save_config(cfg)

    brain = load_brain()
    if not brain.get("org_name"):
        brain["org_name"] = cfg["org_name"]
        save_brain(brain)

    print(f"{GREEN}✓ Connected to Org Brain: {BOLD}{cfg['org_name']}{RESET}")
    print(f"  {DIM}Next: {CYAN}motherflame setup{RESET}{DIM} then {CYAN}motherflame start{RESET}\n")


def cmd_status():
    """motherflame status — show connection & brain status."""
    cfg = load_config()
    brain = load_brain()
    print_banner()
    print_status_box(cfg, brain)


def cmd_brain():
    """motherflame brain — view what's in the Org Brain, grouped by category."""
    brain = load_brain()
    org = brain.get("org_name", "Org")
    items = brain.get("items", [])

    if not items:
        print(f"{RED}✗ Org Brain is empty.{RESET}")
        print(f"  Run: {CYAN}motherflame start{RESET}")
        return

    print(f"\n{FLAME_ORANGE}🔥{RESET} {BOLD}{org} — Org Brain{RESET}\n")
    order = ["Company", "Product", "Team", "Voice", "Strategy"]
    cats = {}
    for it in items:
        cats.setdefault(it["category"], []).append(it)

    for cat in order + [c for c in cats if c not in order]:
        if cat not in cats:
            continue
        print(f"  {BOLD}{cat}{RESET}")
        for it in cats[cat]:
            mark = "✅" if it.get("confidence", 1.0) >= 0.9 else "⚠️ "
            print(f"  {mark} {it['key']}: {DIM}{it['value'][:70]}{RESET}")
        print()


def cmd_help():
    print(f"""
{FLAME_ORANGE}🔥 Motherflame CLI{RESET}  {DIM}v{__version__}{RESET}

{BOLD}Setup:{RESET}
  {CYAN}motherflame setup{RESET}            Connect your AI API key (Anthropic/OpenAI/Ollama)
  {CYAN}motherflame connect <key>{RESET}    Connect to your Org Brain (Flame Key)

{BOLD}Commands:{RESET}
  {CYAN}motherflame status{RESET}           Show connection & brain status
  {CYAN}motherflame start{RESET}            Harvest org context (AI extraction + interview)
  {CYAN}motherflame brain{RESET}            View what's in your Org Brain
  {CYAN}motherflame chat{RESET}             Talk to your Org Brain agent (tool-use, persistent)
  {CYAN}motherflame query <question>{RESET} Ask your Org Brain a one-off question

{BOLD}Sync (zero-knowledge):{RESET}
  {CYAN}motherflame push{RESET}             Encrypt & sync your brain to the cloud
  {CYAN}motherflame pull{RESET}             Pull & merge teammates' context

{BOLD}Integrate:{RESET}
  {CYAN}motherflame mcp{RESET}              Run MCP server (connect Claude Code / Cursor)

{BOLD}Get started:{RESET}
  1. motherflame setup           ← connect your own AI agent
  2. motherflame connect mf_xxx  ← connect Org Brain
  3. motherflame start           ← harvest (AI-powered)
  4. motherflame                 ← chat with your agent 🔥

{DIM}Flame Key format: mf_xxxxxxxx{RESET}
""")


def cmd_start():
    """motherflame start — harvest org context (folder scan + interview)."""
    cfg = ensure_local_identity(load_config())
    brain = load_brain()
    org = brain.get("org_name") or cfg.get("org_name") or "your org"

    print_banner()
    print(f"{BOLD}{FLAME_ORANGE}🔥 Starting Motherflame Harvest{RESET}")
    print(f"{DIM}Building Org Brain for: {BOLD}{org}{RESET}\n")
    print(f"This will take ~5 minutes. Let's go.\n")

    # ── PHASE A: Folder harvest ──
    section("Phase A — Folder Harvest")
    print(f"Motherflame will scan folders and extract company info automatically.\n")

    base = ask("Browse from which directory? (Enter for home ~)", str(Path.home()))
    folders = _pick_folders(base)

    harvested_count = 0
    if folders:
        globs, scan_label = _pick_scan_types()
        # Use LLM extraction if an agent is connected (much higher quality)
        use_llm = bool(cfg.get("agent_api_key")) or cfg.get("provider") == "ollama"
        if use_llm:
            use_llm = _confirm_llm_harvest(cfg)
        for folder in folders:
            spinner(f"Scanning {Path(folder).name} ({scan_label})...", 1.0)
            brain, _ = harvest_from_folder(folder, brain, globs=globs, use_llm=use_llm, cfg=cfg)
            harvested_count = len(brain.get("items", []))
        if harvested_count > 0:
            print(f"{GREEN}✓ Found {harvested_count} org signals from {len(folders)} folder(s){RESET}")
        else:
            print(f"{DIM}  No clear signals found — will ask in the interview{RESET}")
    else:
        print(f"  {DIM}Skipped folder harvest{RESET}")

    # ── PHASE B: Gap detection + Interview ──
    section("Phase B — Gap Detection & Interview")

    existing_keys = {item["key"] for item in brain.get("items", [])}
    questions_to_ask = [q for q in INTERVIEW_QUESTIONS if q[1] not in existing_keys]

    if not questions_to_ask:
        print(f"{GREEN}✓ Org Brain is complete! No extra questions needed.{RESET}")
    else:
        print(f"Found {harvested_count} items from the folder.")
        print(f"Still missing {len(questions_to_ask)} — let me ask a few more:\n")

        from motherflame import conflicts as _cf
        _cf.ensure_layers(brain)
        for i, (cat, key, question, default) in enumerate(questions_to_ask, 1):
            print(f"  {DIM}[{i}/{len(questions_to_ask)}]{RESET} {question}")
            answer = ask("", default)
            if answer:
                # Route through the claims layer (confidence 1.0 — interview is
                # authoritative) so rebuild_canonical never drops these answers.
                _cf.add_claim(brain, cat, key, answer,
                              source="interview", owner=cfg.get("member_name", ""),
                              confidence=1.0)
                from motherflame import ledger
                ledger.record_fact_write(cat, key, answer, source="interview", fact_id=key)
            print()
        _cf.rebuild_canonical(brain)

    # ── PHASE C: Identify remaining gaps ──
    all_keys = {item["key"] for item in brain.get("items", [])}
    all_expected = {q[1] for q in INTERVIEW_QUESTIONS}
    gaps = list(all_expected - all_keys)
    brain["gaps"] = gaps
    brain["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    save_brain(brain)

    # ── Summary ──
    section("Done 🔥")
    total = len(brain["items"])
    print(f"{GREEN}✓ Org Brain created successfully!{RESET}\n")
    print(f"  📦 Knowledge items:  {BOLD}{total}{RESET}")
    print(f"  📁 From folder:      {harvested_count} items")
    print(f"  💬 From interview:   {total - harvested_count} items")
    if gaps:
        print(f"  ⚠️  Gaps remaining:  {len(gaps)} items")
    print()
    print(f"  {DIM}Run 'motherflame brain' to view everything{RESET}")
    print(f"  {DIM}Run 'motherflame start' again to update{RESET}")
    print()
    print(f"  {FLAME_ORANGE}Your org's flame is lit 🔥{RESET}\n")


def cmd_setup():
    """motherflame setup — connect your own AI agent (provider/model/key)."""
    from motherflame.agent import PROVIDERS, test_connection, arrow_select

    cfg = load_config()
    print_banner()
    print(f"{BOLD}{FLAME_ORANGE}🔗 Connect Your AI Agent{RESET}")
    print(f"{DIM}Motherflame uses your own AI key — your data never passes through our server{RESET}\n")

    keys          = list(PROVIDERS.keys())
    provider_labels = [PROVIDERS[k]["label"] for k in keys]
    current_idx   = keys.index(cfg.get("provider", "anthropic")) if cfg.get("provider") in keys else 0
    idx           = arrow_select("Select AI provider:", provider_labels, default=current_idx)
    provider_key  = keys[idx]
    provider      = PROVIDERS[provider_key]
    print(f"  {DIM}→ {provider['label']}{RESET}\n")

    if provider_key == "ollama":
        api_key = ""
        print(f"  {DIM}Ollama needs no key — make sure ollama is running{RESET}")
        print(f"  {DIM}See: https://ollama.ai{RESET}\n")
    else:
        existing = cfg.get("agent_api_key", "")
        hint     = f"[{existing[:12]}...] " if existing else ""
        print(f"  Key format: {provider['key_hint']}")
        api_key  = ask(f"API Key {hint}(Enter to keep existing)", "").strip()
        if not api_key and existing:
            api_key = existing
            print(f"  {DIM}→ Using existing key{RESET}\n")

    models        = provider["models"]
    current_model = cfg.get("model", provider["default_model"])
    default_midx  = models.index(current_model) if current_model in models else 0
    model_labels  = []
    for m in models:
        tag = " (default)" if m == provider["default_model"] else ""
        model_labels.append(f"{m}{tag}")
    midx  = arrow_select("Select model:", model_labels, default=default_midx)
    model = models[midx]
    print(f"  {DIM}→ {model}{RESET}\n")

    cfg["provider"]      = provider_key
    cfg["model"]         = model
    cfg["agent_api_key"] = api_key

    # Member identity — who am I on this team? (powers owner authority in conflicts)
    existing_member = cfg.get("member_name", "")
    member_hint = f" [{existing_member}]" if existing_member else ""
    member = ask(f"Your name (for team attribution){member_hint}", existing_member).strip()
    if member:
        cfg["member_name"] = member

    save_config(cfg)

    spinner("Testing connection...", 0.5)
    test_cfg = {"provider": provider_key, "model": model, "agent_api_key": api_key}
    ok, msg  = test_connection(test_cfg)

    if ok:
        print(f"{GREEN}✓ Agent connected! ({provider['label']} / {model}){RESET}")
        print(f"  {DIM}Response: {msg}{RESET}\n")
        print(f"  {DIM}Harvest will now use intelligent LLM extraction{RESET}")
        print(f"  {DIM}Use `motherflame query` to ask your Org Brain anything{RESET}\n")
    else:
        print(f"{RED}✗ Connection failed{RESET}")
        print(f"  {DIM}Error: {msg}{RESET}")
        print(f"  {DIM}Check your API key and try again{RESET}\n")


def cmd_query(question: str):
    """motherflame query <question> — ask your Org Brain (one-off)."""
    from motherflame.agent import query_brain

    cfg   = load_config()
    brain = load_brain()

    if not cfg.get("agent_api_key") and cfg.get("provider") != "ollama":
        print(f"{RED}✗ No AI agent connected.{RESET}")
        print(f"  Run: {CYAN}motherflame setup{RESET}")
        return

    if not brain.get("items"):
        print(f"{RED}✗ Org Brain is empty.{RESET}")
        print(f"  Run: {CYAN}motherflame start{RESET}")
        return

    org = brain.get("org_name", "Org")
    print(f"\n{FLAME_ORANGE}🔥{RESET} {BOLD}{org} Org Brain{RESET} {DIM}· {len(brain['items'])} items{RESET}")
    print(f"  {DIM}Q: {question}{RESET}\n")

    spinner("Thinking...", 0.8)
    try:
        answer = query_brain(cfg, brain, question)
        print(f"{BOLD}A:{RESET} {answer}\n")
    except Exception as e:
        print(f"{RED}✗ Error: {e}{RESET}\n")


def cmd_chat(resume=False):
    """motherflame chat — interactive agent REPL with tool-use, planning, history & provenance."""
    from motherflame.runtime import agent_turn, plan_task
    from motherflame import ledger, sessions
    from datetime import datetime as _dt

    cfg   = load_config()
    brain = load_brain()

    if not cfg.get("agent_api_key") and cfg.get("provider") != "ollama":
        print(f"{RED}✗ No AI agent connected.{RESET}")
        print(f"  Run: {CYAN}motherflame setup{RESET}")
        return

    org      = brain.get("org_name", "Org")
    provider = cfg.get("provider", "—")
    model    = cfg.get("model", "—")
    n_items  = len(brain.get("items", []))

    # ── Session setup ──
    session_id   = _dt.now().strftime("%Y%m%d-%H%M%S")
    history      = []
    facts_at_start = n_items

    # Optionally resume the most recent session's context
    if resume:
        prev = sessions.latest_session_id()
        if prev:
            data = sessions.load_session(prev)
            if data:
                # rebuild a light history from saved text (context only)
                for m in data.get("history", []):
                    history.append({"role": m["role"], "content": m["text"]})
                print(f"{DIM}Resumed session {prev} ({len(history)} messages){RESET}")

    print_banner()
    print(f"{FLAME_ORANGE}🔥{RESET} {BOLD}{org} Org Brain{RESET} {DIM}· {n_items} items{RESET}")
    print(f"{DIM}Connected: {provider}/{model}  ·  session {session_id}{RESET}")
    print(f"{DIM}Type a message, '/' for commands, or /exit to quit.{RESET}\n")

    # Registry of slash commands: (name, description)
    SLASH_COMMANDS = [
        ("plan",     "Plan a multi-step task, then optionally execute it"),
        ("harvest",  "Scan folders and add new facts to the Org Brain"),
        ("refresh",  "Re-scan only changed files (keep brain fresh)"),
        ("start",    "Run the full harvest + interview flow"),
        ("brain",    "Show everything in the Org Brain"),
        ("gaps",     "Show what info is still missing"),
        ("optimize", "Find gaps, duplicates & suggest improvements"),
        ("conflicts","Show contested facts (teammates disagree)"),
        ("resolve",  "Settle a contested fact — you pick the truth"),
        ("forget",   "Retract a fact — tombstoned so it won't return on sync"),
        ("owner",    "Assign who owns a fact/category (their claim wins)"),
        ("sources",  "Show where a fact came from (provenance)"),
        ("history",  "Show what's been scanned & sent to the Org Brain"),
        ("status",   "Show connection & brain status"),
        ("clear",    "Clear the conversation memory"),
        ("help",     "Show this command list"),
        ("exit",     "Quit the chat"),
    ]

    def show_tool(name, args, result):
        arg_str = ", ".join(f"{k}={v}" for k, v in args.items()) if args else ""
        preview = result.split("\n")[0][:60]
        print(f"  {DIM}⚙ {name}({arg_str}) → {preview}{RESET}")

    def chat_help():
        print(f"\n{BOLD}In-chat commands:{RESET}")
        for name, desc in SLASH_COMMANDS:
            print(f"  {CYAN}/{name:<9}{RESET} {desc}")
        print(f"\n{DIM}Tip: type '/' then Enter to pick from a menu.{RESET}")
        print(f"{DIM}Anything else is sent to the agent.{RESET}\n")

    def pick_command():
        from motherflame.agent import arrow_select
        labels = [f"/{name:<9} {DIM}{desc}{RESET}" for name, desc in SLASH_COMMANDS]
        idx = arrow_select("Pick a command:", labels, default=0)
        return SLASH_COMMANDS[idx][0]

    def do_harvest():
        nonlocal brain
        folders = _pick_folders(str(Path.home()))
        if not folders:
            print(f"  {DIM}No folders selected{RESET}\n")
            return
        globs, label = _pick_scan_types()
        use_llm = bool(cfg.get("agent_api_key")) or cfg.get("provider") == "ollama"
        before = len(brain.get("items", []))
        for folder in folders:
            spinner(f"Scanning {Path(folder).name}...", 1.0)
            brain, _ = harvest_from_folder(folder, brain, globs=globs, use_llm=use_llm, cfg=cfg)
        added = len(brain.get("items", [])) - before
        if added > 0:
            brain["last_updated"] = _dt.now().strftime("%Y-%m-%d %H:%M")
            save_brain(brain)
            print(f"  {GREEN}✓ Added {added} new facts to the Org Brain{RESET}\n")
        else:
            print(f"  {DIM}No new facts found{RESET}\n")

    def do_refresh():
        nonlocal brain
        folders = _pick_folders(str(Path.home()))
        if not folders:
            print(f"  {DIM}No folders selected{RESET}\n")
            return
        globs, label = _pick_scan_types()
        use_llm = bool(cfg.get("agent_api_key")) or cfg.get("provider") == "ollama"
        before = len(brain.get("items", []))
        for folder in folders:
            spinner(f"Refreshing {Path(folder).name}...", 1.0)
            brain, _ = harvest_from_folder(folder, brain, globs=globs,
                                           use_llm=use_llm, cfg=cfg, changed_only=True)
        added = len(brain.get("items", [])) - before
        if added > 0:
            brain["last_updated"] = _dt.now().strftime("%Y-%m-%d %H:%M")
            save_brain(brain)
            print(f"  {GREEN}✓ {added} new facts from changed files{RESET}\n")
        else:
            print(f"  {GREEN}✓ Brain is up to date — nothing changed{RESET}\n")

    def do_conflicts():
        from motherflame import conflicts
        conflicts.ensure_layers(brain)
        conflicts.migrate_items_to_claims(brain)
        items = conflicts.list_conflicts(brain)
        if not items:
            print(f"  {GREEN}✓ No conflicts — every fact has a clear source of truth{RESET}\n")
            return
        print(f"\n{BOLD}⚔️  Contested facts ({len(items)}):{RESET}\n")
        for c in items:
            print(f"  {BOLD}{c['key']}{RESET} {DIM}({c['category']}){RESET}")
            print(f"    {GREEN}→ current:{RESET} {c['current']}  {DIM}[{c['reason']}]{RESET}")
            for cand in c["candidates"]:
                mark = "★" if cand["value"] == c["current"] else " "
                print(f"      {mark} {cand['value'][:50]}  {DIM}{cand['owner']} · {cand['source']} · conf {cand['confidence']:.2f}{RESET}")
            print()
        print(f"  {DIM}Use /resolve to settle one, or /owner to set authority.{RESET}\n")

    def do_forget():
        """Retract (tombstone) a fact — survives merges so it won't resurrect."""
        from motherflame import conflicts
        from motherflame.agent import arrow_select
        conflicts.ensure_layers(brain)
        conflicts.migrate_items_to_claims(brain)
        keys = sorted(k for k, v in brain.get("claims", {}).items()
                      if conflicts._live_claims(brain, k))
        if not keys:
            print(f"  {DIM}Nothing to forget — the brain is empty.{RESET}\n")
            return
        kidx = arrow_select("Forget which fact?", keys, default=0)
        key = keys[kidx]
        n = conflicts.retract_claim(brain, key)
        conflicts.rebuild_canonical(brain)
        brain["last_updated"] = _dt.now().strftime("%Y-%m-%d %H:%M")
        save_brain(brain)
        print(f"  {GREEN}✓ Forgot '{key}'{RESET} {DIM}({n} claim(s) tombstoned — won't return on sync){RESET}\n")

    def do_resolve():
        from motherflame import conflicts
        from motherflame.agent import arrow_select
        conflicts.ensure_layers(brain)
        conflicts.migrate_items_to_claims(brain)
        items = conflicts.list_conflicts(brain)
        if not items:
            print(f"  {GREEN}✓ Nothing to resolve{RESET}\n")
            return
        # pick which contested key (or bulk auto-resolve)
        BULK = "⚡ Auto-resolve all (owner/consensus winners)"
        kidx = arrow_select("Which fact to settle?",
                            [BULK] + [f"{c['key']} ({len(c['candidates'])} claims)" for c in items], default=0)
        if kidx == 0:
            result = conflicts.auto_resolve_all(brain)
            brain["last_updated"] = _dt.now().strftime("%Y-%m-%d %H:%M")
            save_brain(brain)
            na, nh = len(result["auto_resolved"]), len(result["needs_human"])
            print(f"  {GREEN}✓ Auto-resolved {na} conflicts{RESET} "
                  f"{DIM}({nh} still need you — re-run /resolve){RESET}\n")
            return
        chosen = items[kidx - 1]
        # pick the winning value
        labels = [f"{cand['value'][:45]}  ({cand['owner']} · {cand['source']})"
                  for cand in chosen["candidates"]]
        labels.append("✎ Type my own value")
        vidx = arrow_select(f"True value for '{chosen['key']}':", labels, default=0)
        if vidx == len(chosen["candidates"]):
            value = ask("Enter the correct value", "")
            if not value:
                print(f"  {DIM}Cancelled{RESET}\n")
                return
        else:
            value = chosen["candidates"][vidx]["value"]
        me = cfg.get("member_name", "") or "you"
        conflicts.manual_resolve(brain, chosen["key"], value, by=me)
        conflicts.rebuild_canonical(brain)
        brain["last_updated"] = _dt.now().strftime("%Y-%m-%d %H:%M")
        save_brain(brain)
        print(f"  {GREEN}✓ '{chosen['key']}' resolved → {value}{RESET}\n")

    def do_owner():
        from motherflame import conflicts
        scope = ask("Owner for which category or key? (e.g. Product, or pricing)", "")
        if not scope:
            print(f"  {DIM}Cancelled{RESET}\n")
            return
        owner = ask(f"Who owns '{scope}'? (name)", "")
        if not owner:
            print(f"  {DIM}Cancelled{RESET}\n")
            return
        conflicts.ensure_layers(brain)
        conflicts.set_owner(brain, scope, owner)
        conflicts.rebuild_canonical(brain)
        save_brain(brain)
        print(f"  {GREEN}✓ {owner} now owns '{scope}' — their claims win conflicts{RESET}\n")

    def do_plan():
        goal = ask("What do you want to accomplish?", "")
        if not goal:
            print(f"  {DIM}Cancelled{RESET}\n")
            return
        spinner("Planning...", 0.8)
        try:
            steps = plan_task(cfg, brain, goal)
        except Exception as e:
            print(f"  {RED}✗ Planning failed: {e}{RESET}\n")
            return
        if not steps:
            print(f"  {DIM}No plan produced{RESET}\n")
            return
        print(f"\n{BOLD}📋 Plan for:{RESET} {goal}")
        for i, step in enumerate(steps, 1):
            print(f"  {FLAME_ORANGE}{i}.{RESET} {step}")
        print()
        go = ask("Execute this plan with the agent? (y/N)", "n").lower()
        if go in ("y", "yes"):
            # Feed the plan to the agent as a single instruction
            instruction = (f"Execute this plan step by step for goal '{goal}':\n"
                           + "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
                           + "\nUse your tools. Add any facts you discover or decide.")
            print(f"{DIM}  executing...{RESET}", end="\r", flush=True)
            try:
                answer, mutated = agent_turn(cfg, brain, instruction, history, on_tool=show_tool)
                print(f"{CLEAR_LINE}", end="")
                print(f"{FLAME_ORANGE}ai  ›{RESET} {answer}\n")
                if mutated:
                    brain["last_updated"] = _dt.now().strftime("%Y-%m-%d %H:%M")
                    save_brain(brain)
                    print(f"  {GREEN}✓ Org Brain updated{RESET}\n")
            except Exception as e:
                print(f"{CLEAR_LINE}{RED}✗ Error: {e}{RESET}\n")
        else:
            print(f"  {DIM}Plan saved to conversation. Ask the agent to run it anytime.{RESET}\n")

    def do_optimize():
        # Find gaps, duplicates, low-confidence facts
        items = brain.get("items", [])
        print(f"\n{BOLD}🔍 Org Brain Optimization Report{RESET}\n")

        # 1. Gaps
        gaps = brain.get("gaps", [])
        print(f"  {BOLD}Gaps ({len(gaps)}):{RESET}")
        if gaps:
            for g in gaps:
                print(f"    {RED}·{RESET} {g}")
        else:
            print(f"    {GREEN}None — brain is complete{RESET}")

        # 2. Duplicate keys
        seen = {}
        dups = []
        for it in items:
            k = it["key"]
            if k in seen:
                dups.append(k)
            seen[k] = it
        print(f"\n  {BOLD}Duplicate keys ({len(set(dups))}):{RESET}")
        if dups:
            for d in set(dups):
                print(f"    {FLAME_YELLOW}·{RESET} {d}")
        else:
            print(f"    {GREEN}None{RESET}")

        # 3. Low-confidence facts (from keyword harvest, conf < 0.8)
        low = [it for it in items if it.get("confidence", 1.0) < 0.8]
        print(f"\n  {BOLD}Low-confidence facts ({len(low)}):{RESET}")
        for it in low[:8]:
            print(f"    {DIM}· {it['key']}: {it['value'][:50]} (conf {it.get('confidence',0):.1f}){RESET}")
        if len(low) > 8:
            print(f"    {DIM}... and {len(low)-8} more{RESET}")

        # 4. Category coverage
        cats = {}
        for it in items:
            cats[it["category"]] = cats.get(it["category"], 0) + 1
        print(f"\n  {BOLD}Coverage by category:{RESET}")
        for cat in ["Company", "Product", "Team", "Voice", "Strategy"]:
            n = cats.get(cat, 0)
            bar = "█" * min(n, 10)
            color = GREEN if n >= 2 else (FLAME_YELLOW if n == 1 else RED)
            print(f"    {cat:<10} {color}{bar}{RESET} {n}")

        # 5. Suggestion via agent
        print()
        sug = ask("Ask the agent for improvement suggestions? (y/N)", "n").lower()
        if sug in ("y", "yes"):
            print(f"{DIM}  thinking...{RESET}", end="\r", flush=True)
            try:
                q = "Based on the Org Brain, what are the 3 most important missing facts we should add? Be specific and brief."
                answer, _ = agent_turn(cfg, brain, q, history, on_tool=show_tool)
                print(f"{CLEAR_LINE}", end="")
                print(f"{FLAME_ORANGE}ai  ›{RESET} {answer}\n")
            except Exception as e:
                print(f"{CLEAR_LINE}{RED}✗ {e}{RESET}\n")
        else:
            print()

    def do_sources():
        # Show provenance — where facts came from
        writes = ledger.get_fact_writes(limit=20)
        if not writes:
            print(f"  {DIM}No provenance recorded yet. Run /harvest or add facts.{RESET}\n")
            return
        print(f"\n{BOLD}📑 Fact Sources (most recent {len(writes)}):{RESET}")
        for w in reversed(writes):
            ts = w["ts"][5:16].replace("T", " ")
            print(f"  {DIM}{ts}{RESET}  {CYAN}{w['key']}{RESET} {DIM}← {w['source']}{RESET}")
        print()

    def do_history():
        stats = ledger.summary_stats()
        print(f"\n{BOLD}🕘 Motherflame Activity Log{RESET}\n")
        print(f"  Folders scanned:   {BOLD}{stats['total_folders']}{RESET}")
        print(f"  Total scans:       {stats['total_scans']}")
        print(f"  Files seen:        {stats['total_files_seen']}")
        print(f"  Facts written:     {BOLD}{stats['total_writes']}{RESET}")
        if stats["first_event"]:
            print(f"  First activity:    {DIM}{stats['first_event'][:16].replace('T',' ')}{RESET}")
            print(f"  Last activity:     {DIM}{stats['last_event'][:16].replace('T',' ')}{RESET}")
        if stats["folders"]:
            print(f"\n  {BOLD}Scanned folders:{RESET}")
            for f in stats["folders"]:
                print(f"    {DIM}· {f}{RESET}")
        # recent scans
        scans = ledger.get_scans(limit=5)
        if scans:
            print(f"\n  {BOLD}Recent scans:{RESET}")
            for s in reversed(scans):
                ts = s["ts"][5:16].replace("T", " ")
                print(f"    {DIM}{ts}{RESET}  {Path(s['folder']).name}  "
                      f"{DIM}({s['file_count']} files → {s['signals_found']} signals){RESET}")
        # past sessions
        sess = sessions.list_sessions(limit=5)
        if sess:
            print(f"\n  {BOLD}Recent sessions:{RESET}")
            for s in sess:
                print(f"    {DIM}{s['updated_at'][:16].replace('T',' ')}{RESET}  "
                      f"{s['n_messages']} msgs  {DIM}\"{s['preview']}\"{RESET}")
        print()

    while True:
        try:
            user = input(f"{FLAME_YELLOW}you ›{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user:
            continue

        # ── Slash commands ──
        if user.startswith("/") or user.lower() in ("exit", "quit"):
            cmd = user.lower().lstrip("/")
            known = {name for name, _ in SLASH_COMMANDS}
            if cmd == "" or (cmd not in known and cmd not in ("?",)):
                if cmd and cmd != "":
                    print(f"  {DIM}'/{cmd}' not found — pick one:{RESET}")
                cmd = pick_command()

            if cmd in ("exit", "quit"):
                break
            elif cmd in ("help", "?"):
                chat_help()
            elif cmd == "plan":
                do_plan()
            elif cmd == "harvest":
                do_harvest()
            elif cmd == "refresh":
                do_refresh()
            elif cmd == "start":
                cmd_start()
                brain = load_brain()
                print()
            elif cmd == "brain":
                cmd_brain()
            elif cmd == "gaps":
                gaps = brain.get("gaps", [])
                if gaps:
                    print(f"  {RED}Missing:{RESET} {', '.join(gaps)}\n")
                else:
                    print(f"  {GREEN}No known gaps{RESET}\n")
            elif cmd == "optimize":
                do_optimize()
            elif cmd == "conflicts":
                do_conflicts()
            elif cmd == "resolve":
                do_resolve()
            elif cmd == "forget":
                do_forget()
            elif cmd == "owner":
                do_owner()
            elif cmd == "sources":
                do_sources()
            elif cmd == "history":
                do_history()
            elif cmd == "status":
                print()
                print_status_box(cfg, brain)
            elif cmd == "clear":
                history.clear()
                print(f"  {DIM}Conversation memory cleared{RESET}\n")
            else:
                print(f"  {RED}Unknown command: /{cmd}{RESET}  (try /help)\n")
            continue

        # ── Otherwise → agent turn ──
        print(f"{DIM}  thinking...{RESET}", end="\r", flush=True)
        try:
            answer, mutated = agent_turn(cfg, brain, user, history, on_tool=show_tool)
        except Exception as e:
            print(f"{CLEAR_LINE}{RED}✗ Error: {e}{RESET}\n")
            continue
        print(f"{CLEAR_LINE}", end="")
        print(f"{FLAME_ORANGE}ai  ›{RESET} {answer}\n")

        if mutated:
            brain["last_updated"] = _dt.now().strftime("%Y-%m-%d %H:%M")
            save_brain(brain)
            print(f"  {GREEN}✓ Org Brain updated{RESET}\n")

    # ── On exit: persist the session ──
    facts_added = len(brain.get("items", [])) - facts_at_start
    if history:
        sessions.save_session(session_id, history,
                              meta={"org": org, "facts_added": facts_added})
        ledger.record_session(summary=f"{len(history)} messages",
                              n_messages=len(history), n_facts_added=facts_added)
        print(f"{DIM}Session {session_id} saved · {facts_added} facts added this session{RESET}")

    print(f"\n{FLAME_ORANGE}Flame stays lit. 🔥{RESET}\n")


def cmd_push():
    """motherflame push — encrypt the Org Brain client-side and sync to cloud (zero-knowledge)."""
    from motherflame import sync

    cfg = load_config()
    brain = load_brain()
    flame_key = cfg.get("flame_key") or cfg.get("api_key")
    org_id = cfg.get("org_name", "org")

    if not flame_key:
        print(f"{RED}✗ No Flame Key. Run: {CYAN}motherflame connect <key>{RESET}")
        return
    if not brain.get("items"):
        print(f"{RED}✗ Org Brain is empty — nothing to push.{RESET}")
        return

    spinner("Encrypting & pushing...", 0.6)
    git_remote = cfg.get("sync_remote")   # set to a git URL for real team sync
    try:
        receipt = sync.push(brain, flame_key, org_id, git_remote=git_remote)
        if not receipt.get("ok"):
            print(f"{RED}✗ Push failed: {receipt.get('error','unknown')}{RESET}\n")
            return
        where = f"git ({git_remote})" if receipt.get("backend") == "git" else "local store"
        print(f"{GREEN}✓ Pushed to {where} (zero-knowledge){RESET}")
        print(f"  {DIM}{receipt['items']} items · {receipt['bytes']} bytes encrypted{RESET}")
        print(f"  {DIM}Encrypted client-side — the server never sees your data{RESET}")
        if receipt.get("backend") != "git":
            print(f"  {DIM}Tip: set sync_remote to a git URL for real team sync{RESET}")
        print()
    except Exception as e:
        print(f"{RED}✗ Push failed: {e}{RESET}\n")


def cmd_pull():
    """motherflame pull — download & decrypt the Org Brain, merge into local."""
    from motherflame import sync

    cfg = load_config()
    brain = load_brain()
    flame_key = cfg.get("flame_key") or cfg.get("api_key")
    org_id = cfg.get("org_name", "org")

    if not flame_key:
        print(f"{RED}✗ No Flame Key. Run: {CYAN}motherflame connect <key>{RESET}")
        return

    spinner("Pulling & decrypting...", 0.6)
    git_remote = cfg.get("sync_remote")
    try:
        remote = sync.pull(flame_key, org_id, git_remote=git_remote)
    except ValueError as e:
        print(f"{RED}✗ Decryption failed: {e}{RESET}\n")
        return
    except Exception as e:
        print(f"{RED}✗ Pull failed: {e}{RESET}\n")
        return

    if remote is None:
        print(f"{DIM}  Nothing in the cloud yet for {org_id}. Run 'motherflame push' first.{RESET}\n")
        return

    merged, n_new = sync.merge_brains(brain, remote)
    merged["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    save_brain(merged)
    print(f"{GREEN}✓ Pulled & merged{RESET}")
    print(f"  {DIM}{n_new} new facts from teammates · {len(merged['items'])} total{RESET}\n")


def cmd_config(args):
    """motherflame config get|set|list — read or set config values."""
    cfg = load_config()
    if not args or args[0] == "list":
        if not cfg:
            print(f"  {DIM}No config yet. Run 'motherflame setup' or 'motherflame connect'.{RESET}")
            return
        print(f"\n{BOLD}Motherflame config{RESET} {DIM}(~/.motherflame/config.json){RESET}\n")
        SECRET = {"agent_api_key", "api_key", "flame_key"}
        for k, v in cfg.items():
            shown = (str(v)[:6] + "…") if k in SECRET and v else v
            print(f"  {CYAN}{k}{RESET} = {shown}")
        print()
        return
    action = args[0]
    if action == "get":
        if len(args) < 2:
            print("Usage: motherflame config get <key>")
            return
        print(cfg.get(args[1], ""))
    elif action == "set":
        if len(args) < 3:
            print("Usage: motherflame config set <key> <value>")
            return
        key, value = args[1], " ".join(args[2:])
        cfg[key] = value
        save_config(cfg)
        print(f"  {GREEN}✓ {key} = {value}{RESET}")
    else:
        print(f"Unknown config action: {action} (use get/set/list)")
