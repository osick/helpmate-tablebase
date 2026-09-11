import test from "node:test";
import assert from "node:assert/strict";
import { stipulation, positionAt, numberedLine, numberedTokens, grade, pickSession, byPieces, byTheme, themeCounts, sortRows, humanBytes }
  from "../js/lib/solution.js";

const START = "8/7k/5K2/8/8/8/8/6Q1 b - - 0 1";
const PLIES = [
  { san: "Kh6", uci: "h7h6", fen: "8/8/5K1k/8/8/8/8/6Q1 w - - 1 2" },
  { san: "Qg6#", uci: "g1g6", fen: "8/8/5KQk/8/8/8/8/8 b - - 2 2" },
];

test("stipulation: even plies h#n, odd plies h#n.5", () => {
  assert.equal(stipulation(2), "h#1");
  assert.equal(stipulation(34), "h#17");
  assert.equal(stipulation(13), "h#6.5");
  assert.equal(stipulation(0), "");
});

test("positionAt walks the precomputed FENs and clamps", () => {
  assert.equal(positionAt(START, PLIES, 0), START);
  assert.equal(positionAt(START, PLIES, 1), PLIES[0].fen);
  assert.equal(positionAt(START, PLIES, 9), PLIES[1].fen);
});

test("numberedLine numbers Black-first lines the helpmate way", () => {
  assert.equal(numberedLine(START, PLIES), "1.Kh6 Qg6#");
  const w = [{ san: "e3" }, { san: "Kf7" }, { san: "e4" }];
  assert.equal(numberedLine("6k1/8/8/8/8/8/4P3/2K5 w - - 0 1", w), "1...e3 2.Kf7 e4");
  assert.deepEqual(numberedTokens(START, PLIES).map((t) => t.ply), [1, 2]);
});

test("grade: exact match, promotion prefix, anything else wrong", () => {
  assert.equal(grade("h7h6", "h7h6"), "correct");
  assert.equal(grade("h7h6", "h7h5"), "wrong");
  assert.equal(grade("e7e8q", "e7e8"), "promote");
  assert.equal(grade("e7e8q", "e7e8n"), "wrong");
  assert.equal(grade("e7e8q", "e7e8q"), "correct");
});

test("pickSession draws one puzzle per difficulty band, in order", () => {
  const all = Array.from({ length: 40 }, (_, i) => ({ id: i, dtm: 2 + (i % 8) * 2, pieces: 3 + (i % 4) }));
  const s = pickSession(all, 5, () => 0);
  assert.equal(s.length, 5);
  for (let i = 1; i < s.length; i++) assert.ok(s[i].dtm >= s[i - 1].dtm);
  assert.equal(pickSession(all.slice(0, 3), 5).length, 3);
});

test("byPieces and sortRows", () => {
  const rows = [
    { material: "KQvk", pieces: 3, max_dtm: 14 },
    { material: "Kvk", pieces: 2, max_dtm: null },
    { material: "KRvk", pieces: 3, max_dtm: 32 },
  ];
  assert.deepEqual(byPieces(rows, 3).map((r) => r.material), ["KQvk", "KRvk"]);
  assert.equal(byPieces(rows, "all").length, 3);
  assert.deepEqual(sortRows(rows, "max_dtm", "desc").map((r) => r.material), ["KRvk", "KQvk", "Kvk"]);
  assert.deepEqual(sortRows(rows, "max_dtm", "asc").map((r) => r.material), ["KQvk", "KRvk", "Kvk"]);
});

test("humanBytes", () => {
  assert.equal(humanBytes(480), "480 B");
  assert.equal(humanBytes(71647), "70 KiB");
  assert.equal(humanBytes(4156844486), "3.9 GiB");
});

test("byTheme and themeCounts", () => {
  const items = [
    { id: 1, themes: ["mirror", "model"] },
    { id: 2, themes: ["model"] },
    { id: 3 },
  ];
  assert.deepEqual(byTheme(items, "all").map((x) => x.id), [1, 2, 3]);
  assert.deepEqual(byTheme(items, "model").map((x) => x.id), [1, 2]);
  assert.deepEqual(byTheme(items, "mirror").map((x) => x.id), [1]);
  assert.deepEqual(byTheme(items, "nosuch"), []);
  assert.deepEqual(themeCounts(items), [["model", 2], ["mirror", 1]]);
});
