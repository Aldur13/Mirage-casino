const els = {
  betAmount: document.getElementById("bet-amount"),
  startBtn: document.getElementById("start-btn"),
  dealerHand: document.getElementById("dealer-hand"),
  handsContainer: document.getElementById("hands-container"),
  hitBtn: document.getElementById("hit-btn"),
  standBtn: document.getElementById("stand-btn"),
  doubleBtn: document.getElementById("double-btn"),
  splitBtn: document.getElementById("split-btn"),
  insureYesBtn: document.getElementById("insure-yes-btn"),
  insureNoBtn: document.getElementById("insure-no-btn"),
  message: document.getElementById("bj-message"),
};

let currentRoundId = null;

function showMessage(text) {
  els.message.textContent = text;
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

function cardLabel(card) {
  return `${card.rank}${card.suit}`;
}

function renderHand(container, cards) {
  container.innerHTML = "";
  cards.forEach((c) => {
    const div = document.createElement("div");
    div.className = "bj-card";
    div.textContent = cardLabel(c);
    container.appendChild(div);
  });
}

function render(state) {
  currentRoundId = state.round_id;
  renderHand(els.dealerHand, state.dealer_cards);
  if (state.dealer_hidden) {
    const hidden = document.createElement("div");
    hidden.className = "bj-card";
    hidden.textContent = "??";
    els.dealerHand.appendChild(hidden);
  }

  els.handsContainer.innerHTML = "";
  state.hands.forEach((hand, i) => {
    const block = document.createElement("div");
    block.className = "bj-hand-block" + (i === state.active_hand_index && state.phase === "player_turn" ? " active" : "");
    const title = document.createElement("h3");
    title.textContent = `Hand ${i + 1} — ${hand.status}${hand.outcome ? ` (${hand.outcome})` : ""}`;
    block.appendChild(title);
    const cardsDiv = document.createElement("div");
    cardsDiv.className = "bj-hand";
    block.appendChild(cardsDiv);
    renderHand(cardsDiv, hand.cards);
    els.handsContainer.appendChild(block);
  });

  const active = state.phase === "player_turn";
  els.hitBtn.disabled = !active;
  els.standBtn.disabled = !active;
  els.doubleBtn.disabled = !(active && state.can_double);
  els.splitBtn.disabled = !(active && state.can_split);
  els.insureYesBtn.disabled = state.phase !== "insurance_pending";
  els.insureNoBtn.disabled = state.phase !== "insurance_pending";
  els.startBtn.disabled = active || state.phase === "insurance_pending";

  if (state.phase === "settled") {
    showMessage(`Round settled — total payout €${(state.total_payout_cents / 100).toFixed(2)}`);
  } else {
    showMessage("");
  }
}

async function start() {
  try {
    const state = await api("/games/blackjack/start", {
      method: "POST",
      body: JSON.stringify({ bet_amount_cents: parseInt(els.betAmount.value, 10) }),
    });
    render(state);
  } catch (err) {
    showMessage(err.message);
  }
}

async function action(path, options = {}) {
  if (!currentRoundId) return;
  try {
    const state = await api(`/games/blackjack/round/${currentRoundId}${path}`, { method: "POST", ...options });
    render(state);
  } catch (err) {
    showMessage(err.message);
  }
}

els.startBtn.addEventListener("click", start);
els.hitBtn.addEventListener("click", () => action("/hit"));
els.standBtn.addEventListener("click", () => action("/stand"));
els.doubleBtn.addEventListener("click", () => action("/double"));
els.splitBtn.addEventListener("click", () => action("/split"));
els.insureYesBtn.addEventListener("click", () => action("/insurance", { body: JSON.stringify({ want: true }) }));
els.insureNoBtn.addEventListener("click", () => action("/insurance", { body: JSON.stringify({ want: false }) }));
