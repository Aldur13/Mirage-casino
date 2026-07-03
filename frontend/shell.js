// Shared sidebar behavior for every authenticated page (balance, user name,
// active-link highlight, logout). Included after style.css/markup on each page.
const TOKEN_KEY = "mirage_casino_token";

function shellApi(path) {
  const token = localStorage.getItem(TOKEN_KEY);
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  return fetch(path, { headers }).then(async (res) => {
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
    return data;
  });
}

function formatMoney(cents, currency) {
  return new Intl.NumberFormat(undefined, { style: "currency", currency: currency || "EUR" }).format(cents / 100);
}

async function initShell() {
  const token = localStorage.getItem(TOKEN_KEY);
  if (!token) {
    window.location.href = "/";
    return;
  }

  const path = window.location.pathname;
  document.querySelectorAll(".nav-links a").forEach((a) => {
    if (a.getAttribute("href") === path) a.classList.add("active");
  });

  const logoutBtn = document.getElementById("sidebar-logout");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      localStorage.removeItem(TOKEN_KEY);
      window.location.href = "/";
    });
  }

  const nameEl = document.getElementById("sidebar-name");
  const balanceEl = document.getElementById("sidebar-balance");

  try {
    const [me, balance] = await Promise.all([shellApi("/me"), shellApi("/balance")]);
    if (nameEl) nameEl.textContent = me.name;
    if (balanceEl) balanceEl.textContent = formatMoney(balance.balance_cents, balance.currency);
  } catch (err) {
    localStorage.removeItem(TOKEN_KEY);
    window.location.href = "/";
  }
}

initShell();
