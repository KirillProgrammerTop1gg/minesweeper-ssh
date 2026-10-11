from __future__ import annotations

import asyncio
import json
import logging
import random
import sys
import uuid
from typing import Dict, List, Optional, Tuple

from minesweeper.game import GameStatus, MinesweeperGame
from minesweeper.leaderboard import get_pvp_profile, record_pvp_match, update_pvp_nick

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pvp_hub")

HUB_HOST = "127.0.0.1"
HUB_PORT = 9876


class HubClient:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.tag: str = "#----"
        self.nick: str = "Anonymous"
        self.player_num: int = 1
        self.match: Optional[Match] = None
        self.is_bot: bool = False

    async def send_json(self, data: dict) -> None:
        if self.is_bot or self.writer.is_closing():
            return
        try:
            line = json.dumps(data) + "\n"
            self.writer.write(line.encode("utf-8"))
            await self.writer.drain()
        except Exception:
            pass


class BotClient(HubClient):
    def __init__(self, match: Match, player_num: int):
        self.tag = "#BOT0"
        self.nick = "MinesweeperAI"
        self.player_num = player_num
        self.match = match
        self.is_bot = True

    async def send_json(self, data: dict) -> None:
        pass


class Match:
    def __init__(self, match_id: str, p1: HubClient, p2: HubClient, rows: int = 16, cols: int = 16, mines: int = 40):
        self.match_id = match_id
        self.p1 = p1
        self.p2 = p2
        self.p1.match = self
        self.p1.player_num = 1
        self.p2.match = self
        self.p2.player_num = 2
        self.game = MinesweeperGame(rows, cols, mines, difficulty_name="PVP 1v1", is_pvp=True)
        self.is_finished = False

    def get_opponent(self, client: HubClient) -> HubClient:
        return self.p2 if client == self.p1 else self.p1

    def serialize_grid(self) -> list[list[dict]]:
        grid_data = []
        for r in range(self.game.rows):
            row_data = []
            for c in range(self.game.cols):
                cell = self.game.grid[r][c]
                row_data.append({
                    "r": cell.is_revealed,
                    "f": cell.is_flagged,
                    "m": cell.adjacent_mines if cell.is_revealed else 0,
                    "mine": cell.is_mine if cell.is_revealed else False,
                    "det": cell.is_detonated,
                    "p": cell.found_by_player,
                })
            row_data.append(row_data)
        return grid_data

    async def broadcast_state(self, last_action: str = "") -> None:
        cells_state = []
        for r in range(self.game.rows):
            for c in range(self.game.cols):
                cell = self.game.grid[r][c]
                if cell.is_revealed or cell.is_flagged or cell.is_detonated or cell.found_by_player:
                    cells_state.append((
                        r,
                        c,
                        cell.is_revealed,
                        cell.is_flagged,
                        cell.adjacent_mines,
                        cell.found_by_player,
                        cell.is_detonated,
                    ))

        state_msg = {
            "type": "state",
            "status": self.game.status.value,
            "current_player": self.game.current_player,
            "p1_score": self.game.player_scores[1],
            "p2_score": self.game.player_scores[2],
            "cells": cells_state,
            "last_action": last_action,
            "winner": self.game.pvp_winner,
        }
        await self.p1.send_json(state_msg)
        await self.p2.send_json(state_msg)

    async def end_match(self, winner_str: str) -> None:
        if self.is_finished:
            return
        self.is_finished = True
        self.game.status = GameStatus.WON
        self.game.pvp_winner = winner_str

        p1_score = self.game.player_scores[1]
        p2_score = self.game.player_scores[2]

        record_pvp_match(
            p1_tag=self.p1.tag,
            p1_nick=self.p1.nick,
            p2_tag=self.p2.tag,
            p2_nick=self.p2.nick,
            winner=winner_str,
            p1_score=p1_score,
            p2_score=p2_score,
        )

        over_msg = {
            "type": "game_over",
            "winner": winner_str,
            "p1_score": p1_score,
            "p2_score": p2_score,
        }
        logger.info(f"Match ended [{self.match_id}]: Winner {winner_str} ({p1_score} - {p2_score})")
        await self.p1.send_json(over_msg)
        await self.p2.send_json(over_msg)

    def bot_think_and_move(self) -> Tuple[int, int]:
        unrevealed = []
        for r in range(self.game.rows):
            for c in range(self.game.cols):
                cell = self.game.grid[r][c]
                if not cell.is_revealed and not cell.is_flagged:
                    unrevealed.append((r, c))

        if not unrevealed:
            return 0, 0

        for r in range(self.game.rows):
            for c in range(self.game.cols):
                cell = self.game.grid[r][c]
                if cell.is_revealed and cell.adjacent_mines > 0:
                    neighbors = self.game.get_neighbors(r, c)
                    unrev_neighbors = [
                        (nr, nc) for nr, nc in neighbors
                        if not self.game.grid[nr][nc].is_revealed and not self.game.grid[nr][nc].is_flagged
                    ]
                    found_neighbors = [
                        (nr, nc) for nr, nc in neighbors
                        if self.game.grid[nr][nc].found_by_player is not None
                    ]
                    needed_mines = cell.adjacent_mines - len(found_neighbors)
                    if len(unrev_neighbors) == needed_mines and needed_mines > 0:
                        return unrev_neighbors[0]

        return random.choice(unrevealed)


class PVPHubServer:
    def __init__(self):
        self.waiting_queue: List[HubClient] = []
        self.matches: Dict[str, Match] = {}

    async def start(self, host: str = HUB_HOST, port: int = HUB_PORT) -> None:
        server = await asyncio.start_server(self.handle_connection, host, port)
        addr = server.sockets[0].getsockname()
        logger.info(f"PVP Matchmaking Hub serving on {addr}")
        async with server:
            await server.serve_forever()

    async def handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        client = HubClient(reader, writer)
        try:
            while not reader.at_eof():
                line = await reader.readline()
                if not line:
                    break
                try:
                    data = json.loads(line.decode("utf-8").strip())
                    await self.process_message(client, data)
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            logger.debug(f"Connection error: {e}")
        finally:
            await self.handle_disconnect(client)

    async def process_message(self, client: HubClient, msg: dict) -> None:
        mtype = msg.get("type")

        if mtype == "join_queue":
            client.tag = msg.get("tag", "#----")
            client.nick = msg.get("nick", "Anonymous")
            logger.info(f"Player joined queue: {client.nick} ({client.tag})")
            if client in self.waiting_queue:
                return

            if self.waiting_queue:
                p1 = self.waiting_queue.pop(0)
                await self.create_match(p1, client)
            else:
                self.waiting_queue.append(client)
                await client.send_json({
                    "type": "queue_status",
                    "waiting": len(self.waiting_queue),
                    "message": "Searching for opponent online...",
                })

        elif mtype == "play_bot":
            if client in self.waiting_queue:
                self.waiting_queue.remove(client)
            client.player_num = 1
            match_id = uuid.uuid4().hex[:8]
            bot = BotClient(None, 2)
            match = Match(match_id, client, bot)
            bot.match = match
            self.matches[match_id] = match

            await client.send_json({
                "type": "match_start",
                "match_id": match_id,
                "player_num": 1,
                "rows": match.game.rows,
                "cols": match.game.cols,
                "mines": match.game.total_mines,
                "opponent_tag": bot.tag,
                "opponent_nick": bot.nick,
                "my_tag": client.tag,
                "my_nick": client.nick,
            })
            await match.broadcast_state("Game started vs AI Bot!")

        elif mtype == "cancel_queue":
            if client in self.waiting_queue:
                self.waiting_queue.remove(client)
            await client.send_json({"type": "queue_cancelled"})

        elif mtype == "move":
            match = client.match
            if not match or match.is_finished:
                return
            if match.game.current_player != client.player_num:
                return

            action = msg.get("action", "reveal")
            r = int(msg.get("r", 0))
            c = int(msg.get("c", 0))

            if action == "reveal":
                success, desc = match.game.reveal(r, c)
            elif action == "flag":
                success, desc = match.game.toggle_flag(r, c)
            elif action == "chord":
                success, desc = match.game.chord(r, c)
            else:
                return

            await match.broadcast_state(desc)

            if match.game.status == GameStatus.WON:
                winner = match.game.pvp_winner or "Player 1"
                await match.end_match(winner)
                return

            if match.p2.is_bot and match.game.current_player == 2 and not match.is_finished:
                asyncio.create_task(self.bot_turn(match))

        elif mtype == "cursor":
            match = client.match
            if match and not match.is_finished:
                opp = match.get_opponent(client)
                await opp.send_json({
                    "type": "opponent_cursor",
                    "r": msg.get("r", 0),
                    "c": msg.get("c", 0),
                })

        elif mtype == "submit_nick":
            new_nick = msg.get("nick", "").strip()
            if new_nick and client.tag:
                client.nick = new_nick
                update_pvp_nick(client.tag, new_nick)
                profile = get_pvp_profile(client.tag)
                await client.send_json({"type": "profile_updated", "profile": profile})

    async def bot_turn(self, match: Match) -> None:
        await asyncio.sleep(0.6)
        while match.game.current_player == 2 and not match.is_finished:
            br, bc = match.bot_think_and_move()
            await match.p1.send_json({"type": "opponent_cursor", "r": br, "c": bc})
            await asyncio.sleep(0.3)
            success, desc = match.game.reveal(br, bc)
            await match.broadcast_state(f"AI Bot: {desc}")
            if match.game.status == GameStatus.WON:
                winner = match.game.pvp_winner or "Player 2"
                await match.end_match(winner)
                break
            if match.game.current_player == 2:
                await asyncio.sleep(0.5)

    async def create_match(self, p1: HubClient, p2: HubClient) -> None:
        match_id = uuid.uuid4().hex[:8]
        match = Match(match_id, p1, p2)
        self.matches[match_id] = match
        logger.info(f"Match created [{match_id}]: {p1.nick} ({p1.tag}) vs {p2.nick} ({p2.tag})")

        await p1.send_json({
            "type": "match_start",
            "match_id": match_id,
            "player_num": 1,
            "rows": match.game.rows,
            "cols": match.game.cols,
            "mines": match.game.total_mines,
            "opponent_tag": p2.tag,
            "opponent_nick": p2.nick,
            "my_tag": p1.tag,
            "my_nick": p1.nick,
        })
        await p2.send_json({
            "type": "match_start",
            "match_id": match_id,
            "player_num": 2,
            "rows": match.game.rows,
            "cols": match.game.cols,
            "mines": match.game.total_mines,
            "opponent_tag": p1.tag,
            "opponent_nick": p1.nick,
            "my_tag": p2.tag,
            "my_nick": p2.nick,
        })
        await match.broadcast_state("Match found! Player 1 goes first.")

    async def handle_disconnect(self, client: HubClient) -> None:
        if client in self.waiting_queue:
            self.waiting_queue.remove(client)

        match = client.match
        if match and not match.is_finished:
            opp = match.get_opponent(client)
            winner = f"Player {opp.player_num}"
            await opp.send_json({
                "type": "opponent_disconnected",
                "message": f"Opponent ({client.nick}) disconnected! You win by forfeit!",
                "winner": winner,
            })
            await match.end_match(winner)

        try:
            client.writer.close()
            await client.writer.wait_closed()
        except Exception:
            pass


def run_hub() -> None:
    hub = PVPHubServer()
    try:
        asyncio.run(hub.start())
    except KeyboardInterrupt:
        logger.info("Hub stopped by user.")


if __name__ == "__main__":
    run_hub()
