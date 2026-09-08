import { makeBoard } from "./board.js";
import { stipulation, positionAt, numberedTokens, byPieces } from "./lib/solution.js";

let all = [], board, current = null, ply = 0;

export async function initDeepest({ deepest }) {
  all = deepest;
  board = makeBoard(document.getElementById("deepest-board"));
  const sel = document.getElementById("deepest-pieces");
  sel.addEventListener("change", () => renderList(sel.value));
  document.getElementById("deepest-first").addEventListener("click", () => go(0));
  document.getElementById("deepest-prev").addEventListener("click", () => go(ply - 1));
  document.getElementById("deepest-next").addEventListener("click", () => go(ply + 1));
  document.getElementById("deepest-last").addEventListener("click", () => go(Infinity));
  document.addEventListener("keydown", (e) => {
    if (document.getElementById("screen-deepest").hidden || !current) return;
    if (e.key === "ArrowRight") go(ply + 1);
    if (e.key === "ArrowLeft") go(ply - 1);
  });
  renderList("all");
  const fromHash = location.hash.split("/")[2];
  select(all.find((d) => d.material === fromHash) || [...all].sort((a, b) => b.dtm - a.dtm)[0]);
}

export function showDeepest(material) {
  const d = all.find((x) => x.material === material);
  if (d && d !== current) select(d);
}

function renderList(pieces) {
  const rows = byPieces(all, pieces).slice().sort((a, b) => b.dtm - a.dtm || a.material.localeCompare(b.material));
  document.getElementById("deepest-count").textContent = `${rows.length} classes`;
  const tbody = document.querySelector("#deepest-table tbody");
  tbody.innerHTML = rows.map((d) => `<tr data-material="${d.material}"${d === current ? ' class="selected"' : ""}>
    <td class="mono">${d.material}</td><td class="num">${d.pieces}</td>
    <td class="num"><strong>${stipulation(d.dtm)}</strong></td><td class="num">${stipulation(d.max_dtm)}</td>
    <td class="num">${d.unique_at_depth.toLocaleString("en-US")}</td></tr>`).join("");
  tbody.querySelectorAll("tr").forEach((tr) => tr.addEventListener("click", () => {
    const d = all.find((x) => x.material === tr.dataset.material);
    history.replaceState(null, "", `#/deepest/${d.material}`);
    select(d);
  }));
}

function select(d) {
  current = d; ply = 0;
  document.querySelectorAll("#deepest-table tbody tr").forEach((tr) =>
    tr.classList.toggle("selected", tr.dataset.material === d.material));
  board.show(d.fen, true);
  render();
}

function go(n) {
  if (!current) return;
  const max = current.plies.length;
  const next = Math.max(0, Math.min(max, n === Infinity ? max : n));
  if (next === ply) return;
  const jump = Math.abs(next - ply) > 1;   // stepping animates; first/last snap
  ply = next;
  board.show(positionAt(current.fen, current.plies, ply), jump);
  render();
}

function render() {
  const d = current;
  const gap = d.max_dtm - d.dtm;
  document.getElementById("deepest-readout").innerHTML =
    `<span><strong>${d.material}</strong> · ${stipulation(d.dtm)}, unique solution</span>` +
    `<span>class runs to ${stipulation(d.max_dtm)} (${gap} plies deeper, all with duals)</span>`;
  const toks = numberedTokens(d.fen, d.plies);
  document.getElementById("deepest-line").innerHTML =
    `<span class="mono">${d.fen}</span><br>` +
    toks.map((t) => `<span class="${t.ply <= ply ? "played" : ""}">${t.text}</span>`).join(" ");
  document.getElementById("deepest-prev").disabled = ply === 0;
  document.getElementById("deepest-first").disabled = ply === 0;
  document.getElementById("deepest-next").disabled = ply === d.plies.length;
  document.getElementById("deepest-last").disabled = ply === d.plies.length;
}
