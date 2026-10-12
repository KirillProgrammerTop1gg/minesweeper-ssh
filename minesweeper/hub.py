from __future__ import annotations

import asyncio
import json
import logging
import random
import time
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

    async def send_json(self, data: dict) -> None:
        if self.writer.is_closing():
            return
        try:
            line = json.dumps(data) + "\n"
            self.writer.write(line.encode("utf-8"))
            await self.writer.drain()
        except Exception:
            pass


class Match:
    def __init__(
        self,
        match_id: str,
        p1: HubClient,
        p2: HubClient,
        rows: int = 16,
        cols: int = 16,
        mines: int = 40,
    ):
        self.match_id = match_id
        self.p1 = p1
        self.p2 = p2
        self.p1.match = self
        self.p1.player_num = 1
        self.p2.match = self
        self.p2.player_num = 2
        self.rows = rows
        self.cols = cols
        self.mines = mines

        all_cells = [(r, c) for r in range(rows) for c in range(cols)]
        safe_start = {(0, 0), (0, 1), (1, 0), (1, 1)}
        available_cells = [c for c in all_cells if c not in safe_start]
        self.preset_mines = set(random.sample(available_cells, mines))

        self.p1_game = MinesweeperGame(
            rows, cols, mines, difficulty_name="PVP Race", is_pvp=False, preset_mines=set(self.preset_mines)
        )
        self.p2_game = MinesweeperGame(
            rows, cols, mines, difficulty_name="PVP Race", is_pvp=False, preset_mines=set(self.preset_mines)
        )

        self.p1_cursor = (0, 0)
        self.p2_cursor = (0, 0)
        self.is_finished = False
        self.last_move_time = time.time()
        self.p1_last_active = time.time()
        self.p2_last_active = time.time()
        self.p1_timed_out = False
        self.p2_timed_out = False
        self.telemetry_task: Optional[asyncio.Task] = None

    def get_game(self, client: HubClient) -> MinesweeperGame:
        return self.p1_game if client == self.p1 else self.p2_game

    def get_opponent_game(self, client: HubClient) -> MinesweeperGame:
        return self.p2_game if client == self.p1 else self.p1_game

    def get_opponent(self, client: HubClient) -> HubClient:
        return self.p2 if client == self.p1 else self.p1

    def _extract_cells(self, game: MinesweeperGame) -> list:
        cells_state = []
        is_over = game.status in (GameStatus.WON, GameStatus.LOST)
        for r in range(game.rows):
            for c in range(game.cols):
                cell = game.grid[r][c]
                if cell.is_revealed or cell.is_flagged or cell.is_detonated or cell.is_false_flag or (is_over and cell.is_mine):
                    cells_state.append((
                        r,
                        c,
                        cell.is_revealed,
                        cell.is_flagged,
                        cell.adjacent_mines,
                        cell.is_detonated,
                        cell.is_false_flag,
                        cell.is_mine if (cell.is_revealed or is_over) else False,
                    ))
        return cells_state

    async def send_player_state(self, client: HubClient, last_action: str = "") -> None:
        my_game = self.get_game(client)
        opp_game = self.get_opponent_game(client)
        opp_client = self.get_opponent(client)

        now = time.time()
        p1_idle = now - self.p1_last_active
        p2_idle = now - self.p2_last_active
        p1_timeout = max(0, int(30 - p1_idle))
        p2_timeout = max(0, int(30 - p2_idle))
        is_p1 = (client == self.p1)

        state_msg = {
            "type": "state",
            "cells": self._extract_cells(my_game),
            "my_score": my_game.score,
            "my_time": my_game.get_elapsed_time(),
            "my_cleared": my_game.revealed_count,
            "my_total_safe": my_game.safe_cells_total,
            "my_flags": my_game.flags_count,
            "my_status": my_game.status.value,
            "my_timeout": p1_timeout if is_p1 else p2_timeout,
            "my_timed_out": self.p1_timed_out if is_p1 else self.p2_timed_out,
            "opp_nick": opp_client.nick,
            "opp_tag": opp_client.tag,
            "opp_score": opp_game.score,
            "opp_time": opp_game.get_elapsed_time(),
            "opp_cleared": opp_game.revealed_count,
            "opp_total_safe": opp_game.safe_cells_total,
            "opp_status": opp_game.status.value,
            "opp_timeout": p2_timeout if is_p1 else p1_timeout,
            "opp_timed_out": self.p2_timed_out if is_p1 else self.p1_timed_out,
            "last_action": last_action,
        }
        await client.send_json(state_msg)

    async def broadcast_state(self, p1_action: str = "", p2_action: str = "") -> None:
        await self.send_player_state(self.p1, p1_action)
        await self.send_player_state(self.p2, p2_action)

    async def check_match_completion(self) -> None:
        if self.is_finished:
            return

        now = time.time()
        p1_timed_out_now = False
        p2_timed_out_now = False

        if (
            not self.p1_timed_out
            and self.p1_game.status in (GameStatus.PLAYING, GameStatus.READY)
            and not self.is_finished
        ):
            if now - self.p1_last_active >= 30.0:
                self.p1_timed_out = True
                self.p1_game.status = GameStatus.LOST
                self.p1_game.end_time = now
                p1_timed_out_now = True
                logger.info(f"Match [{self.match_id}]: Player 1 timed out (30s inactivity)")

        if (
            not self.p2_timed_out
            and self.p2_game.status in (GameStatus.PLAYING, GameStatus.READY)
            and not self.is_finished
        ):
            if now - self.p2_last_active >= 30.0:
                self.p2_timed_out = True
                self.p2_game.status = GameStatus.LOST
                self.p2_game.end_time = now
                p2_timed_out_now = True
                logger.info(f"Match [{self.match_id}]: Player 2 timed out (30s inactivity)")

        if p1_timed_out_now:
            await self.send_player_state(self.p1, last_action="Timeout! 30 seconds of inactivity — Game Over!")
            await self.send_player_state(self.p2, last_action=f"{self.p1.nick} timed out (30s inactivity)!")
        elif p2_timed_out_now:
            await self.send_player_state(self.p2, last_action="Timeout! 30 seconds of inactivity — Game Over!")
            await self.send_player_state(self.p1, last_action=f"{self.p2.nick} timed out (30s inactivity)!")

        p1_done = self.p1_game.status in (GameStatus.WON, GameStatus.LOST)
        p2_done = self.p2_game.status in (GameStatus.WON, GameStatus.LOST)

        if (self.p1_timed_out or self.p2_timed_out) or (p1_done and p2_done):
            await self._finalize_match()

    async def _finalize_match(self) -> None:
        if self.is_finished:
            return

        p1_score = self.p1_game.score
        p2_score = self.p2_game.score
        p1_time = self.p1_game.get_elapsed_time()
        p2_time = self.p2_game.get_elapsed_time()

        if self.p1_timed_out and self.p2_timed_out:
            if p1_score > p2_score:
                winner = "Player 1"
                winner_nick = self.p1.nick
            elif p2_score > p1_score:
                winner = "Player 2"
                winner_nick = self.p2.nick
            else:
                winner = "Draw"
                winner_nick = "Draw"
        elif self.p1_timed_out and not self.p2_timed_out:
            if self.p2_game.status == GameStatus.LOST:
                if p1_score > p2_score:
                    winner = "Player 1"
                    winner_nick = self.p1.nick
                elif p2_score > p1_score:
                    winner = "Player 2"
                    winner_nick = self.p2.nick
                else:
                    winner = "Player 2"
                    winner_nick = self.p2.nick
            else:
                winner = "Player 2"
                winner_nick = self.p2.nick
        elif self.p2_timed_out and not self.p1_timed_out:
            if self.p1_game.status == GameStatus.LOST:
                if p2_score > p1_score:
                    winner = "Player 2"
                    winner_nick = self.p2.nick
                elif p1_score > p2_score:
                    winner = "Player 1"
                    winner_nick = self.p1.nick
                else:
                    winner = "Player 1"
                    winner_nick = self.p1.nick
            else:
                winner = "Player 1"
                winner_nick = self.p1.nick
        else:
            if p1_score > p2_score:
                winner = "Player 1"
                winner_nick = self.p1.nick
            elif p2_score > p1_score:
                winner = "Player 2"
                winner_nick = self.p2.nick
            else:
                if p1_time < p2_time:
                    winner = "Player 1"
                    winner_nick = self.p1.nick
                elif p2_time < p1_time:
                    winner = "Player 2"
                    winner_nick = self.p2.nick
                else:
                    winner = "Draw"
                    winner_nick = "Draw"

        await self.end_match(winner, winner_nick)

    async def end_match(self, winner: str, winner_nick: str) -> None:
        if self.is_finished:
            return
        self.is_finished = True

        if self.telemetry_task and not self.telemetry_task.done():
            self.telemetry_task.cancel()

        await self.broadcast_state()

        p1_score = self.p1_game.score
        p2_score = self.p2_game.score

        record_pvp_match(
            p1_tag=self.p1.tag,
            p1_nick=self.p1.nick,
            p2_tag=self.p2.tag,
            p2_nick=self.p2.nick,
            winner=winner,
            p1_score=p1_score,
            p2_score=p2_score,
        )

        over_msg = {
            "type": "game_over",
            "winner": winner,
            "winner_nick": winner_nick,
            "p1_nick": self.p1.nick,
            "p1_tag": self.p1.tag,
            "p1_score": p1_score,
            "p1_time": self.p1_game.get_elapsed_time(),
            "p1_status": self.p1_game.status.value,
            "p1_timed_out": self.p1_timed_out,
            "p2_nick": self.p2.nick,
            "p2_tag": self.p2.tag,
            "p2_score": p2_score,
            "p2_time": self.p2_game.get_elapsed_time(),
            "p2_status": self.p2_game.status.value,
            "p2_timed_out": self.p2_timed_out,
        }
        logger.info(
            f"Match ended [{self.match_id}]: Winner {winner_nick} ({p1_score} - {p2_score})"
        )
        await self.p1.send_json(over_msg)
        await self.p2.send_json(over_msg)

    async def start_telemetry_loop(self) -> None:
        try:
            while not self.is_finished:
                await asyncio.sleep(1.0)
                if self.is_finished:
                    break
                await self.check_match_completion()
                if not self.is_finished:
                    await self.broadcast_state()
        except asyncio.CancelledError:
            pass

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

        elif mtype == "cancel_queue":
            if client in self.waiting_queue:
                self.waiting_queue.remove(client)
            await client.send_json({"type": "queue_cancelled"})

        elif mtype == "move":
            match = client.match
            if not match or match.is_finished:
                return

            game = match.get_game(client)
            if game.status in (GameStatus.WON, GameStatus.LOST):
                return

            action = msg.get("action", "reveal")
            r = int(msg.get("r", 0))
            c = int(msg.get("c", 0))

            if action == "reveal":
                success, desc = game.reveal(r, c)
            elif action == "flag":
                success, desc = game.toggle_flag(r, c)
            elif action == "chord":
                success, desc = game.chord(r, c)
            else:
                return

            now = time.time()
            if client == match.p1:
                match.p1_last_active = now
            else:
                match.p2_last_active = now
            match.last_move_time = now

            if game.status == GameStatus.LOST:
                desc = "BOOM! You detonated a mine! Waiting for opponent..."
            elif game.status == GameStatus.WON:
                desc = "VICTORY! All safe cells cleared! Waiting for opponent..."

            await match.send_player_state(client, last_action=desc)
            opp = match.get_opponent(client)
            await match.send_player_state(opp)

            await match.check_match_completion()

        elif mtype == "cursor":
            match = client.match
            if match and not match.is_finished:
                now = time.time()
                if client == match.p1:
                    match.p1_last_active = now
                else:
                    match.p2_last_active = now
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

    async def create_match(self, p1: HubClient, p2: HubClient) -> None:
        match_id = uuid.uuid4().hex[:8]
        match = Match(match_id, p1, p2)
        self.matches[match_id] = match
        logger.info(f"Match created [{match_id}]: {p1.nick} ({p1.tag}) vs {p2.nick} ({p2.tag})")

        await p1.send_json({
            "type": "match_start",
            "match_id": match_id,
            "player_num": 1,
            "rows": match.rows,
            "cols": match.cols,
            "mines": match.mines,
            "opponent_tag": p2.tag,
            "opponent_nick": p2.nick,
            "my_tag": p1.tag,
            "my_nick": p1.nick,
        })
        await p2.send_json({
            "type": "match_start",
            "match_id": match_id,
            "player_num": 2,
            "rows": match.rows,
            "cols": match.cols,
            "mines": match.mines,
            "opponent_tag": p1.tag,
            "opponent_nick": p1.nick,
            "my_tag": p2.tag,
            "my_nick": p2.nick,
        })
        await match.broadcast_state("PVP Race started! Clear safe cells to score.")
        match.telemetry_task = asyncio.create_task(match.start_telemetry_loop())

    async def handle_disconnect(self, client: HubClient) -> None:
        if client in self.waiting_queue:
            self.waiting_queue.remove(client)

        match = client.match
        if match and not match.is_finished:
            opp = match.get_opponent(client)
            winner = f"Player {opp.player_num}"
            await opp.send_json({
                "type": "opponent_disconnected",
                "message": f"Opponent ({client.nick}) disconnected! Victory by forfeit!",
                "winner": winner,
            })
            await match.end_match(winner, opp.nick)

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
