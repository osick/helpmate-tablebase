import test from "node:test";
import assert from "node:assert/strict";
import { STATES, priorityLabel, wildcardMatch, mergeStatus, filterRows, defaultOrder,
  parseQuery, toQuery, esc } from "../js/lib/materials.js";

const row = (material, o = {}) => ({ material, pieces: 6, pawns: 0, priority: 1, done: false, ...o });

test("priority labels", () => {
  assert.equal(priorityLabel(1), "P1");
  assert.equal(priorityLabel(4), "P4");
  assert.equal(priorityLabel(null), "—");
});

test("wildcards match per side, as multisets", () => {
  assert.ok(wildcardMatch("KQvkqbb", "KQvk???"));
  assert.ok(wildcardMatch("KQvkqbb", "KQvkb??"));
  assert.ok(!wildcardMatch("KQvkqbb", "KRvk???"));
  assert.ok(!wildcardMatch("KQvkqb", "KQvk???"));
  assert.ok(wildcardMatch("KRRvkbp", "K??vkbp"));
  assert.ok(wildcardMatch("KRRvkbp", "rrv"));          // plain substring, any case
  assert.ok(wildcardMatch("KRRvkbp", ""));
});

test("merge: status wins, fallback without status", () => {
  const rows = [row("KQvkqbb"), row("KRBvkqq", { done: true, priority: 2 }), row("Kvkqqqq", { priority: null })];
  const none = mergeStatus(rows, null);
  assert.deepEqual(none.map((r) => r.state), ["open", "done", "not needed"]);
  const st = { materials: { KQvkqbb: { state: "claimed", contributor: "popeye37", hf_pr: null, claim: 40 } } };
  const m = mergeStatus(rows, st);
  assert.equal(m[0].state, "claimed");
  assert.equal(m[0].contributor, "popeye37");
  assert.equal(m[1].state, "done");
});

test("filters combine; 'all' and '' mean no filter", () => {
  const rows = mergeStatus([row("KQvkqbb"), row("KQvkqbp", { pawns: 1 }), row("KRRvkbb", { priority: 2 }),
    row("KRBvkqq", { done: true, priority: 2 })], null);
  assert.equal(filterRows(rows, { state: "open" }).length, 3);
  assert.equal(filterRows(rows, { state: "open", prio: "1" }).length, 2);
  assert.equal(filterRows(rows, { prio: "1", pawns: "0" }).length, 1);
  assert.equal(filterRows(rows, { q: "KQvk???", state: "all", pieces: "6" }).length, 2);
  assert.equal(filterRows(rows, {}).length, 4);
});

test("contributor filter matches exactly", () => {
  const rows = mergeStatus([row("KQvkqbb"), row("KRRvkbb")],
    { materials: { KQvkqbb: { state: "claimed", contributor: "popeye37" } } });
  assert.equal(filterRows(rows, { contributor: "popeye37" }).length, 1);
  assert.equal(filterRows(rows, { contributor: "popeye" }).length, 0);
});

test("default order: open first, then priority, pawns, name", () => {
  const rows = mergeStatus([row("KRBvkqq", { done: true, priority: 2 }), row("KRRvkbb", { priority: 2 }),
    row("KQvkqbp", { pawns: 1 }), row("KQvkqbb"), row("Kvkqqqq", { priority: null })], null);
  assert.deepEqual(defaultOrder(rows).map((r) => r.material),
    ["KQvkqbb", "KQvkqbp", "KRRvkbb", "KRBvkqq", "Kvkqqqq"]);
  assert.deepEqual(STATES, ["open", "claimed", "in review", "done", "not needed"]);
});

test("hash query round trip", () => {
  const q = parseQuery("#/materials?state=open&prio=1&q=KQvk%3F%3F%3F");
  assert.deepEqual(q, { state: "open", prio: "1", q: "KQvk???" });
  assert.equal(toQuery({ prio: "1", state: "open", pieces: "all", q: "" }), "state=open&prio=1");
  assert.deepEqual(parseQuery("#/materials"), {});
});

test("esc escapes markup", () => {
  assert.equal(esc(`<b>"x" & 'y'</b>`), "&lt;b&gt;&quot;x&quot; &amp; &#39;y&#39;&lt;/b&gt;");
  assert.equal(esc(null), "");
});
