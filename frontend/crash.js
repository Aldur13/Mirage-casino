const TOKEN_KEY = "mirage_casino_token";

const els = {
  multiplier: document.getElementById("multiplier"),
  phaseBanner: document.getElementById("phase-banner"),
  betAmount: document.getElementById("bet-amount"),
  autoCashout: document.getElementById("auto-cashout"),
  betBtn: document.getElementById("bet-btn"),
  cashoutBtn: document.getElementById("cashout-btn"),
  message: document.getElementById("crash-message"),
  playerList: document.getElementById("player-list"),
  recentCrashes: document.getElementById("recent-crashes"),
  seedHash: document.getElementById("seed-hash"),
  seedReveal: document.getElementById("seed-reveal"),
};

let hasActiveBet = false;

function showMessage(text) {
  els.message.textContent = text;
}

function addPlayerRow(displayName, amountCents, isBot, extra = "") {
  const li = document.createElement("li");
  const badge = isBot ? '<span class="bot-badge">BOT</span>' : "";
  li.innerHTML = `<span>${displayName}${badge}</span><span>${(amountCents / 100).toFixed(2)} ${extra}</span>`;
  els.playerList.appendChild(li);
}

function resetRound() {
  els.playerList.innerHTML = "";
  els.multiplier.classList.remove("crashed");
  els.multiplier.textContent = "1.00x";
  hasActiveBet = false;
  els.cashoutBtn.disabled = true;
  els.betBtn.disabled = false;
}

function wsUrl() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const token = localStorage.getItem(TOKEN_KEY);
  const qs = token ? `?token=${encodeURIComponent(token)}` : "";
  return `${proto}://${location.host}/games/crash/ws${qs}`;
}

const socket = new WebSocket(wsUrl());

socket.addEventListener("message", (event) => {
  const msg = JSON.parse(event.data);

  switch (msg.type) {
    case "state":
      els.seedHash.textContent = msg.server_seed_hash || "—";
      if (msg.status === "running" && msg.current_multiplier) {
        els.multiplier.textContent = `${msg.current_multiplier.toFixed(2)}x`;
      }
      (msg.bets || []).forEach((b) => addPlayerRow(b.display_name, b.amount_cents, b.is_bot));
      break;

    case "betting_open":
      resetRound();
      els.seedHash.textContent = msg.server_seed_hash;
      els.seedReveal.textContent = "";
      els.phaseBanner.textContent = "Betting open...";
      break;

    case "bet_placed":
      addPlayerRow(msg.display_name, msg.amount_cents, msg.is_bot);
      break;

    case "round_started":
      els.phaseBanner.textContent = "Live";
      els.betBtn.disabled = true;
      break;

    case "tick":
      els.multiplier.textContent = `${msg.multiplier.toFixed(2)}x`;
      break;

    case "cashed_out":
      showMessage(`${msg.display_name} cashed out at ${msg.multiplier.toFixed(2)}x`);
      if (!msg.is_bot && hasActiveBet) {
        els.cashoutBtn.disabled = true;
      }
      break;

    case "crashed":
      els.multiplier.textContent = `${msg.crash_point.toFixed(2)}x`;
      els.multiplier.classList.add("crashed");
      els.phaseBanner.textContent = "Crashed — next round soon";
      els.seedReveal.textContent = `Seed: ${msg.server_seed}`;
      els.cashoutBtn.disabled = true;
      hasActiveBet = false;
      prependCrash(msg.crash_point);
      break;

    case "error":
      showMessage(msg.message);
      break;
  }
});

function prependCrash(crashPoint) {
  const li = document.createElement("li");
  li.textContent = `${crashPoint.toFixed(2)}x`;
  els.recentCrashes.prepend(li);
  while (els.recentCrashes.children.length > 20) {
    els.recentCrashes.removeChild(els.recentCrashes.lastChild);
  }
}

els.betBtn.addEventListener("click", () => {
  const amount_cents = parseInt(els.betAmount.value, 10);
  const auto = parseFloat(els.autoCashout.value);
  socket.send(JSON.stringify({
    action: "place_bet",
    amount_cents,
    auto_cashout_multiplier: Number.isFinite(auto) ? auto : null,
  }));
  hasActiveBet = true;
  els.cashoutBtn.disabled = false;
  els.betBtn.disabled = true;
});

els.cashoutBtn.addEventListener("click", () => {
  socket.send(JSON.stringify({ action: "cashout" }));
});
