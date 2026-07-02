const select = document.getElementById("board-select");
const list = document.getElementById("board-list");

async function load() {
  const board = select.value;
  const res = await fetch(`/leaderboards/${board}`);
  const { entries } = await res.json();
  list.innerHTML = "";
  entries.forEach((e) => {
    const li = document.createElement("li");
    li.textContent = `${e.name} — ${e.value}${e.extra ? ` (${e.extra})` : ""}`;
    list.appendChild(li);
  });
}

select.addEventListener("change", load);
load();
