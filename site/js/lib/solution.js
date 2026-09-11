// Pure helpers for stepping through and grading precomputed solutions.
// No DOM, no network, no chess logic: every ply already carries its SAN, its
// UCI and the FEN after it (see tools/build_site_data.py), so the browser
// only ever compares strings and picks positions out of an array.

// Helpmate stipulation from a distance in plies. Black moves first, so an
// even number of plies ends with a White move: h#n. An odd number means
// White is to move and needs one extra half-move: h#n.5.
export function stipulation(dtm) {
  const n = Number(dtm);
  if (!Number.isFinite(n) || n <= 0) return "";
  return n % 2 === 0 ? `h#${n / 2}` : `h#${(n - 1) / 2}.5`;
}

// The placement to show after `ply` moves of the solution have been played
// (0 = the starting position).
export function positionAt(start, plies, ply) {
  if (ply <= 0) return start;
  const i = Math.min(ply, plies.length) - 1;
  return plies[i].fen;
}

// Helpmate move numbering, the project's convention (tools/deepest_lib.py):
// Black moves first, so "1.Kh6 Qg6#" pairs Black's move with White's reply.
// An odd number of plies is White to move: it opens "1...Qg6" and Black's
// first reply starts move two. `upto` bolds nothing; callers mark played
// plies themselves from the returned tokens.
export function numberedLine(startFen, plies) {
  return numberedTokens(startFen, plies).map((t) => t.text).join(" ");
}

// The same line as tokens, one per ply: {text, ply} where ply is 1-based, so
// a renderer can style the plies already played.
export function numberedTokens(startFen, plies) {
  const whiteFirst = startFen.split(" ")[1] === "w";
  const out = [];
  let n = 1;
  plies.forEach((p, i) => {
    if (whiteFirst && i === 0) { out.push({ text: `1...${p.san}`, ply: 1 }); n = 2; return; }
    const blackMove = whiteFirst ? i % 2 === 1 : i % 2 === 0;
    if (blackMove) { out.push({ text: `${n}.${p.san}`, ply: i + 1 }); n += 1; }
    else out.push({ text: p.san, ply: i + 1 });
  });
  return out;
}

// A played move is right when it is the solution's move at this ply. A drag
// without a promotion piece matches a promoting solution move as a prefix,
// which tells the caller to ask which piece; the answer is then graded
// exactly. Returns "correct", "wrong" or "promote".
export function grade(expectedUci, playedUci) {
  const e = String(expectedUci), p = String(playedUci);
  if (e === p) return "correct";
  if (e.length === 5 && p.length === 4 && e.startsWith(p)) return "promote";
  return "wrong";
}

// Pick a puzzle ladder: `n` puzzles ordered by (plies, pieces) drawn evenly
// across the difficulty range, so a session climbs rather than repeats.
export function pickSession(all, n, rnd = Math.random) {
  const sorted = [...all].sort((a, b) => a.dtm - b.dtm || a.pieces - b.pieces);
  if (sorted.length <= n) return sorted;
  const out = [];
  for (let k = 0; k < n; k++) {
    const lo = Math.floor((k * sorted.length) / n);
    const hi = Math.floor(((k + 1) * sorted.length) / n);
    out.push(sorted[lo + Math.floor(rnd() * (hi - lo))]);
  }
  return out;
}

// Filter helpers shared by the deepest and puzzle screens.
export function byPieces(items, pieces) {
  return pieces === "all" ? items : items.filter((x) => String(x.pieces) === String(pieces));
}

// Items whose `themes` list contains `theme`; "all" keeps everything.
export function byTheme(items, theme) {
  return theme === "all" ? items : items.filter((x) => (x.themes || []).includes(theme));
}

// Distinct theme names across `items`, most frequent first, ties alphabetical.
export function themeCounts(items) {
  const n = new Map();
  for (const it of items) for (const t of it.themes || []) n.set(t, (n.get(t) || 0) + 1);
  return [...n.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

export function sortRows(rows, key, dir) {
  const s = dir === "desc" ? -1 : 1;
  return [...rows].sort((a, b) => {
    const x = a[key], y = b[key];
    if (x === y) return a.material < b.material ? -1 : 1;
    if (x === null || x === undefined) return 1;
    if (y === null || y === undefined) return -1;
    return (x < y ? -1 : 1) * s;
  });
}

export function humanBytes(n) {
  if (n < 1024) return `${n} B`;
  const u = ["KiB", "MiB", "GiB", "TiB"];
  let v = n / 1024, i = 0;
  while (v >= 1024 && i < u.length - 1) v /= 1024, i++;
  return `${v < 10 ? v.toFixed(1) : Math.round(v)} ${u[i]}`;
}
