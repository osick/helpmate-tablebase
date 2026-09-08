import { stipulation, sortRows, byPieces, humanBytes } from "./lib/solution.js";

let rows = [], key = "pieces", dir = "asc";
const fmt = (n) => Number(n).toLocaleString("en-US");

export async function initMaterials({ materials, corpus }) {
  rows = materials;
  document.getElementById("materials-lede").textContent =
    `${corpus.tables} tables, ${humanBytes(corpus.size_bytes)} block-compressed. ` +
    `${corpus.markers} of them are markers: material in which no helpmate exists at all, ` +
    `stored as a verdict rather than a table. A dash in "longest mate" is such a class.`;
  document.querySelectorAll("#materials-table th").forEach((th) => {
    th.addEventListener("click", () => {
      if (key === th.dataset.key) dir = dir === "asc" ? "desc" : "asc";
      else { key = th.dataset.key; dir = key === "material" ? "asc" : "desc"; }
      render();
    });
  });
  document.getElementById("materials-pieces").addEventListener("change", render);
  render();
}

function render() {
  const pieces = document.getElementById("materials-pieces").value;
  const shown = sortRows(byPieces(rows, pieces), key, dir);
  document.getElementById("materials-count").textContent = `${shown.length} tables`;
  document.querySelectorAll("#materials-table th").forEach((th) => {
    th.classList.toggle("sorted", th.dataset.key === key);
    th.classList.toggle("asc", th.dataset.key === key && dir === "asc");
    th.classList.toggle("num", th.dataset.key !== "material");
  });
  document.querySelector("#materials-table tbody").innerHTML = shown.map((r) => {
    const marker = r.max_dtm === null;
    return `<tr class="${marker ? "marker" : ""}">
      <td class="mono">${r.material}</td><td class="num">${r.pieces}</td>
      <td class="num">${marker ? "—" : stipulation(r.max_dtm)}</td>
      <td class="num">${marker ? "0" : fmt(r.solvable)}</td>
      <td class="num">${marker ? "0" : fmt(r.unique)}</td>
      <td class="num">${humanBytes(r.size_bytes)}</td></tr>`;
  }).join("");
}
