const select = document.getElementById("board-select");
const list = document.getElementById("board-list");
const MEDALS = ["🥇", "🥈", "🥉"];
const COUNT_BOARDS = new Set(["most-games-played", "most-legendary-items"]);

async function load() {
  const board = select.value;
  const res = await fetch(`/leaderboards/${board}`);
  const { entries } = await res.json();
  const isMoney = !COUNT_BOARDS.has(board);
  list.innerHTML = "";
  entries.forEach((e, i) => {
    const li = document.createElement("li");
    const value = isMoney ? `€${(e.value / 100).toFixed(2)}` : e.value;
    li.innerHTML = `
      <span class="board-rank">${MEDALS[i] || i + 1}</span>
      <span class="board-name">${e.name}</span>
      <span class="board-value num">${value}</span>
      ${e.extra ? `<span class="board-extra">${e.extra}</span>` : ""}
    `;
    list.appendChild(li);
  });
}

select.addEventListener("change", load);
load();
