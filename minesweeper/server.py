from __future__ import annotations

import argparse
import asyncio
import fcntl
import os
import pty
import signal
import struct
import sys
import termios
from typing import Optional

import asyncssh


def set_winsize(fd: int, rows: int, cols: int) -> None:
    try:
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
    except OSError:
        pass


class MinesweeperSSHServer(asyncssh.SSHServer):
    def connection_made(self, conn: asyncssh.SSHServerConnection) -> None:
        pass

    def begin_auth(self, username: str) -> bool:
        return False


async def handle_client(process: asyncssh.SSHServerProcess) -> None:
    cols, rows = process.get_terminal_size()
    term_type = process.get_terminal_type() or "xterm-256color"

    master_fd, slave_fd = pty.openpty()
    set_winsize(master_fd, rows, cols)

    env = os.environ.copy()
    env["TERM"] = term_type
    env["COLUMNS"] = str(cols)
    env["LINES"] = str(rows)

    loop = asyncio.get_running_loop()

    def on_size_changed(new_cols: int, new_rows: int, *_) -> None:
        set_winsize(master_fd, new_rows, new_cols)
        try:
            os.kill(proc.pid, signal.SIGWINCH)
        except (ProcessLookupError, OSError):
            pass

    process.terminal_size_changed = on_size_changed

    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "minesweeper.app",
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
        env=env,
    )
    os.close(slave_fd)

    def on_master_read():
        try:
            data = os.read(master_fd, 1024)
            if data:
                process.stdout.write(data)
            else:
                loop.remove_reader(master_fd)
        except OSError:
            loop.remove_reader(master_fd)

    loop.add_reader(master_fd, on_master_read)

    async def forward_input():
        try:
            while not process.stdin.at_eof():
                data = await process.stdin.read(1024)
                if not data:
                    break
                os.write(master_fd, data if isinstance(data, bytes) else data.encode())
        except (asyncio.CancelledError, OSError):
            pass

    input_task = asyncio.create_task(forward_input())

    try:
        await proc.wait()
    finally:
        input_task.cancel()
        try:
            loop.remove_reader(master_fd)
        except Exception:
            pass
        try:
            os.close(master_fd)
        except OSError:
            pass
        process.exit(proc.returncode or 0)


async def start_server(host: str = "", port: int = 2222, host_key: Optional[str] = None) -> None:
    if host_key is None:
        key = asyncssh.generate_private_key("ssh-ed25519")
    else:
        key = host_key

    server = await asyncssh.create_server(
        MinesweeperSSHServer,
        host,
        port,
        server_host_keys=[key],
        process_factory=handle_client,
        encoding=None,
    )
    print(f"Minesweeper SSH server running on port {port}!")
    print(f"Connect using: ssh -p {port} localhost")
    await server.wait_closed()


def main():
    parser = argparse.ArgumentParser(description="Minesweeper SSH Server")
    parser.add_argument("--port", "-p", type=int, default=2222, help="Port to listen on (default: 2222)")
    parser.add_argument("--host", type=str, default="", help="Host to bind to (default: all interfaces)")
    args = parser.parse_args()

    try:
        asyncio.run(start_server(host=args.host, port=args.port))
    except (KeyboardInterrupt, SystemExit):
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
