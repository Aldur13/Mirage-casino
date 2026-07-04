const CELL_WIDTH = 140;
const REEL_LENGTH = 60;
const LANDING_INDEX = 50;
const SPIN_DURATION_MS = 5500;
const AUTO_SELL_KEY = "mirage_casino_crates_auto_sell";

const els = {
  crateList: document.getElementById("crate-list"),
  inventoryList: document.getElementById("inventory-list"),
  message: document.getElementById("crates-message"),
  autoSellCheckbox: document.getElementById("auto-sell-checkbox"),
  spinOverlay: document.getElementById("spin-overlay"),
  spinViewport: document.getElementById("spin-viewport"),
  spinTrack: document.getElementById("spin-track"),
  spinResult: document.getElementById("spin-result"),
  spinResultName: document.getElementById("spin-result-name"),
  spinResultValue: document.getElementById("spin-result-value"),
  spinResultActions: document.getElementById("spin-result-actions"),
};

// crate.id -> items[] (needed to build a plausible-looking reel client-side;
// the actual outcome always comes from the server response, this is just
// the animation leading up to revealing it)
const crateItemsById = new Map();

els.autoSellCheckbox.checked = localStorage.getItem(AUTO_SELL_KEY) === "1";
els.autoSellCheckbox.addEventListener("change", () => {
  localStorage.setItem(AUTO_SELL_KEY, els.autoSellCheckbox.checked ? "1" : "0");
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
    card.querySelector("button").addEventListener("click", (e) => {
      e.currentTarget.disabled = true;
      openCrate(crate.id).finally(() => { e.currentTarget.disabled = false; });
    });
    els.crateList.appendChild(card);
  });
}

async function openCrate(crateId) {
  try {
    const autoSell = els.autoSellCheckbox.checked;
    const result = await api(`/crates/${crateId}/open`, {
      method: "POST",
      body: JSON.stringify({ auto_sell: autoSell }),
    });
    await runSpin(crateItemsById.get(crateId) || [], result);
  } catch (err) {
    showMessage(err.message, true);
  }
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

function runSpin(crateItems, result) {
  return new Promise((resolve) => {
    const item = result.item;
    // Fall back to a single-cell reel of just the won item if we don't have
    // the crate's item list cached (e.g. loadCrates hasn't resolved yet) —
    // still shows the correct result, just without the scroll flourish.
    const reel = crateItems.length ? buildReel(crateItems, item) : [item];
    const landingIndex = crateItems.length ? LANDING_INDEX : 0;

    els.spinResult.hidden = true;
    els.spinOverlay.hidden = false;
    els.spinTrack.style.transition = "none";
    els.spinTrack.style.transform = "translateX(0)";
    els.spinTrack.innerHTML = reel.map(spinCellHtml).join("");

    // Force layout so the transition reset above actually takes effect
    // before the animated transform is applied below.
    void els.spinTrack.offsetWidth;

    const viewportWidth = els.spinViewport.clientWidth;
    const targetOffset = landingIndex * CELL_WIDTH + CELL_WIDTH / 2 - viewportWidth / 2;
    const jitter = (Math.random() - 0.5) * (CELL_WIDTH * 0.4);

    requestAnimationFrame(() => {
      els.spinTrack.style.transition = `transform ${SPIN_DURATION_MS}ms cubic-bezier(0.1, 0.85, 0.15, 1)`;
      els.spinTrack.style.transform = `translateX(-${targetOffset + jitter}px)`;
    });

    const onDone = (e) => {
      if (e.target !== els.spinTrack || e.propertyName !== "transform") return;
      els.spinTrack.removeEventListener("transitionend", onDone);
      showLandedResult(result);
      resolve();
    };
    els.spinTrack.addEventListener("transitionend", onDone);
  });
}

function closeSpinOverlay() {
  els.spinOverlay.hidden = true;
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

  document.getElementById("spin-close")?.addEventListener("click", () => closeSpinOverlay());
  document.getElementById("spin-keep")?.addEventListener("click", () => closeSpinOverlay());
  document.getElementById("spin-sell")?.addEventListener("click", async () => {
    await sellItem(item.id);
    closeSpinOverlay();
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
