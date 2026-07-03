const els = {
  betAmount: document.getElementById("bet-amount"),
  mineCount: document.getElementById("mine-count"),
  startBtn: document.getElementById("start-btn"),
  cashoutBtn: document.getElementById("cashout-btn"),
  multiplier: document.getElementById("multiplier"),
  message: document.getElementById("mines-message"),
  grid: document.getElementById("grid"),
};

let currentRound = null;
const TOTAL_TILES = 25;

function showMessage(text, isError = false) {
  els.message.textContent = text;
  els.message.classList.toggle("ok", !isError);
}

async function api(path, options = {}) {
  const token = localStorage.getItem(TOKEN_KEY);
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(path, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

function renderGrid(round) {
  els.grid.innerHTML = "";
  for (let i = 0; i < round.total_tiles; i++) {
    const btn = document.createElement("button");
    btn.className = "mines-tile";
    btn.dataset.index = i;

    if (round.revealed_tiles.includes(i)) {
      btn.classList.add("safe");
      btn.textContent = "💎";
      btn.disabled = true;
    } else if (round.mine_positions && round.mine_positions.includes(i)) {
      btn.classList.add("mine");
      btn.textContent = "💣";
      btn.disabled = true;
    } else {
      btn.disabled = round.status !== "active";
      btn.addEventListener("click", () => revealTile(i));
    }
    els.grid.appendChild(btn);
  }
}

function updateFromRound(round) {
  currentRound = round;
  els.multiplier.textContent = `${round.multiplier.toFixed(2)}x`;
  els.cashoutBtn.disabled = round.status !== "active" || round.revealed_tiles.length === 0;
  els.startBtn.disabled = round.status === "active";
  renderGrid(round);

  if (round.status === "busted") showMessage("Busted! Better luck next round.", true);
  else if (round.status === "cashed_out") showMessage(`Cashed out for €${(round.payout_cents / 100).toFixed(2)}`);
  else showMessage("");
}

async function startRound() {
  try {
    const betCents = Math.round(parseFloat(els.betAmount.value) * 100);
    const round = await api("/games/mines/start", {
      method: "POST",
      body: JSON.stringify({
        bet_amount_cents: betCents,
        total_tiles: TOTAL_TILES,
        mine_count: parseInt(els.mineCount.value, 10),
      }),
    });
    updateFromRound(round);
  } catch (err) {
    showMessage(err.message, true);
  }
}

async function revealTile(index) {
  if (!currentRound || currentRound.status !== "active") return;
  try {
    const round = await api(`/games/mines/round/${currentRound.round_id}/reveal`, {
      method: "POST",
      body: JSON.stringify({ tile_index: index }),
    });
    updateFromRound(round);
  } catch (err) {
    showMessage(err.message, true);
  }
}

async function cashout() {
  if (!currentRound) return;
  try {
    const round = await api(`/games/mines/round/${currentRound.round_id}/cashout`, { method: "POST" });
    updateFromRound(round);
  } catch (err) {
    showMessage(err.message, true);
  }
}

els.startBtn.addEventListener("click", startRound);
els.cashoutBtn.addEventListener("click", cashout);
