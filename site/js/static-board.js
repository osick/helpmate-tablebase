// Boards on the generated material pages. The SPA's screens build their own
// boards; these pages have no router and no app.js, so this module does the
// one thing they need: turn every .board the renderer emitted into a board
// that steps through the solutions embedded beside it.
import { makeBoard } from "./board.js";

export function parsePlies(el) {
  try {
    const raw = el.dataset.plies;
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];                       // a malformed attribute shows a static board
  }
}

function wire(el) {
  const fen = el.dataset.fen;
  const lines = parsePlies(el);
  const board = makeBoard(el, { assetsUrl: "../vendor/cm-chessboard/assets/" });
  board.show(fen, true);
  if (!lines.length) return;

  const plies = lines[0];
  let ply = 0;
  const controls = document.createElement("div");
  controls.className = "board-controls";
  controls.innerHTML =
    `<button type="button" data-step="-1">‹</button>` +
    `<span class="ply">start</span>` +
    `<button type="button" data-step="1">›</button>`;
  el.after(controls);

  const render = () => {
    board.show(ply === 0 ? fen : plies[ply - 1].fen);
    controls.querySelector(".ply").textContent =
      ply === 0 ? "start" : plies[ply - 1].san;
  };
  controls.addEventListener("click", (ev) => {
    const step = Number(ev.target.dataset.step || 0);
    if (!step) return;
    ply = Math.min(plies.length, Math.max(0, ply + step));
    render();
  });
}

if (typeof document !== "undefined") {
  document.querySelectorAll(".board").forEach(wire);
}
