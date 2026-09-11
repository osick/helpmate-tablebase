import { makeBoard } from "./board.js";
import { stipulation, numberedTokens, grade, pickSession, byPieces, byTheme, themeCounts } from "./lib/solution.js";

const SESSION = 10;
let all = [], board, session = [], idx = 0, puzzle = null, ply = 0, revealed = false, solved = 0;

export async function initPuzzles({ puzzles }) {
  all = puzzles;
  board = makeBoard(document.getElementById("puzzle-board"), { input: true });
  board.enableInput(onDrag);
  const lengths = [...new Set(all.map((p) => p.dtm))].sort((a, b) => a - b);
  const lenSel = document.getElementById("puzzle-length");
  lenSel.innerHTML = `<option value="all">any</option>` +
    lengths.map((d) => `<option value="${d}">${stipulation(d)}</option>`).join("");
  const themeSel = document.getElementById("puzzle-theme");
  themeSel.innerHTML = `<option value="all">any</option>` +
    themeCounts(all).map(([t, n]) => `<option value="${t}">${t} (${n})</option>`).join("");
  for (const id of ["puzzle-length", "puzzle-pieces", "puzzle-theme"]) {
    document.getElementById(id).addEventListener("change", startSession);
  }
  document.getElementById("puzzle-reveal").addEventListener("click", reveal);
  document.getElementById("puzzle-next").addEventListener("click", next);
  startSession();
}

function pool() {
  const len = document.getElementById("puzzle-length").value;
  const pieces = document.getElementById("puzzle-pieces").value;
  const theme = document.getElementById("puzzle-theme").value;
  let p = byTheme(byPieces(all, pieces), theme);
  if (len !== "all") p = p.filter((x) => String(x.dtm) === len);
  return p;
}

function startSession() {
  const p = pool();
  document.getElementById("puzzle-count").textContent = `${p.length} puzzles match`;
  session = pickSession(p, SESSION);
  idx = 0; solved = 0;
  document.getElementById("puzzle-score").textContent = "0";
  if (!session.length) {
    puzzle = null;
    setStatus("No puzzle matches these filters.", "");
    document.getElementById("puzzle-line").textContent = "";
    renderThemes(false);
    return;
  }
  load();
}

function load() {
  puzzle = session[idx]; ply = 0; revealed = false;
  board.show(puzzle.fen, true);
  const stm = puzzle.fen.split(" ")[1] === "w" ? "White" : "Black";
  document.getElementById("puzzle-readout").innerHTML =
    `<span><strong>${stipulation(puzzle.dtm)}</strong> · ${puzzle.material} · ${idx + 1}/${session.length}</span>` +
    `<span>${stm} to move</span>`;
  setStatus(`${stm} moves first. Find the only solution.`, "");
  renderThemes(false);
  renderLine();
}

// The themes a puzzle shows describe its mate picture and its mechanism, so
// they are a spoiler: shown only once the puzzle is solved or revealed.
function renderThemes(show) {
  const el = document.getElementById("puzzle-themes");
  const themes = (puzzle && puzzle.themes) || [];
  if (!show || !themes.length) { el.innerHTML = ""; el.hidden = true; return; }
  el.hidden = false;
  el.innerHTML = `<span class="tags-label">Themes</span>` +
    themes.map((t) => `<span class="tag">${t}</span>`).join("");
}

function onDrag(uci) {
  if (!puzzle || revealed || ply >= puzzle.plies.length) return "wrong";
  const verdict = grade(puzzle.plies[ply].uci, uci);
  if (verdict === "correct") {
    board.show(puzzle.plies[ply].fen);
    ply += 1;
    if (ply === puzzle.plies.length) {
      solved += 1;
      document.getElementById("puzzle-score").textContent = String(solved);
      setStatus("Mate. That was the only way.", "ok");
      renderThemes(true);
    } else {
      setStatus(`${puzzle.plies[ply - 1].san} — yes. ${sideToMove()} to move.`, "ok");
    }
    renderLine();
  } else if (verdict === "wrong") {
    setStatus("Not that one.", "bad");
  }
  return verdict;
}

// Side to move after `ply` plies: the starting side on even plies.
function sideToMove() {
  const startsWhite = puzzle.fen.split(" ")[1] === "w";
  return (ply % 2 === 0) === startsWhite ? "White" : "Black";
}

function reveal() {
  if (!puzzle) return;
  revealed = true; ply = puzzle.plies.length;
  board.show(puzzle.plies[ply - 1].fen);
  setStatus("Solution shown.", "");
  renderThemes(true);
  renderLine();
}

function next() {
  if (!session.length) { startSession(); return; }
  idx += 1;
  if (idx >= session.length) {
    setStatus(`Session over: ${solved} of ${session.length} solved. Starting a new one.`, "");
    startSession();
    return;
  }
  load();
}

function renderLine() {
  const el = document.getElementById("puzzle-line");
  const toks = numberedTokens(puzzle.fen, puzzle.plies);
  const shown = revealed ? toks : toks.filter((t) => t.ply <= ply);
  el.innerHTML = `<span class="mono">${puzzle.fen}</span><br>` +
    shown.map((t) => `<span class="${t.ply <= ply ? "played" : ""}">${t.text}</span>`).join(" ");
}

function setStatus(text, cls) {
  const el = document.getElementById("puzzle-status");
  el.textContent = text; el.className = `status ${cls}`;
}
