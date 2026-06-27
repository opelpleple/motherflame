#!/usr/bin/env python3
"""Motherflame CLI — Entry point"""

import sys
from motherflame.core import (
    cmd_connect, cmd_status, cmd_start, cmd_brain,
    cmd_help, cmd_setup, cmd_query, cmd_chat, cmd_push, cmd_pull, cmd_config,
    print_banner, load_config, load_brain, print_status_box,
)


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
        if len(args) < 2:
            print("Usage: motherflame connect <flame_key>")
            print("Get your key at motherflame.ai/signup")
            return
        cmd_connect(args[1])

    elif cmd == "status":
        cmd_status()

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
