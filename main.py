from __future__ import annotations

import argparse
import asyncio
import sys

from minesweeper.app import MinesweeperApp
from minesweeper.game import DIFFICULTIES, MinesweeperGame


def main():
    parser = argparse.ArgumentParser(
        description="Minesweeper Terminal & SSH Application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                     # Run game locally
  python main.py -d expert           # Start directly on Expert difficulty
  python main.py --ssh --port 2222   # Run as an SSH server on port 2222
        """,
    )
    parser.add_argument(
        "--difficulty",
        "-d",
        choices=["beginner", "intermediate", "expert"],
        default="beginner",
        help="Initial difficulty (default: beginner)",
    )
    parser.add_argument(
        "--ssh",
        action="store_true",
        help="Run in SSH server mode",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=2222,
        help="Port for SSH server (default: 2222)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="",
        help="Host for SSH server (default: all interfaces)",
    )

    parser.add_argument(
        "--hub",
        action="store_true",
        help="Run PVP matchmaking hub server",
    )

    args, _ = parser.parse_known_args()

    if args.hub:
        from minesweeper.hub import run_hub

        run_hub()
        return

    if args.ssh:
        from minesweeper.server import start_server

        try:
            asyncio.run(start_server(host=args.host, port=args.port))
        except (KeyboardInterrupt, SystemExit):
            print("\nSSH server stopped.")
        return

    if not args.hub and not args.ssh:
        if not sys.stdin.isatty():
            sys.stderr.write("Interactive terminal (TTY) required.\n")
            sys.exit(1)

        import signal
        try:
            signal.signal(signal.SIGHUP, lambda *_: sys.exit(0))
            signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        except (AttributeError, ValueError):
            pass

    app = MinesweeperApp()
    if args.difficulty != "beginner":
        cfg = DIFFICULTIES[args.difficulty]
        app.current_rows = cfg.rows
        app.current_cols = cfg.cols
        app.current_mines = cfg.mines
        app.current_diff_name = cfg.name
        app.game = MinesweeperGame(cfg.rows, cfg.cols, cfg.mines, cfg.name)

    app.run()


if __name__ == "__main__":
    main()

