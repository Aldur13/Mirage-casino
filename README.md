# Mirage Casino

A real-money-balance casino app built on top of [Mirage Bank](https://github.com/Aldur13/mirage-bank). There is no separate casino wallet — the user's Mirage Bank account balance *is* their casino balance, and every wager/payout is a real ledger transaction visible in Mirage Bank's transaction history.

## Status

**Phase 1 — Foundation.** Shared auth (same JWT secret, same Neo4j database, same `User`/`Account` schema as Mirage Bank) and an atomic wager/payout ledger primitive (`backend/ledger.py`).

**Phase 2 — Crash.** Server-authoritative, provably-fair Crash game over WebSockets (`backend/games/crash/`). Bots fill quiet rounds using their own in-memory play-money — they never call `ledger.py` and are always flagged `is_bot` in every payload.

**Phase 3 — Mines.** Turn-based, REST-only (`backend/games/mines/`). Mine positions are generated server-side and never sent to the client until the round ends; multiplier is the standard hypergeometric-odds formula scaled by a house edge.

**Phase 4 — Blackjack.** Full REST state machine (`backend/games/blackjack/`): hit/stand/double/split/insurance, natural blackjack (3:2) and push detection, dealer stands on all 17s. Each hand and side bet uses its own ledger `round_id` suffix (e.g. `{round_id}:split`, `{round_id}:double`) so split/double/insurance wagers can't collide with each other's idempotency keys.

## Stack

Same as Mirage Bank, by design — this is one ecosystem sharing one database:

| Layer | Technology |
|---|---|
| Backend | Python 3.13 + FastAPI + Uvicorn |
| Database | The **same** Neo4j Aura instance as Mirage Bank |
| Auth | JWT (HS256) signed with the **same secret** as Mirage Bank + bcrypt passwords |
| Frontend | Static HTML/CSS/JS placeholder (intentionally plain — real UI comes with each game) |

## Why a separate repo but the same database?

Mirage Bank and Mirage Casino are independently deployable apps that must recognize the *same* users and money. Rather than importing code across two separate git repos (fragile for independent deploys), the small stable primitives that must interoperate byte-for-byte — JWT encode/decode, password hashing, the Neo4j driver, registration/login Cypher — are vendored into this repo from `mirage-bank/backend/`. See the header comments in `backend/auth.py`, `backend/dependencies.py`, and `backend/routes/auth.py` for what must stay in sync and why.

## Local development

**Requirements:** Python 3.13, packages in `backend/requirements.txt`, and the **same** Neo4j Aura instance Mirage Bank uses.

```
cp .env.example .env
# Fill in NEO4J_* and JWT_SECRET with the exact same values as mirage-bank/.env

cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8914
```

Open **http://localhost:8914** for the placeholder frontend, or `http://localhost:8914/docs` for the interactive API docs.

## Ledger

`backend/ledger.py` is the only module allowed to move money for games:

- `place_wager(user_id, amount_cents, game, round_id)` — debits the user's bank Account into the shared Treasury account. Rejects (raises `InsufficientFundsError`) on insufficient balance, inactive account, or an already-placed wager for that round.
- `settle_payout(user_id, amount_cents, game, round_id)` — credits the user's bank Account from Treasury. Idempotent: a retried call for the same `(game, round_id, user_id)` is a no-op, guarded by a Neo4j unique constraint — not a race-prone read-then-write check.

Every future game (Crash, Blackjack, Mines, Crates) calls these two functions instead of writing its own Cypher against the ledger.

In non-production (`APP_ENV != production`), `POST /account/_dev/wager` and `POST /account/_dev/payout` expose these directly for manual/integration testing.

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | — | Create a personal account (same shape as Mirage Bank's) |
| POST | `/auth/login` | — | Returns a JWT valid on both Mirage Bank and Mirage Casino |
| GET | `/me` | Bearer | Current user profile |
| GET | `/balance` | Bearer | Current bank Account balance (the casino balance) |
| GET | `/games/crash/state` | — | Snapshot of the current round |
| GET | `/games/crash/history` | — | Last 20 crashed rounds |
| GET | `/games/crash/verify/{round_id}` | — | Recomputes the crash point from the revealed seed to prove it's provably fair |
| WS | `/games/crash/ws?token=<jwt>` | optional | Live round updates; token required to place bets/cash out, omit to spectate |

## Crash game

One shared round for every connected client, driven by a single `asyncio` loop (`backend/games/crash/round_manager.py`):

1. **Betting** (7s) — bets accepted, room topped up with bots if real attendance is low (`backend/games/crash/bots.py`).
2. **Running** — multiplier climbs `e^(rate·t)`, broadcast every 100ms. Manual cashout settles at whatever the server's multiplier is at that instant; auto-cashout settles the moment the live multiplier reaches the target. Both paths call `ledger.settle_payout`, so a duplicate/retried cashout can't double-pay.
3. **Crashed** — `server_seed` revealed, any still-active bets lose (wager was already taken), pause, next round.

The crash point is generated **before** betting closes (`backend/games/crash/provably_fair.py`): the server publishes `sha256(server_seed)` immediately and reveals `server_seed` only after the crash, so nobody — including the house — can change the outcome after seeing who bet what. `GET /games/crash/verify/{round_id}` lets anyone recompute it independently.

This assumes a single server process — scaling to multiple workers would need a shared pub/sub (e.g. Redis) to keep the round in sync, which isn't implemented yet.
