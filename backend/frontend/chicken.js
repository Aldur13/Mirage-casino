const els = {
  betAmount: document.getElementById("bet-amount"),
  difficultySelector: document.getElementById("difficulty-selector"),
  startBtn: document.getElementById("start-btn"),
  crossBtn: document.getElementById("cross-btn"),
  cashoutBtn: document.getElementById("cashout-btn"),
  multiplier: document.getElementById("multiplier"),
  nextMultiplierWrap: document.getElementById("next-multiplier-wrap"),
  nextMultiplier: document.getElementById("next-multiplier"),
  message: document.getElementById("chicken-message"),
  road: document.getElementById("road"),
};

let currentRound = null;
let selectedDifficulty = "medium";

els.difficultySelector.querySelectorAll(".qty-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (currentRound && currentRound.status === "active") return;
    selectedDifficulty = btn.dataset.difficulty;
    els.difficultySelector.querySelectorAll(".qty-btn").forEach((b) => b.classList.toggle("active", b === btn));
  });
});

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

function renderRoad(round) {
  els.road.innerHTML = "";
  for (let i = 0; i < round.max_lanes; i++) {
    const cell = document.createElement("div");
    cell.className = "chicken-lane";

    const crossed = i < round.lanes_crossed;
    const isCurrent = i === round.lanes_crossed && round.status === "active";
    const isFatal = i === round.lanes_crossed && round.status === "busted";
    const outcome = round.lane_outcomes ? round.lane_outcomes[i] : null; // true = car

    if (crossed) {
      cell.classList.add("crossed");
      cell.textContent = "🐔";
    } else if (isCurrent) {
      cell.classList.add("current");
      cell.textContent = "🐔";
    } else if (isFatal) {
      cell.classList.add("hit");
      cell.textContent = "💥";
    } else if (outcome === true) {
      cell.classList.add("car");
      cell.textContent = "🚗";
    } else if (outcome === false) {
      cell.classList.add("clear");
      cell.textContent = "";
    }
    els.road.appendChild(cell);
  }
}

function updateFromRound(round) {
  currentRound = round;
  els.multiplier.textContent = `${round.multiplier.toFixed(2)}x`;

  if (round.status === "active" && round.next_multiplier != null) {
    els.nextMultiplierWrap.hidden = false;
    els.nextMultiplier.textContent = `${round.next_multiplier.toFixed(2)}x`;
  } else {
    els.nextMultiplierWrap.hidden = true;
  }

  const active = round.status === "active";
  els.startBtn.disabled = active;
  els.crossBtn.disabled = !active;
  els.cashoutBtn.disabled = !active || round.lanes_crossed === 0;
  els.difficultySelector.querySelectorAll(".qty-btn").forEach((b) => { b.disabled = active; });

  renderRoad(round);

  if (round.status === "busted") showMessage("Clipped! Better luck next time.", true);
  else if (round.status === "cashed_out") showMessage(`Cashed out for €${(round.payout_cents / 100).toFixed(2)}`);
  else showMessage("");
}

function setSidebarBalance(cents, currency) {
  const el = document.getElementById("sidebar-balance");
  if (el) el.textContent = formatMoney(cents, currency || "EUR");
}

async function startRound() {
  try {
    const betCents = Math.round(parseFloat(els.betAmount.value) * 100);
    const round = await api("/games/chicken/start", {
      method: "POST",
      body: JSON.stringify({ bet_amount_cents: betCents, difficulty: selectedDifficulty }),
    });
    updateFromRound(round);
  } catch (err) {
    showMessage(err.message, true);
  }
}

async function crossLane() {
  if (!currentRound || currentRound.status !== "active") return;
  try {
    const round = await api(`/games/chicken/round/${currentRound.round_id}/cross`, { method: "POST" });
    updateFromRound(round);
    if (round.status === "busted") await refreshBalance();
  } catch (err) {
    showMessage(err.message, true);
  }
}

async function cashout() {
  if (!currentRound) return;
  try {
    const round = await api(`/games/chicken/round/${currentRound.round_id}/cashout`, { method: "POST" });
    updateFromRound(round);
    await refreshBalance();
  } catch (err) {
    showMessage(err.message, true);
  }
}

async function refreshBalance() {
  try {
    const balance = await api("/balance");
    setSidebarBalance(balance.balance_cents, balance.currency);
  } catch {
    // sidebar balance is a convenience refresh — ignore failures here
  }
}

els.startBtn.addEventListener("click", () => { startRound().then(refreshBalance); });
els.crossBtn.addEventListener("click", crossLane);
els.cashoutBtn.addEventListener("click", cashout);
