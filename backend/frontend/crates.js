const CELL_WIDTH = 140;
const REEL_LENGTH = 60;
const LANDING_INDEX = 50;
const SPIN_DURATION_MS = 5500;
const BATCH_SPIN_DURATION_MS = 900;
const BATCH_STEP_PAUSE_MS = 200;
const AUTO_SELL_KEY = "mirage_casino_crates_auto_sell";
const OPEN_QTY_KEY = "mirage_casino_crates_open_qty";

const els = {
  crateList: document.getElementById("crate-list"),
  inventoryList: document.getElementById("inventory-list"),
  message: document.getElementById("crates-message"),
  autoSellCheckbox: document.getElementById("auto-sell-checkbox"),
  qtySelector: document.getElementById("qty-selector"),
  spinOverlay: document.getElementById("spin-overlay"),
  spinViewport: document.getElementById("spin-viewport"),
  spinTrack: document.getElementById("spin-track"),
  spinBatchInfo: document.getElementById("spin-batch-info"),
  spinBatchProgress: document.getElementById("spin-batch-progress"),
  spinBatchStop: document.getElementById("spin-batch-stop"),
  spinResult: document.getElementById("spin-result"),
  spinResultName: document.getElementById("spin-result-name"),
  spinResultValue: document.getElementById("spin-result-value"),
  spinResultActions: document.getElementById("spin-result-actions"),
};

// crate.id -> items[] (needed to build a plausible-looking reel client-side;
// the actual outcome always comes from the server response, this is just
// the animation leading up to revealing it)
const crateItemsById = new Map();

// isBusy gates every "Open" button and the qty selector for the duration of
// a single open OR a whole batch run, so two opens can never overlap on the
// one shared spin overlay. It's only ever cleared by endInteraction(), which
// fires from an explicit user action (Keep/Sell/Done) or a thrown error —
// never implicitly — so a crate's button can't get stuck disabled looking
// "sold out" while nothing is actually in flight.
let isBusy = false;
let batchStopRequested = false;
let selectedQty = Number(localStorage.getItem(OPEN_QTY_KEY)) || 1;

els.autoSellCheckbox.checked = localStorage.getItem(AUTO_SELL_KEY) === "1";
els.autoSellCheckbox.addEventListener("change", () => {
  localStorage.setItem(AUTO_SELL_KEY, els.autoSellCheckbox.checked ? "1" : "0");
});

els.qtySelector.querySelectorAll(".qty-btn").forEach((btn) => {
  btn.classList.toggle("active", Number(btn.dataset.qty) === selectedQty);
  btn.addEventListener("click", () => {
    if (isBusy) return;
    selectedQty = Number(btn.dataset.qty);
    localStorage.setItem(OPEN_QTY_KEY, String(selectedQty));
    els.qtySelector.querySelectorAll(".qty-btn").forEach((b) => b.classList.toggle("active", b === btn));
  });
});

els.spinBatchStop.addEventListener("click", () => {
  batchStopRequested = true;
});

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

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

function rarityBadge(rarity) {
  return `<span class="badge badge-${rarity}">${rarity}</span>`;
}

function setSidebarBalance(cents, currency) {
  const el = document.getElementById("sidebar-balance");
  if (el) el.textContent = formatMoney(cents, currency || "EUR");
}

async function loadCrates() {
  const { crates } = await api("/crates");
  const details = await Promise.all(crates.map((c) => api(`/crates/${c.id}`)));

  els.crateList.innerHTML = "";
  details.forEach((detail, i) => {
    const crate = crates[i];
    crateItemsById.set(crate.id, detail.items);

    const card = document.createElement("div");
    card.className = "crate-card";
    card.innerHTML = `
      <div class="emoji">🎁</div>
      <div><strong>${crate.name}</strong></div>
      <div class="crate-desc">${crate.description}</div>
      <div class="num">€${(crate.price_cents / 100).toFixed(2)}</div>
      <div class="crate-odds">
        ${detail.items.map((i) => `
          <div class="crate-odds-row">
            <span>${i.image_url} ${i.name} ${rarityBadge(i.rarity)}</span>
            <span class="pct num">${i.drop_chance_pct}%</span>
          </div>
        `).join("")}
      </div>
      <button data-id="${crate.id}" class="btn-primary">Open</button>
    `;
    card.querySelector("button").addEventListener("click", () => openCrate(crate.id));
    els.crateList.appendChild(card);
  });
}

function setCratesControlsDisabled(disabled) {
  document.querySelectorAll(".crate-card button").forEach((b) => { b.disabled = disabled; });
  document.querySelectorAll(".qty-btn").forEach((b) => { b.disabled = disabled; });
}

function beginInteraction() {
  isBusy = true;
  batchStopRequested = false;
  setCratesControlsDisabled(true);
}

// The only way the overlay closes and controls re-enable. Called from an
// explicit user click (Keep/Sell/Done) or from a caught error — every
// open/batch path funnels here eventually, so a crate can never end up
// permanently disabled with nothing actually running.
function endInteraction() {
  isBusy = false;
  setCratesControlsDisabled(false);
  els.spinOverlay.hidden = true;
  els.spinBatchInfo.hidden = true;
  els.spinResult.hidden = true;
}

function openCrate(crateId) {
  if (isBusy) return;
  beginInteraction();
  const run = selectedQty > 1 ? openBatch(crateId, selectedQty) : openSingle(crateId);
  run.catch((err) => {
    showMessage(err.message, true);
    endInteraction();
  });
}

async function openSingle(crateId) {
  const autoSell = els.autoSellCheckbox.checked;
  const result = await api(`/crates/${crateId}/open`, {
    method: "POST",
    body: JSON.stringify({ auto_sell: autoSell }),
  });
  await runSpin(crateItemsById.get(crateId) || [], result);
  showLandedResult(result);
}

async function openBatch(crateId, qty) {
  const crateItems = crateItemsById.get(crateId) || [];
  const autoSell = els.autoSellCheckbox.checked;
  const tally = { opened: 0, soldCents: 0, keptValueCents: 0, byRarity: {} };

  els.spinResult.hidden = true;
  els.spinBatchInfo.hidden = false;
  els.spinOverlay.hidden = false;

  for (let i = 0; i < qty; i++) {
    if (batchStopRequested) break;
    els.spinBatchProgress.textContent = `Opening ${i + 1} / ${qty}…`;

    let result;
    try {
      result = await api(`/crates/${crateId}/open`, {
        method: "POST",
        body: JSON.stringify({ auto_sell: autoSell }),
      });
    } catch (err) {
      showMessage(`Auto-open stopped after ${tally.opened}: ${err.message}`, true);
      break;
    }

    const item = result.item;
    tally.opened += 1;
    tally.byRarity[item.rarity] = (tally.byRarity[item.rarity] || 0) + 1;
    if (result.sold) tally.soldCents += result.payout_cents;
    else tally.keptValueCents += item.sell_value_cents;

    setSidebarBalance(result.new_balance_cents);
    els.spinBatchProgress.textContent =
      `Opened ${i + 1} / ${qty} — last: ${item.image_url} ${item.name} (${item.rarity})`;
    await runSpin(crateItems, result, { durationMs: BATCH_SPIN_DURATION_MS });

    if (batchStopRequested) break;
    await sleep(BATCH_STEP_PAUSE_MS);
  }

  await loadInventory();
  showBatchSummary(tally, qty);
}

function weightedSample(items) {
  const total = items.reduce((sum, item) => sum + item.drop_weight, 0);
  let roll = Math.random() * total;
  for (const item of items) {
    if (roll < item.drop_weight) return item;
    roll -= item.drop_weight;
  }
  return items[items.length - 1];
}

function buildReel(items, landedItem) {
  const reel = [];
  for (let i = 0; i < REEL_LENGTH; i++) {
    reel.push(i === LANDING_INDEX ? landedItem : weightedSample(items));
  }
  return reel;
}

function spinCellHtml(item) {
  return `
    <div class="spin-cell rarity-${item.rarity}">
      <div class="emoji">${item.image_url}</div>
      <div class="spin-cell-name">${item.name}</div>
    </div>
  `;
}

function runSpin(crateItems, result, opts = {}) {
  const duration = opts.durationMs || SPIN_DURATION_MS;

  return new Promise((resolve) => {
    const item = result.item;
    // Fall back to a single-cell reel of just the won item if we don't have
    // the crate's item list cached (e.g. loadCrates hasn't resolved yet) —
    // still shows the correct result, just without the scroll flourish.
    const reel = crateItems.length ? buildReel(crateItems, item) : [item];
    const landingIndex = crateItems.length ? LANDING_INDEX : 0;

    els.spinTrack.style.transition = "none";
    els.spinTrack.style.transform = "translateX(0)";
    els.spinTrack.innerHTML = reel.map(spinCellHtml).join("");

    // Force layout so the transition reset above actually takes effect
    // before the animated transform is applied below.
    void els.spinTrack.offsetWidth;

    const viewportWidth = els.spinViewport.clientWidth;
    const targetOffset = landingIndex * CELL_WIDTH + CELL_WIDTH / 2 - viewportWidth / 2;
    const jitter = (Math.random() - 0.5) * (CELL_WIDTH * 0.4);

    let settled = false;
    const settle = () => {
      if (settled) return;
      settled = true;
      els.spinTrack.removeEventListener("transitionend", onDone);
      clearTimeout(fallbackTimer);
      resolve();
    };
    const onDone = (e) => {
      if (e.target !== els.spinTrack || e.propertyName !== "transform") return;
      settle();
    };
    els.spinTrack.addEventListener("transitionend", onDone);
    // Hard fallback: transitionend can silently fail to fire (backgrounded
    // tab throttling, prefers-reduced-motion overriding the transition,
    // browser quirks). Without this, a missed event would leave the promise
    // unresolved forever — and with it, the crate's button stuck disabled,
    // looking permanently "sold out". This guarantees settle() always runs.
    const fallbackTimer = setTimeout(settle, duration + 400);

    requestAnimationFrame(() => {
      els.spinTrack.style.transition = `transform ${duration}ms cubic-bezier(0.1, 0.85, 0.15, 1)`;
      els.spinTrack.style.transform = `translateX(-${targetOffset + jitter}px)`;
    });
  });
}

function showLandedResult(result) {
  const item = result.item;
  els.spinResultName.textContent = `${item.image_url} ${item.name} (${item.rarity})`;

  if (result.sold) {
    els.spinResultValue.textContent = `Auto-sold for €${(result.payout_cents / 100).toFixed(2)}`;
  } else {
    els.spinResultValue.textContent =
      `Value: €${(item.value_cents / 100).toFixed(2)} · Sell: €${(item.sell_value_cents / 100).toFixed(2)}`;
  }

  els.spinResultActions.innerHTML = result.sold
    ? `<button class="btn-primary" id="spin-close">Continue</button>`
    : `<button class="btn-ghost" id="spin-keep">Keep it</button>
       <button class="btn-primary" id="spin-sell">Sell now</button>`;

  document.getElementById("spin-close")?.addEventListener("click", () => endInteraction());
  document.getElementById("spin-keep")?.addEventListener("click", () => endInteraction());
  document.getElementById("spin-sell")?.addEventListener("click", async () => {
    await sellItem(item.id);
    endInteraction();
  });

  setSidebarBalance(result.new_balance_cents);
  showMessage(
    result.sold
      ? `You got ${item.name} — auto-sold for €${(result.payout_cents / 100).toFixed(2)}`
      : `You got: ${item.name} (${item.rarity})`,
  );
  els.spinResult.hidden = false;
  loadInventory();
}

function showBatchSummary(tally, qty) {
  els.spinBatchInfo.hidden = true;

  const rarityParts = Object.entries(tally.byRarity).map(([r, n]) => `${n} ${r}`).join(", ") || "nothing";
  let valueLine;
  if (tally.soldCents > 0 && tally.keptValueCents > 0) {
    valueLine = `sold for €${(tally.soldCents / 100).toFixed(2)}, kept items worth ~€${(tally.keptValueCents / 100).toFixed(2)}`;
  } else if (tally.soldCents > 0) {
    valueLine = `auto-sold for €${(tally.soldCents / 100).toFixed(2)} total`;
  } else {
    valueLine = `kept, worth ~€${(tally.keptValueCents / 100).toFixed(2)} total`;
  }

  els.spinResultName.textContent = `Opened ${tally.opened} of ${qty} crates`;
  els.spinResultValue.textContent = `${rarityParts} — ${valueLine}`;
  els.spinResultActions.innerHTML = `<button class="btn-primary" id="spin-close">Done</button>`;
  document.getElementById("spin-close").addEventListener("click", () => endInteraction());

  els.spinResult.hidden = false;
  showMessage(`Auto-open finished: ${tally.opened}/${qty} — ${valueLine}`);
}

async function loadInventory() {
  const { items } = await api("/crates/inventory/mine");
  els.inventoryList.innerHTML = "";
  items.filter((i) => i.status === "owned").forEach((item) => {
    const card = document.createElement("div");
    card.className = `item-card rarity-${item.rarity}`;
    card.innerHTML = `
      <div class="emoji">${item.image_url}</div>
      <div><strong>${item.name}</strong></div>
      ${rarityBadge(item.rarity)}
      <div class="item-sell-value num">Sell: €${(item.sell_value_cents / 100).toFixed(2)}</div>
      <button data-id="${item.id}" class="btn-ghost">Sell</button>
    `;
    card.querySelector("button").addEventListener("click", () => sellItem(item.id));
    els.inventoryList.appendChild(card);
  });
}

async function sellItem(itemId) {
  try {
    const result = await api(`/crates/inventory/${itemId}/sell`, { method: "POST" });
    showMessage(`Sold for €${(result.payout_cents / 100).toFixed(2)}`);
    setSidebarBalance(result.new_balance_cents);
    await loadInventory();
  } catch (err) {
    showMessage(err.message, true);
  }
}

loadCrates().catch((err) => showMessage(`Failed to load crates: ${err.message}`));
loadInventory().catch(() => {});
