"""
Motherflame splash screen — the big startup banner.

A Hermes-style launch panel: a figlet wordmark, then a bordered box with an
ASCII flame on the left and live status sections (Org Brain, AI agent, Team,
Knowledge) on the right, plus a footer. Pure stdlib + ANSI — no deps.
"""
from motherflame import __version__

RESET        = "\033[0m"
BOLD         = "\033[1m"
DIM          = "\033[2m"
GREEN        = "\033[92m"
RED          = "\033[91m"
CYAN         = "\033[96m"
FLAME_ORANGE = "\033[38;5;208m"
FLAME_YELLOW = "\033[38;5;220m"
FLAME_RED    = "\033[38;5;196m"
FLAME_DEEP   = "\033[38;5;202m"
EMBER        = "\033[38;5;238m"
GREY         = "\033[38;5;245m"

# Figlet "MOTHERFLAME" (standard font). Rendered with a warm gradient per line.
_BANNER = r""" __  __  ___ _____ _   _ _____ ____  _____ _        _    __  __ _____
|  \/  |/ _ \_   _| | | | ____|  _ \|  ___| |      / \  |  \/  | ____|
| |\/| | | | || | | |_| |  _| | |_) | |_  | |     / _ \ | |\/| |  _|
| |  | | |_| || | |  _  | |___|  _ <|  _| | |___ / ___ \| |  | | |___
|_|  |_|\___/ |_| |_| |_|_____|_| \_\_|   |_____/_/   \_\_|  |_|_____|"""

# Per-row gradient: ember at the base → bright tip at the top of the letters.
_BANNER_GRAD = [FLAME_YELLOW, FLAME_ORANGE, FLAME_ORANGE, FLAME_DEEP, FLAME_RED]

# A small ASCII flame for the left of the box.
_FLAME = [
    "       (              ",
    "        )      )      ",
    "      (    (  /(      ",
    "       )   )\\()(      ",
    "      /(  ((_)\\ )     ",
    "     (_))  _((_)      ",
    "     | _ \\| | | |     ",
    "     |  _/| | | |     ",
    "     |_|  |_| |_|     ",
    "      \\  the  /       ",
    "       \\ fire/        ",
    "        \\__/          ",
]


def _gradient_banner() -> str:
    out = []
    rows = _BANNER.split("\n")
    for i, row in enumerate(rows):
        c = _BANNER_GRAD[min(i, len(_BANNER_GRAD) - 1)]
        out.append(f"{c}{BOLD}{row}{RESET}")
    return "\n".join(out)


def _flame_line(i: int) -> str:
    """Colored flame row i (or blank padding) — orange body, dim base."""
    if i < len(_FLAME):
        c = FLAME_YELLOW if i <= 1 else (FLAME_ORANGE if i <= 8 else EMBER)
        return f"{c}{_FLAME[i]}{RESET}"
    return " " * 21


def render_splash(cfg: dict, brain: dict) -> str:
    """Build the full splash screen string for the current state."""
    org       = cfg.get("org_name") or brain.get("org_name") or "—"
    has_ai    = bool(cfg.get("agent_api_key")) or cfg.get("provider") == "ollama"
    provider  = f"{cfg.get('provider','—')}/{cfg.get('model','—')}" if has_ai else "not connected"
    n_items   = len(brain.get("items", []))
    n_pending = len(brain.get("pending", []))
    remote    = cfg.get("sync_remote")
    members   = cfg.get("members", 1)
    key       = cfg.get("flame_key") or cfg.get("api_key")

    def ok(b):   return f"{GREEN}●{RESET}" if b else f"{EMBER}○{RESET}"

    # right-column content rows (label, value, lit?)
    rows = [
        (f"{BOLD}Org Brain{RESET}",  org if key else "not connected",       bool(key)),
        (f"{BOLD}AI Agent{RESET}",   provider,                              has_ai),
        (f"{BOLD}Knowledge{RESET}",  f"{n_items} fact" + ("" if n_items == 1 else "s") + (f" · {n_pending} pending" if n_pending else ""), n_items > 0),
        (f"{BOLD}Team{RESET}",       (f"{members} member(s) · synced" if remote else "solo (no remote)"), True),
    ]

    lines = []
    lines.append("")
    lines.append(_gradient_banner())
    lines.append("")
    # title line above the box
    lines.append(f"  {FLAME_ORANGE}{BOLD}🔥 Motherflame{RESET} {DIM}v{__version__}{RESET}  "
                 f"{DIM}· the Org Brain for teams that use AI{RESET}")
    lines.append("")

    # box: flame on the left, status on the right
    BW = 64  # inner width
    top = f"  {FLAME_DEEP}╭{'─' * BW}╮{RESET}"
    bot = f"  {FLAME_DEEP}╰{'─' * BW}╯{RESET}"
    lines.append(top)

    # section content (right column)
    content = [f"{FLAME_YELLOW}{BOLD}Your Org Brain{RESET}", ""]
    for label, val, lit in rows:
        valc = GREEN if lit else EMBER
        plain_label = label.replace(BOLD, "").replace(RESET, "")
        content.append(f"  {ok(lit)} {BOLD}{plain_label:<10}{RESET} {valc}{val}{RESET}")
    content.append("")
    if key:
        content.append(f"{DIM}Flame Key {FLAME_YELLOW}{key}{RESET}{DIM} 🔒{RESET}")
    # next-step hint
    if not has_ai:
        content.append(f"{DIM}Next:{RESET} {CYAN}motherflame setup{RESET}")
    elif n_items == 0:
        content.append(f"{DIM}Next:{RESET} {CYAN}motherflame start{RESET}")
    else:
        content.append(f"{DIM}Ready 🔥 — type{RESET} {CYAN}motherflame chat{RESET} {DIM}or{RESET} {CYAN}/help{RESET}")

    # zip flame + content into rows of the box
    nrows = max(len(_FLAME), len(content))
    for i in range(nrows):
        left = _flame_line(i)
        right = content[i] if i < len(content) else ""
        # pad right to inner width accounting for ANSI (approx: strip codes for len)
        bare = _strip_ansi(right)
        pad = max(0, BW - 23 - len(bare))
        lines.append(f"  {FLAME_DEEP}│{RESET} {left} {right}{' ' * pad} {FLAME_DEEP}│{RESET}")
    lines.append(bot)

    # footer
    lines.append("")
    lines.append(f"  {DIM}Welcome to Motherflame! Type a command or{RESET} {CYAN}motherflame doctor{RESET} "
                 f"{DIM}to check setup.{RESET}")
    lines.append("")
    return "\n".join(lines)


def _strip_ansi(s: str) -> str:
    import re
    return re.sub(r"\033\[[0-9;]*m", "", s)
