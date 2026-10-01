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

import { contributorCards, sixProgress } from "../js/lib/materials.js";

test("contributor cards escape names and link profiles unless anonymous", () => {
  const status = { contributors: [
    { display: "<b>T</b>", hf: "T31M", github: "T31M", anonymous: false, tables: 30, six: 30, materials: [] },
    { display: "anonymous", hf: null, github: null, anonymous: true, tables: 2, six: 2, materials: [] }] };
  const html = contributorCards(status);
  assert.ok(html.includes("&lt;b&gt;T&lt;/b&gt;") && !html.includes("<b>T</b>"));
  assert.ok(html.includes("https://huggingface.co/T31M") && html.includes("https://github.com/T31M"));
  assert.ok(html.includes(`#/materials?contributor=${encodeURIComponent("<b>T</b>")}`));
  assert.equal((html.match(/huggingface\.co/g) || []).length, 1);            // none for anonymous
  assert.equal(contributorCards(null), "");
});

test("six-piece progress with and without status", () => {
  const status = { counts: { six: { done: 46, "in review": 30, claimed: 50, open: 519, "not needed": 70 } } };
  assert.equal(sixProgress(status, { by_pieces: { 6: 46 } }),
    "Six men: 46 done, 30 in review, 50 claimed, 519 open of 645.");
  assert.equal(sixProgress(null, { by_pieces: { 6: 31 } }), "Six men: 31 of 645 done.");
});

test("six-piece progress falls back on a malformed status", () => {
  const corpus = { by_pieces: { 6: 31 } };
  const fallback = "Six men: 31 of 645 done.";
  assert.equal(sixProgress({ counts: {} }, corpus), fallback);
  assert.equal(sixProgress({ counts: { six: { done: 1, open: 2 } } }, corpus), fallback);
  assert.ok(!sixProgress({ counts: { six: { done: 1 } } }, corpus).includes("undefined"));
});
