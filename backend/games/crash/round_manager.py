"""The Crash game engine: one asyncio background task drives a shared
round for every connected client (the "shared live round" requirement).

Neo4j access (repository.py, ledger.py) uses the synchronous driver that
the rest of this codebase already uses (see database.py) — synchronous
network I/O would normally block the asyncio event loop, so every call
into repository/ledger from here goes through asyncio.to_thread() to run
it off-loop. That keeps the 100ms tick loop and WebSocket broadcasts
responsive without needing a second (async) Neo4j driver instance.
"""
import asyncio
import math
import random
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import ledger
from games.crash import provably_fair, repository
from games.crash.bots import BotPlayer, maybe_spawn_bots
from games.crash.connection_manager import manager

BETTING_DURATION_SECONDS = 7
BOT_SPAWN_AT_SECONDS = 3  # into the betting window
TICK_INTERVAL_SECONDS = 0.1
GROWTH_RATE = math.log(2) / 5  # multiplier reaches ~2.00x around t=5s
POST_CRASH_DELAY_SECONDS = 3
MIN_BET_CENTS = 100


class BetRejectedError(Exception):
    """Raised for any bet/cashout that fails validation — the WS handler
    turns this into an error frame back to that one client."""


@dataclass
class BetRecord:
    id: str
    user_id: Optional[str]  # None for bots
    display_name: str
    amount_cents: int
    auto_cashout_multiplier: Optional[float]
    is_bot: bool
    bot_ref: Optional[BotPlayer] = None
    status: str = "active"  # active | cashed_out | busted
    cashout_multiplier: Optional[float] = None
    payout_cents: Optional[int] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RoundManager:
    def __init__(self):
        self.status = "idle"  # idle | betting | running | crashed
        self.round_id: Optional[str] = None
        self.nonce: Optional[int] = None
        self.server_seed: Optional[str] = None
        self.server_seed_hash: Optional[str] = None
        self.crash_point: Optional[float] = None
        self.betting_closes_at: Optional[str] = None
        self.current_multiplier: float = 1.0
        self.bets: dict[str, BetRecord] = {}  # key = user_id or bot.id
        self._lock = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None
        self._running_started_monotonic: Optional[float] = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()

    def public_state(self) -> dict:
        bets = [
            {
                "display_name": b.display_name,
                "amount_cents": b.amount_cents,
                "auto_cashout_multiplier": b.auto_cashout_multiplier,
                "cashout_multiplier": b.cashout_multiplier,
                "payout_cents": b.payout_cents,
                "is_bot": b.is_bot,
            }
            for b in self.bets.values()
        ]
        return {
            "round_id": self.round_id,
            "status": self.status,
            "server_seed_hash": self.server_seed_hash,
            "nonce": self.nonce,
            "betting_closes_at": self.betting_closes_at,
            "current_multiplier": self.current_multiplier if self.status == "running" else None,
            "crash_point": self.crash_point if self.status == "crashed" else None,
            "server_seed": self.server_seed if self.status == "crashed" else None,
            "bets": bets,
        }

    async def _loop(self) -> None:
        while True:
            try:
                await self._betting_phase()
                await self._running_phase()
                await self._crashed_phase()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # a transient Neo4j hiccup shouldn't kill the game forever
                await manager.broadcast({"type": "error", "message": "round loop error, restarting"})
                print(f"[crash] round loop error: {exc!r}")
                await asyncio.sleep(1)

    # ── Betting phase ───────────────────────────────────────────────

    async def _betting_phase(self) -> None:
        nonce = await asyncio.to_thread(repository.next_nonce)
        server_seed = provably_fair.generate_server_seed()
        server_seed_hash = provably_fair.commit_hash(server_seed)
        crash_point = provably_fair.crash_point_for(server_seed, nonce)
        round_id = str(uuid.uuid4())
        started_at = _now_iso()
        closes_at = (datetime.now(timezone.utc) + timedelta(seconds=BETTING_DURATION_SECONDS)).isoformat()

        async with self._lock:
            self.status = "betting"
            self.round_id = round_id
            self.nonce = nonce
            self.server_seed = server_seed
            self.server_seed_hash = server_seed_hash
            self.crash_point = crash_point
            self.current_multiplier = 1.0
            self.bets = {}
            self.betting_closes_at = closes_at

        await asyncio.to_thread(
            repository.create_round, round_id, nonce, server_seed, server_seed_hash,
            crash_point, started_at,
        )
        await manager.broadcast({
            "type": "betting_open", "round_id": round_id, "nonce": nonce,
            "server_seed_hash": server_seed_hash, "betting_closes_at": closes_at,
        })

        await asyncio.sleep(BOT_SPAWN_AT_SECONDS)

        real_count = sum(1 for b in self.bets.values() if not b.is_bot)
        for bot in maybe_spawn_bots(real_count):
            await self._place_bot_bet(bot)
            await asyncio.sleep(random.uniform(0.1, 0.5))

        remaining = BETTING_DURATION_SECONDS - BOT_SPAWN_AT_SECONDS
        if remaining > 0:
            await asyncio.sleep(remaining)

    # ── Running phase ───────────────────────────────────────────────

    async def _running_phase(self) -> None:
        async with self._lock:
            self.status = "running"
        await asyncio.to_thread(repository.mark_round_running, self.round_id, _now_iso())
        await manager.broadcast({"type": "round_started", "round_id": self.round_id})

        self._running_started_monotonic = time.monotonic()
        while True:
            elapsed = time.monotonic() - self._running_started_monotonic
            multiplier = math.exp(GROWTH_RATE * elapsed)

            if multiplier >= self.crash_point:
                self.current_multiplier = self.crash_point
                break

            self.current_multiplier = round(multiplier, 2)
            await manager.broadcast({"type": "tick", "multiplier": self.current_multiplier})
            await self._resolve_auto_cashouts()
            await asyncio.sleep(TICK_INTERVAL_SECONDS)

    async def _resolve_auto_cashouts(self) -> None:
        targets = [
            key for key, bet in self.bets.items()
            if bet.status == "active" and bet.auto_cashout_multiplier is not None
            and bet.auto_cashout_multiplier <= self.current_multiplier
        ]
        for key in targets:
            await self._settle_cashout(key, self.current_multiplier)

    # ── Crashed phase ───────────────────────────────────────────────

    async def _crashed_phase(self) -> None:
        async with self._lock:
            self.status = "crashed"
        crashed_at = _now_iso()
        await asyncio.to_thread(repository.mark_round_crashed, self.round_id, crashed_at)

        for key, bet in list(self.bets.items()):
            if bet.status == "active":
                bet.status = "busted"
                await asyncio.to_thread(repository.resolve_bet, bet.id, "busted", None, None)

        await manager.broadcast({
            "type": "crashed", "round_id": self.round_id, "nonce": self.nonce,
            "crash_point": self.crash_point, "server_seed": self.server_seed,
        })
        await asyncio.sleep(POST_CRASH_DELAY_SECONDS)

    # ── Player actions (called from the WebSocket route) ───────────

    async def place_bet(self, user_id: str, display_name: str, amount_cents: int,
                         auto_cashout_multiplier: Optional[float]) -> None:
        if self.status != "betting":
            raise BetRejectedError("Betting is closed for this round")
        if amount_cents < MIN_BET_CENTS:
            raise BetRejectedError(f"Minimum bet is {MIN_BET_CENTS} cents")
        if user_id in self.bets:
            raise BetRejectedError("You already placed a bet this round")

        try:
            await asyncio.to_thread(ledger.place_wager, user_id, amount_cents, "crash", self.round_id)
        except ledger.InsufficientFundsError as exc:
            raise BetRejectedError(str(exc)) from exc

        bet_id = str(uuid.uuid4())
        record = BetRecord(
            id=bet_id, user_id=user_id, display_name=display_name, amount_cents=amount_cents,
            auto_cashout_multiplier=auto_cashout_multiplier, is_bot=False,
        )
        self.bets[user_id] = record

        await asyncio.to_thread(
            repository.create_bet, bet_id, self.round_id, user_id, display_name,
            amount_cents, auto_cashout_multiplier, False, _now_iso(),
        )
        await manager.broadcast({
            "type": "bet_placed", "display_name": display_name, "amount_cents": amount_cents,
            "auto_cashout_multiplier": auto_cashout_multiplier, "is_bot": False,
        })

    async def cashout(self, user_id: str) -> None:
        bet = self.bets.get(user_id)
        if bet is None or bet.status != "active":
            raise BetRejectedError("No active bet to cash out")
        if self.status != "running":
            raise BetRejectedError("Round is not currently running")
        await self._settle_cashout(user_id, self.current_multiplier)

    async def _place_bot_bet(self, bot: BotPlayer) -> None:
        record = BetRecord(
            id=str(uuid.uuid4()), user_id=None, display_name=bot.display_name,
            amount_cents=bot.amount_cents, auto_cashout_multiplier=bot.auto_cashout_multiplier,
            is_bot=True, bot_ref=bot,
        )
        self.bets[bot.id] = record

        await asyncio.to_thread(
            repository.create_bet, record.id, self.round_id, None, bot.display_name,
            bot.amount_cents, bot.auto_cashout_multiplier, True, _now_iso(),
        )
        await manager.broadcast({
            "type": "bet_placed", "display_name": bot.display_name, "amount_cents": bot.amount_cents,
            "auto_cashout_multiplier": bot.auto_cashout_multiplier, "is_bot": True,
        })

    async def _settle_cashout(self, key: str, multiplier: float) -> None:
        async with self._lock:
            bet = self.bets.get(key)
            if bet is None or bet.status != "active":
                return  # already settled by a concurrent auto-cashout/manual request
            bet.status = "cashed_out"
            bet.cashout_multiplier = multiplier
            bet.payout_cents = round(bet.amount_cents * multiplier)

            if bet.is_bot:
                bet.bot_ref.bankroll_cents += bet.payout_cents  # virtual only, never ledger.py
            else:
                await asyncio.to_thread(
                    ledger.settle_payout, bet.user_id, bet.payout_cents, "crash", self.round_id,
                )

            await asyncio.to_thread(
                repository.resolve_bet, bet.id, "cashed_out", multiplier, bet.payout_cents,
            )

        await manager.broadcast({
            "type": "cashed_out", "display_name": bet.display_name, "multiplier": multiplier,
            "payout_cents": bet.payout_cents, "is_bot": bet.is_bot,
        })


round_manager = RoundManager()
