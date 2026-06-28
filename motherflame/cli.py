#!/usr/bin/env python3
"""Motherflame CLI — Entry point"""

import sys
from motherflame.core import (
    cmd_connect, cmd_create, cmd_join, cmd_status, cmd_doctor, cmd_team, cmd_start, cmd_brain,
    cmd_help, cmd_setup, cmd_query, cmd_chat, cmd_push, cmd_pull, cmd_config,
    print_banner, load_config, load_brain, print_status_box,
)


def _pop_flag(args, flag):
    """Extract `--flag value` from args, return (value or None, remaining args)."""
    if flag in args:
        i = args.index(flag)
        if i + 1 < len(args):
            return args[i + 1], args[:i] + args[i + 2:]
    return None, args


def main():
    args = sys.argv[1:]

    if not args:
        # Bare `motherflame` → smart entry:
        #   not set up      → show status + guide to setup
        #   set up + brain  → jump straight into chat (the agent)
        #   set up, no brain→ show status + guide to start
        cfg   = load_config()
        brain = load_brain()
        has_agent = bool(cfg.get("agent_api_key")) or cfg.get("provider") == "ollama"
        has_brain = bool(brain.get("items"))

        if has_agent and has_brain:
            cmd_chat()
        else:
            print_banner()
            print_status_box(cfg, brain)
        return

    cmd = args[0].lower()

    if cmd == "setup":
        cmd_setup()

    elif cmd == "connect":
        # No key → cmd_connect auto-generates a local Flame Key (no server needed).
        cmd_connect(args[1] if len(args) >= 2 else None)

    elif cmd == "create":
        remote, rest = _pop_flag(args[1:], "--remote")
        org_name = rest[0] if rest else None
        cmd_create(org_name, remote=remote)

    elif cmd == "join":
        remote, rest = _pop_flag(args[1:], "--remote")
        key = rest[0] if rest else None
        cmd_join(key, remote=remote)

    elif cmd == "status":
        cmd_status()

    elif cmd == "doctor":
        cmd_doctor()

    elif cmd == "team":
        cmd_team()

    elif cmd == "start":
        cmd_start()

    elif cmd == "brain":
        cmd_brain()

    elif cmd == "query":
        if len(args) < 2:
            print("Usage: motherflame query \"your question here\"")
            return
        question = " ".join(args[1:])
        cmd_query(question)

    elif cmd == "chat":
        resume = "--resume" in args or "-r" in args
        cmd_chat(resume=resume)

    elif cmd == "push":
        cmd_push()

    elif cmd == "pull":
        cmd_pull()

    elif cmd == "mcp":
        from motherflame.mcp_server import serve
        serve()

    elif cmd == "config":
        cmd_config(args[1:])

    elif cmd in ("help", "--help", "-h"):
        cmd_help()

    else:
        print(f"Unknown command: {cmd}")
        print("Run 'motherflame help' for usage")


if __name__ == "__main__":
    main()
