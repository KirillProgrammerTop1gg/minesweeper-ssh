# Minesweeper Terminal & SSH

Play without installing anything:

```bash
ssh -p 5822 play@minesweeper-ssh.duckdns.org
```

Minesweeper for the terminal, written in Python with [Textual](https://github.com/Textualize/textual). It runs locally or over SSH, and has a ranked PvP mode.


![Screenshot](screenshot.svg)

## Gameplay

Boards: Beginner 9x9 with 10 mines, Intermediate 16x16 with 40, Expert 16x30 with 99, or Custom (width, height and mines set in a dialog). First click is always safe, and chording is supported.

Cells are addressed by coordinates: columns are letters (`A`-`Z`, then `AA`...), rows are numbers. The cursor wraps around the edges. You can also type `B5` in the bar at the bottom to open a cell, or `F B5` to flag it. The mouse works too: left-click opens, right-click flags.

Singleplayer high scores are saved in `leaderboard.json`.

## PvP

Press `5` to queue for a ranked match. Both players get the same 16x16 board with 40 mines and play at the same time, seeing each other's score, time, cleared cells and status.

- Hitting a mine ends your run.
- 30 seconds without an action also ends it.
- Safe cells give points, a correct flag gives +25, a wrong flag costs 10, and clearing the board gives a speed bonus.
- Highest score wins, ties go to the faster time.

Records are tied to a fingerprint of your SSH client (shown as a tag like `#A4E2`). Winners enter a nickname for the leaderboard (`L`).

## Controls

| Key | Action |
| --- | --- |
| Arrows / `WASD` | Move cursor |
| `O` / `Enter` / `Space` | Reveal cell |
| `F` | Toggle flag |
| `C` | Chord |
| `1`-`4` | Beginner, Intermediate, Expert, Custom |
| `5` | PvP matchmaking |
| `L` | Leaderboard |
| `R` | Restart |
| `/` | Focus coordinate bar |
| `H` | Help |
| `Esc` | Back to board / close dialog |
| `Ctrl+Q` / `Q` | Quit |

## Running locally

Needs Python 3.10+.

```bash
pip install textual asyncssh
python main.py              # or: uv run python main.py
python main.py -d expert    # start at a given difficulty
```

## Hosting your own server

```bash
python main.py --hub &              # PvP matchmaking hub
python main.py --ssh --port 2222    # SSH server
ssh -p 2222 localhost               # connect
```

## Code layout

`game.py` has the game logic and PvP engine, `hub.py` is the matchmaking server, `pvp_client.py` is its client, `server.py` is the SSH server, `leaderboard.py` handles saved scores and profiles, and `fingerprint.py` makes the client tag. The UI is in `app.py`, `screens/` (dialogs) and `widgets/` (board, command bar, stats).
