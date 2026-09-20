import test from "node:test";
import assert from "node:assert/strict";
import { parsePlies } from "../js/static-board.js";

test("parsePlies reads the JSON the renderer embedded", () => {
  const el = { dataset: { plies: JSON.stringify([[{ san: "Qg7#", uci: "g5g7", fen: "8/8" }]]) } };
  const lines = parsePlies(el);
  assert.equal(lines.length, 1);
  assert.equal(lines[0][0].san, "Qg7#");
});

test("parsePlies returns an empty list rather than throwing on bad data", () => {
  assert.deepEqual(parsePlies({ dataset: { plies: "not json" } }), []);
  assert.deepEqual(parsePlies({ dataset: {} }), []);
});
