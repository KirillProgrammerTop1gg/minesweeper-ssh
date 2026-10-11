from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

LEADERBOARD_PATH = Path("leaderboard.json")


def _get_path() -> Path:
    if LEADERBOARD_PATH.parent.exists():
        return LEADERBOARD_PATH
    return Path.home() / ".minesweeper_leaderboard.json"


def load_leaderboard() -> dict:
    path = _get_path()
    if not path.exists():
        return {"singleplayer": [], "pvp": [], "pvp_profiles": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {"singleplayer": [], "pvp": [], "pvp_profiles": {}}
            data.setdefault("singleplayer", [])
            data.setdefault("pvp", [])
            data.setdefault("pvp_profiles", {})
            return data
    except Exception:
        return {"singleplayer": [], "pvp": [], "pvp_profiles": {}}


def save_leaderboard(data: dict) -> None:
    path = _get_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def add_singleplayer_score(name: str, difficulty: str, score: int, elapsed_time: int) -> None:
    data = load_leaderboard()
    entry = {
        "name": name.strip() or "Anonymous",
        "difficulty": difficulty,
        "score": score,
        "time": elapsed_time,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    data["singleplayer"].append(entry)
    data["singleplayer"].sort(key=lambda x: (-x["score"], x["time"]))
    data["singleplayer"] = data["singleplayer"][:50]
    save_leaderboard(data)


def get_pvp_profile(tag: str) -> dict:
    data = load_leaderboard()
    profiles = data.setdefault("pvp_profiles", {})
    if tag not in profiles:
        profiles[tag] = {
            "tag": tag,
            "nick": f"Player{tag.replace('#', '')[:4]}",
            "wins": 0,
            "losses": 0,
            "mines_found": 0,
            "matches": 0,
            "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    return profiles[tag]


def update_pvp_nick(tag: str, nick: str) -> None:
    clean_nick = nick.strip()
    if not clean_nick:
        return
    data = load_leaderboard()
    profiles = data.setdefault("pvp_profiles", {})
    prof = profiles.setdefault(
        tag,
        {
            "tag": tag,
            "nick": clean_nick,
            "wins": 0,
            "losses": 0,
            "mines_found": 0,
            "matches": 0,
            "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
    )
    prof["nick"] = clean_nick
    prof["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    save_leaderboard(data)


def record_pvp_match(
    p1_tag: str,
    p1_nick: str,
    p2_tag: str,
    p2_nick: str,
    winner: str,
    p1_score: int,
    p2_score: int,
) -> None:
    data = load_leaderboard()
    profiles = data.setdefault("pvp_profiles", {})

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    for tag, nick, score, is_winner, is_loser in [
        (p1_tag, p1_nick, p1_score, winner == "Player 1", winner == "Player 2"),
        (p2_tag, p2_nick, p2_score, winner == "Player 2", winner == "Player 1"),
    ]:
        if not tag:
            continue
        prof = profiles.setdefault(
            tag,
            {
                "tag": tag,
                "nick": nick or f"Player{tag.replace('#', '')[:4]}",
                "wins": 0,
                "losses": 0,
                "mines_found": 0,
                "matches": 0,
                "last_seen": now_str,
            },
        )
        if nick and nick.strip():
            prof["nick"] = nick.strip()
        prof["matches"] += 1
        prof["mines_found"] += score
        prof["last_seen"] = now_str
        if is_winner:
            prof["wins"] += 1
        elif is_loser:
            prof["losses"] += 1

    entry = {
        "p1": f"{p1_nick} ({p1_tag})",
        "p2": f"{p2_nick} ({p2_tag})",
        "winner": winner,
        "score": f"{p1_score} - {p2_score}",
        "date": now_str,
    }
    data["pvp"].insert(0, entry)
    data["pvp"] = data["pvp"][:50]
    save_leaderboard(data)


def add_pvp_score(p1_name: str, p2_name: str, winner: str, p1_score: int, p2_score: int) -> None:
    record_pvp_match(
        p1_tag="",
        p1_nick=p1_name,
        p2_tag="",
        p2_nick=p2_name,
        winner=winner,
        p1_score=p1_score,
        p2_score=p2_score,
    )


def get_top_pvp_players(limit: int = 15) -> list[dict]:
    data = load_leaderboard()
    profiles = list(data.get("pvp_profiles", {}).values())

    def sort_key(p: dict) -> tuple:
        wins = p.get("wins", 0)
        losses = p.get("losses", 0)
        matches = wins + losses
        winrate = (wins / matches) if matches > 0 else 0.0
        mines = p.get("mines_found", 0)
        return (-wins, -winrate, -mines)

    profiles.sort(key=sort_key)
    return profiles[:limit]
