const els = {
  multiplier: document.getElementById("multiplier"),
  graph: document.getElementById("crash-graph"),
  graphLine: document.getElementById("crash-line"),
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
let graphPoints = []; // multiplier values sampled this round, oldest first

function showMessage(text, isError = false) {
  els.message.textContent = text;
  els.message.classList.toggle("ok", !isError);
}

function addPlayerRow(displayName, amountCents, isBot, extra = "") {
  const li = document.createElement("li");
  const badge = isBot ? '<span class="bot-badge">BOT</span>' : "";
  li.innerHTML = `<span>${displayName}${badge}</span><span>€${(amountCents / 100).toFixed(2)} ${extra}</span>`;
  els.playerList.appendChild(li);
}

function resetGraph() {
  graphPoints = [1];
  els.graph.classList.remove("crashed");
  drawGraph();
}

function drawGraph() {
  const width = 300;
  const height = 100;
  const pad = 6;
  if (graphPoints.length < 2) {
    els.graphLine.setAttribute("points", `${pad},${height - pad} ${width - pad},${height - pad}`);
    return;
  }
  // Log scale so the line stays readable as the multiplier grows exponentially.
  const maxLog = Math.log2(Math.max(...graphPoints, 2));
  const points = graphPoints.map((m, i) => {
    const x = pad + (i / (graphPoints.length - 1)) * (width - pad * 2);
    const y = height - pad - (Math.log2(Math.max(m, 1)) / maxLog) * (height - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  els.graphLine.setAttribute("points", points.join(" "));
}

function resetRound() {
  els.playerList.innerHTML = "";
  els.multiplier.classList.remove("crashed");
  els.multiplier.textContent = "1.00x";
  hasActiveBet = false;
  els.cashoutBtn.disabled = true;
  els.betBtn.disabled = false;
  resetGraph();
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
        graphPoints = [1, msg.current_multiplier];
        drawGraph();
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
      graphPoints.push(msg.multiplier);
      drawGraph();
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
      els.graph.classList.add("crashed");
      els.phaseBanner.textContent = "Crashed — next round soon";
      els.seedReveal.textContent = `Seed: ${msg.server_seed}`;
      els.cashoutBtn.disabled = true;
      hasActiveBet = false;
      prependCrash(msg.crash_point);
      break;

    case "error":
      showMessage(msg.message, true);
      break;
  }
});

function prependCrash(crashPoint) {
  const li = document.createElement("li");
  li.textContent = `${crashPoint.toFixed(2)}x`;
  li.className = crashPoint < 2 ? "low" : "high";
  els.recentCrashes.prepend(li);
  while (els.recentCrashes.children.length > 20) {
    els.recentCrashes.removeChild(els.recentCrashes.lastChild);
  }
}

els.betBtn.addEventListener("click", () => {
  const amount_cents = Math.round(parseFloat(els.betAmount.value) * 100);
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

resetGraph();
