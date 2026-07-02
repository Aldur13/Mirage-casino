// Minimal auth + balance UI for Phase 1. Talks to the FastAPI backend on
// the same origin (see backend/main.py's catch-all static file route).

const TOKEN_KEY = "mirage_casino_token";

const els = {
  authForms: document.getElementById("auth-forms"),
  loginForm: document.getElementById("login-form"),
  registerForm: document.getElementById("register-form"),
  dashboard: document.getElementById("dashboard"),
  userName: document.getElementById("user-name"),
  balance: document.getElementById("balance"),
  logoutBtn: document.getElementById("logout-btn"),
  message: document.getElementById("message"),
};

function showMessage(text, isError = true) {
  els.message.textContent = text;
  els.message.style.color = isError ? "var(--danger)" : "var(--accent)";
}

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function api(path, options = {}) {
  const token = getToken();
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(path, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `Request failed (${res.status})`);
  }
  return data;
}

function formatBalance(cents, currency) {
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(cents / 100);
}

async function loadDashboard() {
  const [me, balance] = await Promise.all([api("/me"), api("/balance")]);
  els.userName.textContent = me.name;
  els.balance.textContent = formatBalance(balance.balance_cents, balance.currency);
  els.authForms.hidden = true;
  els.dashboard.hidden = false;
}

els.loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  showMessage("");
  const form = new FormData(e.target);
  try {
    const { access_token } = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
    });
    setToken(access_token);
    await loadDashboard();
  } catch (err) {
    showMessage(err.message);
  }
});

els.registerForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  showMessage("");
  const form = new FormData(e.target);
  try {
    await api("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        name: form.get("name"),
        email: form.get("email"),
        password: form.get("password"),
      }),
    });
    showMessage("Registered — logging you in...", false);
    const { access_token } = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
    });
    setToken(access_token);
    await loadDashboard();
  } catch (err) {
    showMessage(err.message);
  }
});

els.logoutBtn.addEventListener("click", () => {
  clearToken();
  els.dashboard.hidden = true;
  els.authForms.hidden = false;
});

if (getToken()) {
  loadDashboard().catch(() => {
    clearToken();
  });
}
