#!/bin/bash
if [ ! -t 0 ] || [ ! -t 1 ]; then
    echo "Error: Interactive terminal (TTY) required. Connect with: ssh -t -p 5822 play@minesweeper-ssh.duckdns.org" >&2
    exit 1
fi

export TERM=${TERM:-xterm-256color}
export PYTHONPATH=/opt/minesweeper
cd /opt/minesweeper
exec /opt/minesweeper/venv/bin/python /opt/minesweeper/main.py
