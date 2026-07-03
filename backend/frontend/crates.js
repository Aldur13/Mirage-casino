const els = {
  crateList: document.getElementById("crate-list"),
  inventoryList: document.getElementById("inventory-list"),
  message: document.getElementById("crates-message"),
};

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

async function loadCrates() {
  const { crates } = await api("/crates");
  els.crateList.innerHTML = "";
  for (const crate of crates) {
    const detail = await api(`/crates/${crate.id}`);
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
  }
}

async function openCrate(crateId) {
  try {
    const result = await api(`/crates/${crateId}/open`, { method: "POST" });
    showMessage(`You got: ${result.item.name} (${result.item.rarity})`);
    await loadInventory();
  } catch (err) {
    showMessage(err.message, true);
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
    await loadInventory();
  } catch (err) {
    showMessage(err.message, true);
  }
}

loadCrates().catch((err) => showMessage(`Failed to load crates: ${err.message}`));
loadInventory().catch(() => {});
