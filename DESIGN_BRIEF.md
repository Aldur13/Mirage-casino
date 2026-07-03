# Mirage Casino — UI Design Brief

Paste this whole document into Claude Designer as the brief for the Mirage Casino frontend. It contains everything needed to design every screen with no follow-up questions: product context, the full screen list, and the complete API contract each screen is built against.

## Product

Mirage Casino is a real-money-balance casino web app. There is no separate casino wallet — the user's bank account balance (shared with a sibling app, "Mirage Bank") **is** the casino balance. Every bet and payout is a real transaction. This should read as a **premium, trustworthy, real-money product** — not a cartoonish free-to-play game. Think: dark, confident, slightly luxe (the name "Mirage" suggests desert/oasis/neon-at-night — a warm gold/amber accent on near-black is a reasonable direction, but pick what reads best). Avoid anything that looks like a mobile gacha game skin.

Four games: **Crash** (shared live multiplayer round), **Mines** (solo grid), **Blackjack** (solo hand-based), **Crates** (solo loot-box/gacha with a resale market). Plus account-wide **Statistics**, **Leaderboards**, and **Achievements**.

All money is in EUR, transmitted as integer cents — every screen must display `amount_cents / 100` formatted as currency, never raw cents.

## Screen list

1. **Auth** — Register and Login (can be one screen with a toggle, or two). Register: name, email, password. Login: email, password. Show inline validation errors matching the API's error cases (duplicate email on register; invalid credentials / disabled / frozen account on login).
2. **App shell / navigation** — persistent header showing live balance (`GET /balance`), user name, and nav to: Crash, Mines, Blackjack, Crates, Leaderboards, Statistics, Achievements, Profile/Logout. Balance should feel "live" (it's shared with the bank app, so treat it as something that can change outside this session).
3. **Crash** — the flagship real-time screen. Needs:
   - A live multiplier readout (huge, central) that climbs during the `running` phase and freezes red on crash.
   - A countdown during `betting` phase (7s window) with bet amount input + optional auto-cashout multiplier input, and a live feed of other players' bets streaming in (name, amount, is_bot flag distinguishable subtly — e.g. bots don't need a badge but shouldn't be indistinguishable from real players in a misleading way).
   - A "Cash Out" button, enabled only when the user has an active bet during `running`.
   - A rolling multiplier history strip (last N crash points, color-coded low/high).
   - A "Provably Fair" section/modal: shows `server_seed_hash` before the round, reveals `server_seed` after crash, and a verify view (`/verify/{round_id}`) showing hash, seed, nonce, computed crash point, and a pass/fail badge.
   - Round history list (last 20 rounds).
4. **Mines** — a configurable grid game. Needs:
   - Pre-round setup: bet amount input, tile-count selector (4–64, default 25 → 5x5 grid), mine-count selector (1 to tiles−1, default 3).
   - The grid itself: unrevealed tiles clickable; on reveal, show updated multiplier and a "next multiplier" preview for anticipation; a persistent Cash Out button enabled once ≥1 tile is revealed.
   - Bust state: flip all tiles, reveal every mine position, loss styling.
   - Cashout state: reveal all mine positions, win styling, show payout.
   - A history list of past rounds (bet, tiles, mines, multiplier, payout, status).
5. **Blackjack** — standard hand-based table UI. Needs:
   - Bet input to start a round.
   - Dealer area: up-card visible, hole card face-down until revealed (`dealer_hidden`).
   - Player hand area(s): after a split, render two hand areas side-by-side, clearly highlighting whichever is `active_hand_index`.
   - Action buttons: Hit, Stand always available when it's the player's turn on the active hand; Double only when `can_double`; Split only when `can_split`.
   - Insurance prompt (Yes/No) shown only when `phase == insurance_pending` (dealer showing an Ace).
   - Settled state: show each hand's `outcome` (bust/push/blackjack/win/loss) and payout, plus `total_payout_cents`.
   - History list of past rounds.
6. **Crates** — loot-box flow with three sub-screens:
   - Crate list (grid of cards: name, price, short description).
   - Crate detail: every possible item with image, name, rarity badge (color-coded by rarity tier — design an open-ended rarity scale, not just one "legendary" color, since more tiers may exist), value, and exact drop percentage — this is an odds-transparency screen, treat it as such.
   - Open flow: "Open" button (disabled if balance insufficient) → a reveal/spin animation → result card showing the won item.
   - Inventory screen: grid of owned items, each with a "Sell" action (hidden/disabled once already sold), and a distinction between owned vs. previously-sold items.
7. **Statistics** — a profile/stats dashboard. One screen, data-dense but scannable: overall totals (games played/won/lost, wagered, profit, biggest win/loss, favorite game) plus a per-game breakdown section (Crash, Mines, Blackjack, Crates each get their own stat block per the fields below).
8. **Leaderboards** — multiple ranked lists. Suggested structure: a "Top Winners" leaderboard with a Daily / Weekly / Monthly / All-Time tab switcher (all backed by the same profit metric at different time windows), plus separate tabs/screens for Richest, Biggest Win, Most Wagered, Most Games Played, Biggest Crash Cashout, and Most Legendary Items. Each row: rank, user name, primary value, optional secondary value (`extra`).
9. **Achievements** — a badge/checklist grid, 12 achievements, each showing name, description, and a clear locked vs. unlocked visual state (e.g. grayscale + lock icon when locked, full color + checkmark when unlocked).

## Full API contract

All amounts are integer cents, currency EUR. Authenticated requests use `Authorization: Bearer <JWT>`.

### Auth (no auth required)

**POST /auth/register**
Request: `name` (string 1–100), `email` (email), `password` (string 8–72).
Response 201: `message`, `user: { id, name, email, role, status }`.
Errors: 409 if email already registered.

**POST /auth/login**
Request: `email`, `password`.
Response 200: `access_token`, `token_type` ("bearer"), `role`.
Errors: 401 invalid credentials; 403 "Account has been disabled"; 403 "Account is frozen. Please contact support."

### Balance / Account (bearer required)

**GET /me** → `id, name, email, role, status, account_type`.

**GET /balance** → `account_id, balance_cents, currency, status`. 404 if no account.

### Crash (`/games/crash`) — shared live round, driven server-side

**GET /games/crash/state** (public) → `round_id, status ("betting"|"running"|"crashed"), server_seed_hash, nonce, betting_closes_at, current_multiplier, crash_point, server_seed, bets: [{display_name, amount_cents, auto_cashout_multiplier, cashout_multiplier, payout_cents, is_bot}]`.

**GET /games/crash/history** (public) → `rounds: [{round_id, nonce, crash_point, crashed_at}]` (last 20).

**GET /games/crash/verify/{round_id}** (public) → `round_id, nonce, server_seed, server_seed_hash, crash_point, verified`. 404 not found; 409 if round hasn't crashed yet.

**WS /games/crash/ws?token=<jwt>** (token optional — omit to spectate only)
On connect, server sends `{"type": "state", ...state fields...}`.

Client → server: `{"action": "place_bet", "amount_cents", "auto_cashout_multiplier"}` (min bet 100 cents, one bet per round, rejected if insufficient funds or round not in `betting`); `{"action": "cashout"}` (requires active bet, round must be `running`).

Server → client broadcasts: `{"type": "betting_open", round_id, nonce, server_seed_hash, betting_closes_at}` (7s window) · `{"type": "bet_placed", display_name, amount_cents, auto_cashout_multiplier, is_bot}` · `{"type": "round_started", round_id}` · `{"type": "tick", multiplier}` (every 100ms) · `{"type": "cashed_out", display_name, multiplier, payout_cents, is_bot}` · `{"type": "crashed", round_id, nonce, crash_point, server_seed}` (3s pause before next round) · `{"type": "error", message}`.

### Mines (`/games/mines`, bearer required)

**POST /games/mines/start** — `bet_amount_cents` (>0, min 100), `total_tiles` (default 25, 4–64), `mine_count` (default 3, 1 to total_tiles−1) → `RoundStateResponse`.

**GET /games/mines/round/{round_id}** → `RoundStateResponse`.

**POST /games/mines/round/{round_id}/reveal** — `tile_index` → `RoundStateResponse`. 409 if round already ended or tile already revealed; 422 if index out of range.

**POST /games/mines/round/{round_id}/cashout** → `RoundStateResponse`. 409 if round ended or no tiles revealed yet.

**GET /games/mines/history** → `rounds: [{round_id, bet_amount_cents, total_tiles, mine_count, multiplier, payout_cents, status, created_at, ended_at}]`.

`RoundStateResponse`: `round_id, status ("active"|"cashed_out"|"busted"), total_tiles, mine_count, revealed_tiles: [int], multiplier, next_multiplier (null once ended), payout_cents (null until cashed out), mine_positions (null while active, populated on bust/cashout)`.

### Blackjack (`/games/blackjack`, bearer required) — dealer stands on all 17s, min bet 100 cents

**POST /games/blackjack/start** — `bet_amount_cents` (≥100) → `RoundStateResponse`. Deals 2+2 cards; if dealer shows an Ace, phase → `insurance_pending`; otherwise resolves naturals immediately (push/loss/blackjack-2.5x) or continues to `player_turn`.

**GET /games/blackjack/round/{round_id}** → `RoundStateResponse`.

**POST /games/blackjack/round/{round_id}/insurance** — `want: bool` → `RoundStateResponse`. Only valid during `insurance_pending`. Insurance stake = half original bet; pays 3x stake if dealer has blackjack.

**POST /games/blackjack/round/{round_id}/hit** → `RoundStateResponse`. 409 if not player's turn.

**POST /games/blackjack/round/{round_id}/stand** → `RoundStateResponse`.

**POST /games/blackjack/round/{round_id}/double** → `RoundStateResponse`. Only on first two cards; doubles the wager, draws exactly one card, locks the hand.

**POST /games/blackjack/round/{round_id}/split** → `RoundStateResponse`. Only once, only on matching-rank first two cards (10/J/Q/K count as equal); creates a second hand with an equal wager.

**GET /games/blackjack/history** → `rounds: [{round_id, bet_amount_cents, status, created_at, ended_at}]`.

`RoundStateResponse`: `round_id, phase ("insurance_pending"|"player_turn"|"settled"), hands: [{cards: [{rank, suit}], bet_cents, status ("active"|"stood"|"busted"|"blackjack"|"doubled"), outcome ("bust"|"push"|"blackjack"|"win"|"loss"|null), payout_cents}], active_hand_index, dealer_cards (only first card visible while dealer_hidden), dealer_hidden, insurance_available, insurance_bet_cents, insurance_outcome, can_double, can_split, total_payout_cents`.

Payouts: blackjack win 2.5x bet · regular win 2x bet · push returns 1x bet · loss/bust 0 · insurance win 3x insurance stake.

### Crates (`/crates`)

**GET /crates** (public) → `crates: [{id, name, price_cents, description}]`.

**GET /crates/{crate_id}** (public) → `{id, name, price_cents, description, items: [{id, name, rarity, value_cents, sell_value_cents, image_url, description, drop_weight, drop_chance_pct}]}`. `drop_chance_pct` is the number to display as odds.

Rarity tiers (fixed 5-tier scale, ascending): `common`, `uncommon`, `rare`, `epic`, `legendary`. Design a distinct color per tier (e.g. gray → green → blue → purple → gold, a standard loot-tier convention).

Note: `image_url` currently holds a plain emoji character (e.g. 🪙, 💎), not a real image URL — design the item icon slot to work with a single emoji/glyph today, swappable for a real image later.

Seeded catalog (real current content — use this as actual design content, not placeholder text):

**Starter Crate** — 500 cents — "A cheap crate with modest odds at something rare."
| Item | Rarity | Value | Sell Value | Icon | Drop % |
|---|---|---|---|---|---|
| Copper Trinket | common | €2.00 | €1.50 | 🪙 | 60.0% |
| Silver Charm | uncommon | €6.00 | €4.50 | 🔮 | 28.0% |
| Sapphire Ring | rare | €25.00 | €18.00 | 💍 | 10.0% |
| Jeweled Crown | epic | €80.00 | €60.00 | 👑 | 1.8% |
| Mirage Heartstone | legendary | €500.00 | €400.00 | 💎 | 0.2% |

**High Roller Crate** — 5000 cents — "Expensive, but the floor and ceiling are both much higher."
| Item | Rarity | Value | Sell Value | Icon | Drop % |
|---|---|---|---|---|---|
| Steel Watch | common | €30.00 | €22.00 | ⌚ | 50.0% |
| Porcelain Vase | uncommon | €60.00 | €45.00 | 🏺 | 30.0% |
| Golden Statue | rare | €200.00 | €150.00 | 🗿 | 13.0% |
| Ancient Chalice | epic | €600.00 | €450.00 | 🏆 | 5.5% |
| Mirage Eternity Orb | legendary | €3000.00 | €2400.00 | 🔱 | 1.5% |

**POST /crates/{crate_id}/open** (bearer) → `{item: {id, name, rarity, value_cents, sell_value_cents, image_url, obtained_at, status: "owned", sold_at: null}, new_balance_cents}`. 422 insufficient funds; 409 if crate has no items configured.

**GET /crates/inventory/mine** (bearer) → `items: [InventoryItemView]` (both owned and sold).

**POST /crates/inventory/{item_id}/sell** (bearer) → `{item: {...status: "sold", sold_at}, payout_cents, new_balance_cents}`. 409 if item not owned/already sold.

### Statistics (`/statistics`, bearer required)

**GET /statistics/me** →
`games_played, games_won, games_lost, total_wagered_cents, total_profit_cents, biggest_win_cents, biggest_loss_cents, favorite_game (nullable string: "crash"|"mines"|"blackjack"|"crates"), crash_games_played, crash_games_won, crash_highest_multiplier, mines_games_played, mines_cashouts, blackjack_hands_played, blackjack_win_rate_pct, crates_opened, legendary_items_obtained`.

### Leaderboards (`/leaderboards`, public, query param `limit` default 10, range 1–100)

Common shape: `entries: [{user_id, name, value, extra}]`.

- `GET /leaderboards/richest` — value = current balance.
- `GET /leaderboards/biggest-win` — value = largest single payout; extra = game name.
- `GET /leaderboards/most-profit` — value = lifetime profit (all-time).
- `GET /leaderboards/most-wagered` — value = lifetime total wagered.
- `GET /leaderboards/most-games-played` — value = round count.
- `GET /leaderboards/biggest-crash-cashout` — value = largest single Crash payout; extra = the cashout multiplier.
- `GET /leaderboards/most-legendary-items` — value = legendary item count.
- `GET /leaderboards/daily-winners` / `weekly-winners` / `monthly-winners` — same profit metric, rolling 24h / 7d / 30d windows.

### Achievements (`/achievements`, bearer required)

**GET /achievements/me** → `{achievements: [{id, name, description, unlocked: bool}]}`. Achievements are evaluated lazily on every call (checking-and-unlocking, not event-pushed) and stay unlocked permanently once earned. No progress-fraction field is returned — only a locked/unlocked boolean — so don't design a numeric progress bar driven by this endpoint alone; some thresholds (e.g. `high_roller`'s "biggest single wager") aren't exposed by any other endpoint either.

Full catalog (12, design as a grid in this order):

1. **First Bet** — Place your first wager.
2. **First Win** — Win a game for the first time.
3. **Lucky** — Win 10 games.
4. **Millionaire** — Reach a bank balance of €1,000,000.00.
5. **High Roller** — Wager €100.00 or more in a single bet.
6. **Blackjack Master** — Win 25 Blackjack hands.
7. **Mine Expert** — Cash out 25 Mines rounds.
8. **Crash Addict** — Play 50 Crash rounds.
9. **Legendary Pull** — Obtain a legendary crate item.
10. **100 Games** — Play 100 games total.
11. **1000 Games** — Play 1000 games total.
12. **Huge Profit** — Reach €10,000.00 in total profit.

## Notes for the designer

- Treat balance as shared/live state, not something this app fully owns.
- Crash is the only shared/multiplayer, real-time screen — it deserves the most motion/animation design attention (climbing multiplier, live bet feed, cashout flashes).
- Mines and Blackjack are turn-based/solo — REST round-trips are fine, no need for websocket-style live updates.
- Crates needs a gacha-style reveal animation and clear rarity color coding, but must still foreground the exact odds (`drop_chance_pct`) for trust/transparency.
- All screens that show money must format cents as currency consistently.
- No mockups or wireframes exist yet — this brief is the complete starting context.
