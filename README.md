# Mirage Casino

A real-money-balance casino app built on top of [Mirage Bank](https://github.com/Aldur13/mirage-bank). There is no separate casino wallet — the user's Mirage Bank account balance *is* their casino balance, and every wager/payout is a real ledger transaction visible in Mirage Bank's transaction history.

## Status

**Phase 1 — Foundation.** Shared auth (same JWT secret, same Neo4j database, same `User`/`Account` schema as Mirage Bank) and an atomic wager/payout ledger primitive (`backend/ledger.py`). No games yet.

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

## Endpoints (Phase 1)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | — | Create a personal account (same shape as Mirage Bank's) |
| POST | `/auth/login` | — | Returns a JWT valid on both Mirage Bank and Mirage Casino |
| GET | `/me` | Bearer | Current user profile |
| GET | `/balance` | Bearer | Current bank Account balance (the casino balance) |
