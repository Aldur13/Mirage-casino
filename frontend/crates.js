const TOKEN_KEY = "mirage_casino_token";

const els = {
  crateList: document.getElementById("crate-list"),
  inventoryList: document.getElementById("inventory-list"),
  message: document.getElementById("crates-message"),
};

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

async function loadCrates() {
  const { crates } = await api("/crates");
  els.crateList.innerHTML = "";
  crates.forEach((crate) => {
    const card = document.createElement("div");
    card.className = "crate-card";
    card.innerHTML = `
      <div class="emoji">🎁</div>
      <div>${crate.name}</div>
      <div>${(crate.price_cents / 100).toFixed(2)}</div>
      <button data-id="${crate.id}">Open</button>
    `;
    card.querySelector("button").addEventListener("click", () => openCrate(crate.id));
    els.crateList.appendChild(card);
  });
}

async function openCrate(crateId) {
  try {
    const result = await api(`/crates/${crateId}/open`, { method: "POST" });
    showMessage(`You got: ${result.item.name} (${result.item.rarity})`);
    await loadInventory();
  } catch (err) {
    showMessage(err.message);
  }
}

async function loadInventory() {
  const { items } = await api("/crates/inventory/mine");
  els.inventoryList.innerHTML = "";
  items.filter((i) => i.status === "owned").forEach((item) => {
    const card = document.createElement("div");
    card.className = `item-card rarity-${item.rarity}`;
    card.innerHTML = `
      <div class="emoji">${item.image_url}</div>
      <div>${item.name}</div>
      <div>Sell: ${(item.sell_value_cents / 100).toFixed(2)}</div>
      <button data-id="${item.id}">Sell</button>
    `;
    card.querySelector("button").addEventListener("click", () => sellItem(item.id));
    els.inventoryList.appendChild(card);
  });
}

async function sellItem(itemId) {
  try {
    const result = await api(`/crates/inventory/${itemId}/sell`, { method: "POST" });
    showMessage(`Sold for ${(result.payout_cents / 100).toFixed(2)}`);
    await loadInventory();
  } catch (err) {
    showMessage(err.message);
  }
}

loadCrates();
loadInventory().catch(() => {});
