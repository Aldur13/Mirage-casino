const els = {
  name: document.getElementById("profile-name"),
  statsGrid: document.getElementById("stats-grid"),
  achievementsList: document.getElementById("achievements-list"),
};

async function api(path) {
  const token = localStorage.getItem(TOKEN_KEY);
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(path, { headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

function statCard(label, value) {
  const div = document.createElement("div");
  div.className = "stat-card";
  div.innerHTML = `<div class="label">${label}</div><div class="value num">${value}</div>`;
  return div;
}

function money(cents) {
  return `€${(cents / 100).toFixed(2)}`;
}

async function load() {
  try {
    const me = await api("/me");
    els.name.textContent = me.name;

    const s = await api("/statistics/me");
    const cards = [
      ["Games played", s.games_played],
      ["Games won", s.games_won],
      ["Games lost", s.games_lost],
      ["Total wagered", money(s.total_wagered_cents)],
      ["Total profit", money(s.total_profit_cents)],
      ["Biggest win", money(s.biggest_win_cents)],
      ["Biggest loss", money(s.biggest_loss_cents)],
      ["Favorite game", s.favorite_game || "—"],
      ["Crash highest multiplier", s.crash_highest_multiplier ? `${s.crash_highest_multiplier.toFixed(2)}x` : "—"],
      ["Blackjack win rate", s.blackjack_win_rate_pct != null ? `${s.blackjack_win_rate_pct}%` : "—"],
      ["Mines cashouts", s.mines_cashouts],
      ["Crates opened", s.crates_opened],
      ["Legendary items", s.legendary_items_obtained],
    ];
    els.statsGrid.innerHTML = "";
    cards.forEach(([label, value]) => els.statsGrid.appendChild(statCard(label, value)));
  } catch (err) {
    els.name.textContent = "Log in to view your profile";
  }

  try {
    const { achievements } = await api("/achievements/me");
    els.achievementsList.innerHTML = "";
    achievements.forEach((a) => {
      const div = document.createElement("div");
      div.className = "achievement-card" + (a.unlocked ? " unlocked" : " locked");
      div.innerHTML = `
        <div class="ach-icon">${a.unlocked ? "🏆" : "🔒"}</div>
        <div class="ach-name">${a.name}</div>
        <div class="ach-desc">${a.description}</div>
      `;
      els.achievementsList.appendChild(div);
    });
  } catch (err) {
    // Achievements endpoint requires auth; ignore if not logged in.
  }
}

load();
